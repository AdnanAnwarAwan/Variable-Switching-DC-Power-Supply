/**
 * @file    main.c
 * @brief   Variable Switching DC Power Supply — main application.
 *
 *          STM32F103C8T6 @ 72 MHz.
 *          Synchronous buck (IR2104 half-bridge driver): 1.25-30 V, 0-5 A.
 *          Voltage PID at 50 us (20 kHz) in the TIM1 update ISR.
 *
 *  CONTROL-LOOP RATE:
 *    TIM1 runs the switching PWM at 200 kHz (period 359 @ 72 MHz). The update
 *    interrupt is divided down by the repetition counter (RCR = 9) so it fires
 *    once every 10 switching periods = 20 kHz = 50 us. This is what makes the
 *    "50 us PID loop" real; without RCR the ISR would fire at 200 kHz (5 us),
 *    which cannot host a ~21 us ADC read. See docs/pid_control.md.
 *
 *  GATE DRIVE:
 *    A single PWM output (PA8) feeds IR2104 IN. The IR2104 generates the
 *    complementary HO/LO with its own internal dead-time and shoot-through
 *    interlock, so no STM32 complementary output / TIM1 dead-time is used.
 *
 * @author  Adnan Anwar Awan
 */
#include "main.h"
#include "pid.h"
#include "adc.h"
#include "display.h"
#include "ina226.h"
#include <stdio.h>

/* ── HAL handles ── */
ADC_HandleTypeDef  hadc1;
I2C_HandleTypeDef  hi2c1;
TIM_HandleTypeDef  htim1;   /* PWM        */
TIM_HandleTypeDef  htim3;   /* Encoder    */
TIM_HandleTypeDef  htim4;   /* Fan PWM    */
UART_HandleTypeDef huart1;  /* Debug UART */
IWDG_HandleTypeDef hiwdg;   /* Watchdog   */

/* ── Application constants ── */
#define SWITCHING_FREQ_HZ   200000U
#define PWM_PERIOD          (72000000U / SWITCHING_FREQ_HZ - 1U)   /* = 359 */
#define CTRL_DIVIDER        10U        /* RCR+1 : 200 kHz / 10 = 20 kHz ISR */
#define MAX_DUTY            (PWM_PERIOD - 10U)
#define SOFTSTART_STEPS     100U       /* 100 * 50 us = 5 ms ramp */
#define FAN_ON_TEMP_C       50.0f
#define SHUTDOWN_TEMP_C     85.0f
#define V_MIN               1.25f
#define V_MAX               30.0f
#define I_LIMIT_DEFAULT     5.0f
#define I_ALERT_AMPS        5.5f       /* INA226 hardware over-current trip */

/* ── PID + setpoints + measured (ISR-shared) ── */
static PID_t vpid;
static volatile float    v_setpoint = 12.0f;
static volatile float    i_limit    = I_LIMIT_DEFAULT;
static volatile float    v_measured = 0.0f;
static volatile float    i_measured = 0.0f;
static volatile float    temp_c     = 25.0f;
static volatile uint8_t  fault_active = 0;
static volatile uint32_t ss_count   = 0;
static volatile uint8_t  mode_cc    = 0;

/* ── Prototypes ── */
static void SystemClock_Config(void);
static void MX_GPIO_Init(void);
static void MX_ADC1_Init(void);
static void MX_I2C1_Init(void);
static void MX_TIM1_Init(void);
static void MX_TIM3_Init(void);
static void MX_TIM4_Init(void);
static void MX_USART1_Init(void);
static void MX_IWDG_Init(void);
static void Fault_Shutdown(const char *reason);
static void Fan_SetDuty(uint8_t percent);

