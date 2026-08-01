/**
 * @file    main.h
 * @brief   Shared declarations for the Variable Switching DC Power Supply.
 *
 *          STM32F103C8T6 @ 72 MHz. Peripheral handles are defined once in
 *          main.c and declared extern here so drivers can reach them.
 *
 *  NOTE ON PIN CHANGES: the original pin map double-assigned PA8 (PWM AND
 *  shutdown) and PA0/PA1 (ADC AND TIM2 encoder). Both are electrically
 *  impossible. This map resolves them — see docs/design_review_findings.md
 *  (DR-1, DR-2). Verify against your physical board before flashing.
 *
 * @author  Adnan Anwar Awan
 */
#ifndef MAIN_H
#define MAIN_H

#include "stm32f1xx_hal.h"

/* ── Shared HAL handles (defined in main.c) ── */
extern ADC_HandleTypeDef  hadc1;
extern I2C_HandleTypeDef  hi2c1;
extern TIM_HandleTypeDef  htim1;   /* Single-channel 200 kHz PWM -> IR2104 IN */
extern TIM_HandleTypeDef  htim3;   /* Rotary encoder input                    */
extern TIM_HandleTypeDef  htim4;   /* Fan PWM                                  */
extern UART_HandleTypeDef huart1;  /* Debug telemetry                         */
extern IWDG_HandleTypeDef hiwdg;   /* Independent watchdog                     */

/* ── Pin map (single source of truth — keep README in sync) ──
 *  PA0   ADC1_IN0    Output voltage sense (100k/12k divider)
 *  PA1   ADC1_IN1    NTC temperature sense (10k NTC / 10k series)
 *  PA4   GPIO out    FAULT LED (red)
 *  PA5   GPIO in     Encoder push button (pull-up)
 *  PA6   TIM3_CH1    Encoder A
 *  PA7   TIM3_CH2    Encoder B
 *  PA8   TIM1_CH1    200 kHz PWM -> IR2104 IN (driver makes HO/LO + dead-time)
 *  PA9   USART1_TX   Debug telemetry, 115200 8N1
 *  PB0   EXTI0       INA226 ALERT (fast over-current, hardware threshold)
 *  PB6   I2C1_SCL    INA226 + SSD1306
 *  PB7   I2C1_SDA    INA226 + SSD1306
 *  PB9   TIM4_CH4    Fan PWM
 *  PB12  GPIO out    IR2104 /SD (active-low shutdown; HIGH = enabled)
 *  PC13  GPIO out    CV status LED (green)
 *  PC14  GPIO out    CC status LED (amber)
 */
#define PORT_FAULT_LED    GPIOA
#define PIN_FAULT_LED     GPIO_PIN_4
#define PORT_ENC_BTN      GPIOA
#define PIN_ENC_BTN       GPIO_PIN_5
#define PORT_IR2104_SD    GPIOB
#define PIN_IR2104_SD     GPIO_PIN_12   /* active low = shutdown */
#define PORT_ALERT        GPIOB
#define PIN_INA226_ALERT  GPIO_PIN_0    /* EXTI0 */
#define PORT_CV_LED       GPIOC
#define PIN_CV_LED        GPIO_PIN_13
#define PORT_CC_LED       GPIOC
#define PIN_CC_LED        GPIO_PIN_14

#endif /* MAIN_H */
