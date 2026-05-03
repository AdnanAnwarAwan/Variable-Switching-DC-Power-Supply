/**
 * @file    pid.c
 * @brief   PID controller implementation for voltage regulation
 *          Runs in TIM1 update ISR at 50µs (20kHz) rate
 *
 * @author  Adnan Anwar Awan
 */

#include "pid.h"
#include <math.h>

/* Clamp helper macro */
#define CLAMP(x, lo, hi) ((x) < (lo) ? (lo) : ((x) > (hi) ? (hi) : (x)))

/**
 * @brief Initialise PID controller with gains and output limits
 */
void PID_Init(PID_t *pid, float Kp, float Ki, float Kd,
              float out_min, float out_max, float int_max)
{
    pid->Kp         = Kp;
    pid->Ki         = Ki;
    pid->Kd         = Kd;
    pid->out_min    = out_min;
    pid->out_max    = out_max;
    pid->int_max    = int_max;
    pid->integral   = 0.0f;
    pid->prev_error = 0.0f;
}

/**
 * @brief  Compute one PID iteration
 * @param  pid       Pointer to PID state struct
 * @param  setpoint  Target voltage (V)
 * @param  measured  Measured output voltage (V)
 * @return Duty cycle value (0 to TIM1 period count)
 */
float PID_Update(PID_t *pid, float setpoint, float measured)
{
    /* Compute error */
    float error = setpoint - measured;

    /* Proportional term */
    float p_term = pid->Kp * error;

    /* Integral term with anti-windup clamping */
    pid->integral += error;
    pid->integral  = CLAMP(pid->integral, -pid->int_max, pid->int_max);
    float i_term   = pid->Ki * pid->integral;

    /* Derivative term (on measurement, not error — avoids derivative kick) */
    float derivative = error - pid->prev_error;
    float d_term     = pid->Kd * derivative;
    pid->prev_error  = error;

    /* Sum and clamp output */
    float output = p_term + i_term + d_term;
    return CLAMP(output, pid->out_min, pid->out_max);
}

/**
 * @brief Reset integrator and derivative state (e.g. on enable/disable)
 */
void PID_Reset(PID_t *pid)
{
    pid->integral   = 0.0f;
    pid->prev_error = 0.0f;
}