/* ─────────────────────────────────────────────────────────── main ─── */
int main(void)
{
    HAL_Init();
    SystemClock_Config();

    MX_GPIO_Init();
    MX_ADC1_Init();
    MX_I2C1_Init();
    MX_TIM1_Init();
    MX_TIM3_Init();
    MX_TIM4_Init();
    MX_USART1_Init();
    MX_IWDG_Init();

    /* Enable the converter: IR2104 /SD high */
    HAL_GPIO_WritePin(PORT_IR2104_SD, PIN_IR2104_SD, GPIO_PIN_SET);

    Display_Init();
    Display_Clear();
    INA226_Init(I_ALERT_AMPS);

    /* Kp=0.8, Ki=0.02, Kd=0.001, out [0..MAX_DUTY], int clamp 500 */
    PID_Init(&vpid, 0.8f, 0.02f, 0.001f, 0.0f, (float)MAX_DUTY, 500.0f);

    /* Start single-output PWM and the divided-down control ISR */
    HAL_TIM_PWM_Start(&htim1, TIM_CHANNEL_1);
    HAL_TIM_Base_Start_IT(&htim1);

    HAL_TIM_Encoder_Start(&htim3, TIM_CHANNEL_ALL);
    HAL_TIM_PWM_Start(&htim4, TIM_CHANNEL_4);

    printf("Variable Switching DC PSU - Adnan Anwar Awan\r\n");
    printf("Vset=%.2fV  Ilim=%.2fA\r\n", v_setpoint, i_limit);

    uint32_t last_display = 0, last_isense = 0;
    int32_t  enc_last = 0;

    while (1)
    {
        HAL_IWDG_Refresh(&hiwdg);

        /* INA226 over I2C at ~1 kHz — NEVER in the 50 us ISR (I2C read is
         * ~70-100 us). Fast OCP is the INA226 ALERT pin, not this poll. */
        if (HAL_GetTick() - last_isense >= 1) {
            last_isense = HAL_GetTick();
            i_measured  = INA226_ReadCurrent();
        }

        /* Encoder -> voltage setpoint (0.1 V / detent) */
        int32_t enc_now   = (int32_t)__HAL_TIM_GET_COUNTER(&htim3);
        int32_t enc_delta = enc_now - enc_last;
        enc_last = enc_now;
        if (enc_delta != 0) {
            v_setpoint += (float)enc_delta * 0.1f;
            if (v_setpoint < V_MIN) v_setpoint = V_MIN;
            if (v_setpoint > V_MAX) v_setpoint = V_MAX;
            ss_count = 0;               /* re-arm soft-start on change */
            PID_Reset(&vpid);
        }

        /* Thermal management */
        temp_c = ADC_ReadTemperature();
        if (temp_c >= SHUTDOWN_TEMP_C) {
            Fault_Shutdown("OVER TEMP");
        } else if (temp_c >= FAN_ON_TEMP_C) {
            uint8_t fan_pct = (uint8_t)((temp_c - FAN_ON_TEMP_C) /
                              (SHUTDOWN_TEMP_C - FAN_ON_TEMP_C) * 100.0f);
            Fan_SetDuty(fan_pct);
        } else {
            Fan_SetDuty(0);
        }

        /* Display + telemetry at 10 Hz */
        if (HAL_GetTick() - last_display >= 100) {
            last_display = HAL_GetTick();
            float vo = v_measured, io = i_measured;
            Display_Update(v_setpoint, vo, io, mode_cc);
            printf("Vset=%.2f Vout=%.2f Iout=%.2f T=%.1fC %s\r\n",
                   v_setpoint, vo, io, temp_c, mode_cc ? "[CC]" : "[CV]");
        }
    }
}

/* ───────────────────────── TIM1 update ISR — PID at 50 us ─────────── */
void HAL_TIM_PeriodElapsedCallback(TIM_HandleTypeDef *htim)
{
    if (htim->Instance != TIM1) return;
    if (fault_active)           return;

    v_measured = ADC_ReadVoltage();     /* ~21 us, fits the 50 us budget */

    /* Over-current handling (coarse; fast trip is the ALERT EXTI below) */
    if (i_measured > i_limit + 0.5f) {
        Fault_Shutdown("OVER CURRENT");
        return;
    }
    if (i_measured > i_limit) {
        mode_cc = 1;
        HAL_GPIO_WritePin(PORT_CC_LED, PIN_CC_LED, GPIO_PIN_SET);
        HAL_GPIO_WritePin(PORT_CV_LED, PIN_CV_LED, GPIO_PIN_RESET);
    } else {
        mode_cc = 0;
        HAL_GPIO_WritePin(PORT_CV_LED, PIN_CV_LED, GPIO_PIN_SET);
        HAL_GPIO_WritePin(PORT_CC_LED, PIN_CC_LED, GPIO_PIN_RESET);
    }

    float duty = PID_Update(&vpid, v_setpoint, v_measured);

    if (ss_count < SOFTSTART_STEPS) {
        duty = duty * (float)ss_count / (float)SOFTSTART_STEPS;
        ss_count++;
    }
    __HAL_TIM_SET_COMPARE(&htim1, TIM_CHANNEL_1, (uint32_t)duty);
}

