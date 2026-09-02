/**
 * @file    telemetry.c
 * @brief   CSV telemetry transmitter and UART command parser.
 *
 *          See telemetry.h for why this replaces the printf() in main.c.
 *
 * @author  Adnan Anwar Awan
 */
#include "telemetry.h"
#include "main.h"

#include <stdio.h>
#include <stdlib.h>
#include <string.h>

/* ── RX ring buffer ────────────────────────────────────────────────────
 * Sized for the longest command plus slack. A ring buffer written by the
 * IRQ and drained by the main loop keeps the ISR to a single store, which
 * matters: this MCU is already spending 21 us of every 50 us slot in the
 * ADC read.
 */
#define RX_BUF_SIZE   64U
#define CMD_MAX_LEN   32U

static volatile uint8_t  rx_buf[RX_BUF_SIZE];
static volatile uint16_t rx_head = 0;   /* written by IRQ  */
static volatile uint16_t rx_tail = 0;   /* read by main    */
static uint8_t           rx_byte;       /* HAL landing pad */

static char    cmd_line[CMD_MAX_LEN];
static uint8_t cmd_len = 0;

static const Telemetry_Commands_t *g_cmds = NULL;

/* ── init ──────────────────────────────────────────────────────────────
 * PA10 must be configured as USART1_RX before this is useful. main.c's
 * MX_USART1_Init() currently sets up PA9 only, so add:
 *
 *     g.Pin  = GPIO_PIN_10;
 *     g.Mode = GPIO_MODE_INPUT;
 *     g.Pull = GPIO_NOPULL;
 *     HAL_GPIO_Init(GPIOA, &g);
 *
 *     HAL_NVIC_SetPriority(USART1_IRQn, 6, 0);
 *     HAL_NVIC_EnableIRQ(USART1_IRQn);
 *
 * Priority 6 keeps it below the TIM1 PID interrupt. A UART byte must never
 * delay the control loop.
 */
void Telemetry_Init(void)
{
    rx_head = rx_tail = 0;
    cmd_len = 0;
    HAL_UART_Receive_IT(&huart1, &rx_byte, 1);
}

void Telemetry_SetCommands(const Telemetry_Commands_t *cmds)
{
    g_cmds = cmds;
}

/* ── TX ────────────────────────────────────────────────────────────────
 * Format matches docs/Python_Code_Descriptions.pdf Block 8 exactly:
 *     Vset,Vmeas,Imeas,Duty,Temp,Status
 *
 * NOTE: newlib's printf pulls in a large float-formatting path. If flash on
 * the F103C8 (64 kB) gets tight, replace with a fixed-point formatter —
 * multiply by 1000 and print integers. The Python parser handles either,
 * since it parses floats from text.
 */
void Telemetry_Send(const Telemetry_State_t *state)
{
    if (state == NULL) {
        return;
    }
    printf("%.3f,%.3f,%.3f,%.2f,%.1f,%s\r\n",
           state->v_setpoint,
           state->v_measured,
           state->i_measured,
           state->duty_percent,
           state->temp_c,
           state->fault_active ? "FAULT" : "OK");
}

/* ── RX ────────────────────────────────────────────────────────────── */
void Telemetry_RxByte(uint8_t byte)
{
    uint16_t next = (uint16_t)((rx_head + 1U) % RX_BUF_SIZE);
    if (next != rx_tail) {          /* drop on overflow, never block */
        rx_buf[rx_head] = byte;
        rx_head = next;
    }
}

/* HAL callback — wire this up by leaving HAL_UART_Receive_IT re-armed. */
void HAL_UART_RxCpltCallback(UART_HandleTypeDef *huart)
{
    if (huart->Instance == USART1) {
        Telemetry_RxByte(rx_byte);
        HAL_UART_Receive_IT(&huart1, &rx_byte, 1);
    }
}

static void Telemetry_Execute(const char *line)
{
    if (g_cmds == NULL) {
        return;
    }

    if (strncmp(line, "SETV ", 5) == 0) {
        if (g_cmds->set_voltage) {
            g_cmds->set_voltage(strtof(line + 5, NULL));
        }
    } else if (strncmp(line, "SETI ", 5) == 0) {
        if (g_cmds->set_current) {
            g_cmds->set_current(strtof(line + 5, NULL));
        }
    } else if (strcmp(line, "CLEARFAULT") == 0) {
        if (g_cmds->clear_fault) {
            g_cmds->clear_fault();
        }
    } else if (strcmp(line, "*IDN?") == 0) {
        printf("Variable Switching DC PSU,STM32F103C8T6,0001,1.0\r\n");
    }
    /* Unknown commands are ignored deliberately. A power converter should
     * not change behaviour because of line noise on a debug UART. */
}

