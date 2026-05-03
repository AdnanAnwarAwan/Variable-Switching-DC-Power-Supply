#ifndef PID_H
#define PID_H

#include <stdint.h>

/* PID controller state */
typedef struct {
    float Kp;           /* Proportional gain */
    float Ki;           /* Integral gain     */
    float Kd;           /* Derivative gain   */
    float integral;     /* Accumulated integral */
    float prev_error;   /* Previous error for derivative */
    float out_min;      /* Output clamp minimum */
    float out_max;      /* Output clamp maximum */
    float int_max;      /* Anti-windup integral clamp */
} PID_t;

/* Initialise PID with gains and limits */
void  PID_Init(PID_t *pid, float Kp, float Ki, float Kd,
               float out_min, float out_max, float int_max);

/* Run one PID iteration — returns duty cycle output */
float PID_Update(PID_t *pid, float setpoint, float measured);

/* Reset integrator and derivative state */
void  PID_Reset(PID_t *pid);

#endif /* PID_H */