/* ─────────── INA226 ALERT — hardware-threshold fast over-current ───── */
/* This EXTI fires on the INA226 ALERT pin the moment shunt current exceeds
 * I_ALERT_AMPS, independent of the 1 kHz current poll. It is still firmware-
 * mediated (MCU pin -> firmware -> /SD). For a path that does NOT depend on
 * firmware at all, wire ALERT directly to IR2104 /SD in hardware — see
 * docs/design_review_findings.md DR-3. */
void HAL_GPIO_EXTI_Callback(uint16_t pin)
{
    if (pin == PIN_INA226_ALERT) {
        Fault_Shutdown("OC ALERT");
    }
}

/* ───────────────────────────── fault handler ─────────────────────── */
static void Fault_Shutdown(const char *reason)
{
    fault_active = 1;

    __HAL_TIM_SET_COMPARE(&htim1, TIM_CHANNEL_1, 0);
    HAL_TIM_PWM_Stop(&htim1, TIM_CHANNEL_1);

    /* IR2104 /SD low = both gates off (hardware kill) */
    HAL_GPIO_WritePin(PORT_IR2104_SD, PIN_IR2104_SD, GPIO_PIN_RESET);
    /* FAULT LED on (PA4) */
    HAL_GPIO_WritePin(PORT_FAULT_LED, PIN_FAULT_LED, GPIO_PIN_SET);

    Display_ShowFault(reason);
    printf("FAULT: %s\r\n", reason);
}

/* ─────────────────────────────── fan PWM ─────────────────────────── */
static void Fan_SetDuty(uint8_t percent)
{
    uint32_t arr  = __HAL_TIM_GET_AUTORELOAD(&htim4);
    uint32_t duty = ((uint32_t)percent * (arr + 1U)) / 100U;
    __HAL_TIM_SET_COMPARE(&htim4, TIM_CHANNEL_4, duty);
}

/* ───────────────────────── printf -> USART1 ──────────────────────── */
int _write(int file, char *ptr, int len)
{
    (void)file;
    HAL_UART_Transmit(&huart1, (uint8_t *)ptr, (uint16_t)len, HAL_MAX_DELAY);
    return len;
}

/* ══════════════════════════════════════════════════════════════════
 *  Peripheral initialisation.
 *  These are hand-maintained equivalents of the CubeMX-generated code.
 *  Re-generating from the provided .ioc will overwrite them; the register
 *  intent is documented so the two stay in agreement.
 * ══════════════════════════════════════════════════════════════════ */

static void SystemClock_Config(void)
{
    RCC_OscInitTypeDef osc = {0};
    RCC_ClkInitTypeDef clk = {0};
    RCC_PeriphCLKInitTypeDef pclk = {0};

    osc.OscillatorType = RCC_OSCILLATORTYPE_HSE;
    osc.HSEState       = RCC_HSE_ON;
    osc.HSEPredivValue = RCC_HSE_PREDIV_DIV1;
    osc.PLL.PLLState   = RCC_PLL_ON;
    osc.PLL.PLLSource  = RCC_PLLSOURCE_HSE;
    osc.PLL.PLLMUL     = RCC_PLL_MUL9;             /* 8 MHz * 9 = 72 MHz */
    HAL_RCC_OscConfig(&osc);

    clk.ClockType = RCC_CLOCKTYPE_HCLK | RCC_CLOCKTYPE_SYSCLK |
                    RCC_CLOCKTYPE_PCLK1 | RCC_CLOCKTYPE_PCLK2;
    clk.SYSCLKSource   = RCC_SYSCLKSOURCE_PLLCLK;
    clk.AHBCLKDivider  = RCC_SYSCLK_DIV1;          /* 72 MHz */
    clk.APB1CLKDivider = RCC_HCLK_DIV2;            /* 36 MHz */
    clk.APB2CLKDivider = RCC_HCLK_DIV1;            /* 72 MHz */
    HAL_RCC_ClockConfig(&clk, FLASH_LATENCY_2);

    pclk.PeriphClockSelection = RCC_PERIPHCLK_ADC;
    pclk.AdcClockSelection    = RCC_ADCPCLK2_DIV6; /* 72/6 = 12 MHz (<14) */
    HAL_RCCEx_PeriphCLKConfig(&pclk);
}