void Telemetry_Poll(void)
{
    while (rx_tail != rx_head) {
        char c = (char)rx_buf[rx_tail];
        rx_tail = (uint16_t)((rx_tail + 1U) % RX_BUF_SIZE);

        if (c == '\n' || c == '\r') {
            if (cmd_len > 0U) {
                cmd_line[cmd_len] = '\0';
                Telemetry_Execute(cmd_line);
                cmd_len = 0U;
            }
        } else if (cmd_len < (CMD_MAX_LEN - 1U)) {
            cmd_line[cmd_len++] = c;
        } else {
            cmd_len = 0U;    /* overlong line: discard rather than truncate */
        }
    }
}

/* ──────────────────────────────────────────────────────────────────────
 * REFERENCE INTEGRATION for main.c
 * ──────────────────────────────────────────────────────────────────────
 *
 * The harness's OVP procedure also needs an over-voltage check, which the
 * current firmware does not have anywhere. Fault_Shutdown() is reached only
 * from over-current and over-temperature. Add to the TIM1 PID ISR, right
 * after v_measured is read:
 *
 *     if (v_measured > OVP_THRESHOLD_V) {
 *         Fault_Shutdown("OVER VOLTAGE");
 *         return;
 *     }
 *
 * with #define OVP_THRESHOLD_V 32.0f alongside the other limits. Note this
 * gives a firmware-mediated trip of roughly one control period (50 us),
 * which does NOT meet the "< 20 us" requirement in the Testing & Validation
 * Framework Phase 6 table. Meeting 20 us requires either a hardware
 * comparator driving IR2104 /SD directly, or a fast analogue watchdog on
 * the ADC. Decide which before writing that number into a test report.
 *
 * Command callbacks, in main.c:
 *
 *     static void Cmd_SetVoltage(float v) {
 *         if (v < V_MIN || v > V_MAX) { return; }
 *         v_setpoint = v;
 *         ss_count = 0;
 *         PID_Reset(&vpid);
 *     }
 *     static void Cmd_SetCurrent(float a) {
 *         if (a > 0.0f && a <= I_LIMIT_DEFAULT) { i_limit = a; }
 *     }
 *     static void Cmd_ClearFault(void) {
 *         fault_active = 0;
 *         HAL_GPIO_WritePin(PORT_FAULT_LED, PIN_FAULT_LED, GPIO_PIN_RESET);
 *         HAL_GPIO_WritePin(PORT_IR2104_SD, PIN_IR2104_SD, GPIO_PIN_SET);
 *         PID_Reset(&vpid);
 *         ss_count = 0;
 *         HAL_TIM_PWM_Start(&htim1, TIM_CHANNEL_1);
 *     }
 *
 *     static const Telemetry_Commands_t tcmds = {
 *         .set_voltage = Cmd_SetVoltage,
 *         .set_current = Cmd_SetCurrent,
 *         .clear_fault = Cmd_ClearFault,
 *         .request_id  = NULL,
 *     };
 *
 * and in the 10 Hz block, replacing the existing printf:
 *
 *     Telemetry_State_t st = {
 *         .v_setpoint   = v_setpoint,
 *         .v_measured   = v_measured,
 *         .i_measured   = i_measured,
 *         .duty_percent = (float)__HAL_TIM_GET_COMPARE(&htim1, TIM_CHANNEL_1)
 *                         * 100.0f / (float)PWM_PERIOD,
 *         .temp_c       = temp_c,
 *         .fault_active = fault_active,
 *     };
 *     Telemetry_Send(&st);
 *     Telemetry_Poll();
 *
 * SAFETY NOTE ON Cmd_ClearFault: re-enabling the converter over a debug
 * UART, remotely, with no confirmation, is a real hazard on a 45 V bus. It
 * exists so the automated protection suite can run 5-10 fault cycles
 * unattended per the framework document. Gate it behind a compile-time
 * TEST_BUILD flag and leave it out of any firmware that ships.
 */
