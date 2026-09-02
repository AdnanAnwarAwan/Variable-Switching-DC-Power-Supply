/**
 * @file    telemetry.h
 * @brief   CSV telemetry transmitter and UART command parser for the
 *          Variable Switching DC Power Supply.
 *
 *  WHY THIS FILE EXISTS
 *  --------------------
 *  docs/Python_Code_Descriptions.pdf (Block 8) specifies a CSV telemetry
 *  line and a Python harness that parses it. The firmware in main.c prints
 *  a human-readable line instead:
 *
 *      Vset=12.00 Vout=11.98 Iout=2.50 T=41.2C [CV]
 *
 *  The documented Python parser splits on ',' and requires six fields, so
 *  against that line it matches nothing and silently records no telemetry
 *  at all. This module emits the documented format instead:
 *
 *      Vset,Vmeas,Imeas,Duty,Temp,Status
 *
 *  It also adds the UART receive path the harness needs for automated
 *  protection tests. main.c initialises USART1 in TX_RX mode but never
 *  configures PA10 as an input and never reads RX, so commands sent to the
 *  board today are discarded.
 *
 *  INTEGRATION (three edits to main.c)
 *  -----------------------------------
 *    1. #include "telemetry.h"
 *    2. In main(), after MX_USART1_Init():   Telemetry_Init();
 *    3. Replace the printf() in the 10 Hz display block with:
 *           Telemetry_Send();
 *           Telemetry_Poll();
 *
 *  MX_USART1_Init() must also configure PA10 as USART1_RX (input floating)
 *  and enable the USART1 interrupt; see telemetry.c for the exact code.
 *
 * @note  Telemetry_Send() uses printf, which blocks on HAL_UART_Transmit.
 *        At 115200 baud a ~45 character line takes about 3.9 ms. That is
 *        fine in the 10 Hz main-loop slot and would be catastrophic in the
 *        50 us PID ISR. Never call it from the ISR.
 */
#ifndef TELEMETRY_H
#define TELEMETRY_H

#include <stdint.h>

/** Snapshot of controller state supplied by the application each cycle. */
typedef struct {
    float   v_setpoint;   /**< Commanded output voltage, V            */
    float   v_measured;   /**< ADC-measured output voltage, V         */
    float   i_measured;   /**< INA226 output current, A               */
    float   duty_percent; /**< Active PWM duty cycle, 0-100 %         */
    float   temp_c;       /**< NTC temperature, degrees C             */
    uint8_t fault_active; /**< Non-zero once a protection event fired */
} Telemetry_State_t;

/** Command callbacks the parser invokes. Any may be NULL. */
typedef struct {
    void (*set_voltage)(float volts);   /**< "SETV <v>"      */
    void (*set_current)(float amps);    /**< "SETI <a>"      */
    void (*clear_fault)(void);          /**< "CLEARFAULT"    */
    void (*request_id)(void);           /**< "*IDN?"         */
} Telemetry_Commands_t;

/** Enable USART1 RX interrupt reception. Call once after MX_USART1_Init(). */
void Telemetry_Init(void);

/** Register command callbacks. Pass NULL to make the link receive-only. */
void Telemetry_SetCommands(const Telemetry_Commands_t *cmds);

/**
 * Emit one CSV line: Vset,Vmeas,Imeas,Duty,Temp,Status
 * Call at about 10 Hz from the main loop. Never from an ISR.
 */
void Telemetry_Send(const Telemetry_State_t *state);

/**
 * Process any complete command line received since the last call.
 * Call from the main loop alongside Telemetry_Send().
 */
void Telemetry_Poll(void);

/** Feed one received byte. Called from the USART1 IRQ handler. */
void Telemetry_RxByte(uint8_t byte);

#endif /* TELEMETRY_H */