static void MX_GPIO_Init(void)
{
    __HAL_RCC_GPIOA_CLK_ENABLE();
    __HAL_RCC_GPIOB_CLK_ENABLE();
    __HAL_RCC_GPIOC_CLK_ENABLE();

    GPIO_InitTypeDef g = {0};

    /* Outputs: FAULT LED, CV LED, CC LED, IR2104 /SD (start disabled=low) */
    HAL_GPIO_WritePin(PORT_FAULT_LED, PIN_FAULT_LED, GPIO_PIN_RESET);
    HAL_GPIO_WritePin(PORT_CV_LED, PIN_CV_LED, GPIO_PIN_RESET);
    HAL_GPIO_WritePin(PORT_CC_LED, PIN_CC_LED, GPIO_PIN_RESET);
    HAL_GPIO_WritePin(PORT_IR2104_SD, PIN_IR2104_SD, GPIO_PIN_RESET);

    g.Mode = GPIO_MODE_OUTPUT_PP;
    g.Speed = GPIO_SPEED_FREQ_LOW;
    g.Pin = PIN_FAULT_LED;   HAL_GPIO_Init(PORT_FAULT_LED, &g);
    g.Pin = PIN_CV_LED;      HAL_GPIO_Init(PORT_CV_LED, &g);
    g.Pin = PIN_CC_LED;      HAL_GPIO_Init(PORT_CC_LED, &g);
    g.Pin = PIN_IR2104_SD;   HAL_GPIO_Init(PORT_IR2104_SD, &g);

    /* Encoder button: input pull-up */
    g.Mode = GPIO_MODE_INPUT;
    g.Pull = GPIO_PULLUP;
    g.Pin  = PIN_ENC_BTN;    HAL_GPIO_Init(PORT_ENC_BTN, &g);

    /* INA226 ALERT: falling-edge EXTI0, pull-up (ALERT is open-drain) */
    g.Mode = GPIO_MODE_IT_FALLING;
    g.Pull = GPIO_PULLUP;
    g.Pin  = PIN_INA226_ALERT; HAL_GPIO_Init(PORT_ALERT, &g);
    HAL_NVIC_SetPriority(EXTI0_IRQn, 1, 0);
    HAL_NVIC_EnableIRQ(EXTI0_IRQn);
}

static void MX_ADC1_Init(void)
{
    __HAL_RCC_ADC1_CLK_ENABLE();
    __HAL_RCC_GPIOA_CLK_ENABLE();

    GPIO_InitTypeDef g = {0};
    g.Pin  = GPIO_PIN_0 | GPIO_PIN_1;      /* PA0, PA1 analog */
    g.Mode = GPIO_MODE_ANALOG;
    HAL_GPIO_Init(GPIOA, &g);

    hadc1.Instance = ADC1;
    hadc1.Init.ScanConvMode          = ADC_SCAN_DISABLE;
    hadc1.Init.ContinuousConvMode    = DISABLE;
    hadc1.Init.DiscontinuousConvMode = DISABLE;
    hadc1.Init.ExternalTrigConv      = ADC_SOFTWARE_START;
    hadc1.Init.DataAlign             = ADC_DATAALIGN_RIGHT;
    hadc1.Init.NbrOfConversion       = 1;
    HAL_ADC_Init(&hadc1);
    HAL_ADCEx_Calibration_Start(&hadc1);
}

static void MX_I2C1_Init(void)
{
    __HAL_RCC_I2C1_CLK_ENABLE();
    __HAL_RCC_GPIOB_CLK_ENABLE();

    GPIO_InitTypeDef g = {0};
    g.Pin   = GPIO_PIN_6 | GPIO_PIN_7;     /* PB6 SCL, PB7 SDA */
    g.Mode  = GPIO_MODE_AF_OD;
    g.Pull  = GPIO_PULLUP;
    g.Speed = GPIO_SPEED_FREQ_HIGH;
    HAL_GPIO_Init(GPIOB, &g);

    hi2c1.Instance             = I2C1;
    hi2c1.Init.ClockSpeed      = 400000;
    hi2c1.Init.DutyCycle       = I2C_DUTYCYCLE_2;
    hi2c1.Init.AddressingMode  = I2C_ADDRESSINGMODE_7BIT;
    hi2c1.Init.OwnAddress1     = 0;
    HAL_I2C_Init(&hi2c1);
}

static void MX_TIM1_Init(void)
{
    /* 200 kHz PWM, single output CH1 (PA8). RCR = CTRL_DIVIDER-1 so the
     * update ISR is generated at 20 kHz. No complementary output / no TIM1
     * dead-time: the IR2104 makes HO/LO with its internal dead-time. */
    __HAL_RCC_TIM1_CLK_ENABLE();
    __HAL_RCC_GPIOA_CLK_ENABLE();

    GPIO_InitTypeDef g = {0};
    g.Pin   = GPIO_PIN_8;                  /* PA8 = TIM1_CH1 */
    g.Mode  = GPIO_MODE_AF_PP;
    g.Speed = GPIO_SPEED_FREQ_HIGH;
    HAL_GPIO_Init(GPIOA, &g);

    htim1.Instance               = TIM1;
    htim1.Init.Prescaler         = 0;
    htim1.Init.CounterMode       = TIM_COUNTERMODE_UP;
    htim1.Init.Period            = PWM_PERIOD;              /* 359 */
    htim1.Init.ClockDivision     = TIM_CLOCKDIVISION_DIV1;
    htim1.Init.RepetitionCounter = CTRL_DIVIDER - 1U;      /* 9 -> 20 kHz ISR */
    htim1.Init.AutoReloadPreload = TIM_AUTORELOAD_PRELOAD_ENABLE;
    HAL_TIM_PWM_Init(&htim1);

    TIM_OC_InitTypeDef oc = {0};
    oc.OCMode     = TIM_OCMODE_PWM1;
    oc.Pulse      = 0;
    oc.OCPolarity = TIM_OCPOLARITY_HIGH;
    oc.OCFastMode = TIM_OCFAST_DISABLE;
    HAL_TIM_PWM_ConfigChannel(&htim1, &oc, TIM_CHANNEL_1);

    /* Advanced-timer outputs need the main output enabled */
    __HAL_TIM_MOE_ENABLE(&htim1);

    HAL_NVIC_SetPriority(TIM1_UP_IRQn, 0, 0);
    HAL_NVIC_EnableIRQ(TIM1_UP_IRQn);
}

static void MX_TIM3_Init(void)
{
    /* Rotary encoder on TIM3 CH1/CH2 = PA6/PA7 (no remap needed). */
    __HAL_RCC_TIM3_CLK_ENABLE();
    __HAL_RCC_GPIOA_CLK_ENABLE();

    GPIO_InitTypeDef g = {0};
    g.Pin  = GPIO_PIN_6 | GPIO_PIN_7;
    g.Mode = GPIO_MODE_INPUT;
    g.Pull = GPIO_PULLUP;
    HAL_GPIO_Init(GPIOA, &g);

    htim3.Instance = TIM3;
    htim3.Init.Prescaler   = 0;
    htim3.Init.CounterMode = TIM_COUNTERMODE_UP;
    htim3.Init.Period      = 0xFFFF;
    htim3.Init.ClockDivision = TIM_CLOCKDIVISION_DIV1;

    TIM_Encoder_InitTypeDef enc = {0};
    enc.EncoderMode = TIM_ENCODERMODE_TI12;
    enc.IC1Polarity = TIM_ICPOLARITY_RISING;
    enc.IC1Selection= TIM_ICSELECTION_DIRECTTI;
    enc.IC1Prescaler= TIM_ICPSC_DIV1;
    enc.IC1Filter   = 6;
    enc.IC2Polarity = TIM_ICPOLARITY_RISING;
    enc.IC2Selection= TIM_ICSELECTION_DIRECTTI;
    enc.IC2Prescaler= TIM_ICPSC_DIV1;
    enc.IC2Filter   = 6;
    HAL_TIM_Encoder_Init(&htim3, &enc);
}

static void MX_TIM4_Init(void)
{
    /* Fan PWM on TIM4 CH4 = PB9. ~1 kHz. */
    __HAL_RCC_TIM4_CLK_ENABLE();
    __HAL_RCC_GPIOB_CLK_ENABLE();

    GPIO_InitTypeDef g = {0};
    g.Pin   = GPIO_PIN_9;
    g.Mode  = GPIO_MODE_AF_PP;
    g.Speed = GPIO_SPEED_FREQ_LOW;
    HAL_GPIO_Init(GPIOB, &g);

    htim4.Instance = TIM4;
    htim4.Init.Prescaler   = 71;           /* 72 MHz / 72 = 1 MHz */
    htim4.Init.CounterMode = TIM_COUNTERMODE_UP;
    htim4.Init.Period      = 999;          /* 1 MHz / 1000 = 1 kHz */
    htim4.Init.ClockDivision = TIM_CLOCKDIVISION_DIV1;
    HAL_TIM_PWM_Init(&htim4);

    TIM_OC_InitTypeDef oc = {0};
    oc.OCMode     = TIM_OCMODE_PWM1;
    oc.Pulse      = 0;
    oc.OCPolarity = TIM_OCPOLARITY_HIGH;
    HAL_TIM_PWM_ConfigChannel(&htim4, &oc, TIM_CHANNEL_4);
}

static void MX_USART1_Init(void)
{
    __HAL_RCC_USART1_CLK_ENABLE();
    __HAL_RCC_GPIOA_CLK_ENABLE();

    GPIO_InitTypeDef g = {0};
    g.Pin   = GPIO_PIN_9;                  /* PA9 = USART1_TX */
    g.Mode  = GPIO_MODE_AF_PP;
    g.Speed = GPIO_SPEED_FREQ_HIGH;
    HAL_GPIO_Init(GPIOA, &g);

    huart1.Instance          = USART1;
    huart1.Init.BaudRate     = 115200;
    huart1.Init.WordLength   = UART_WORDLENGTH_8B;
    huart1.Init.StopBits     = UART_STOPBITS_1;
    huart1.Init.Parity       = UART_PARITY_NONE;
    huart1.Init.Mode         = UART_MODE_TX_RX;
    huart1.Init.HwFlowCtl    = UART_HWCONTROL_NONE;
    huart1.Init.OverSampling = UART_OVERSAMPLING_16;
    HAL_UART_Init(&huart1);
}

static void MX_IWDG_Init(void)
{
    /* LSI 40 kHz / 64 = 625 Hz; reload 625 -> ~1 s timeout. A hung control
     * loop on a power converter must reset, not free-run. */
    hiwdg.Instance       = IWDG;
    hiwdg.Init.Prescaler = IWDG_PRESCALER_64;
    hiwdg.Init.Reload    = 625;
    HAL_IWDG_Init(&hiwdg);
}

/* TIM1 update IRQ -> HAL -> HAL_TIM_PeriodElapsedCallback */
void TIM1_UP_IRQHandler(void)   { HAL_TIM_IRQHandler(&htim1); }
/* INA226 ALERT -> HAL -> HAL_GPIO_EXTI_Callback */
void EXTI0_IRQHandler(void)     { HAL_GPIO_EXTI_IRQHandler(PIN_INA226_ALERT); }

void SysTick_Handler(void)      { HAL_IncTick(); }

void Error_Handler(void)        { __disable_irq(); while (1) { } }
