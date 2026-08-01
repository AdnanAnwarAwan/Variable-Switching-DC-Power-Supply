# PID Control Loop

## Theory

```
error(t)  = Vsetpoint − Vmeasured(t)
u(t)      = Kp·error(t) + Ki·∫error(t)dt + Kd·d(error)/dt
```

u(t) is the duty cycle value written to TIM1 CCR1.

## Loop rate

TIM1 generates the 200 kHz switching PWM. Its update interrupt is divided by the
repetition counter (RCR = 9) so the PID ISR fires once every 10 switching periods
= **20 kHz (50 µs)**. Without the RCR divider the update ISR would run at 200 kHz
(5 µs), which cannot host the ~21 µs ADC read — so the divider is load-bearing,
not cosmetic.

## Implementation (50µs ISR)

```c
void HAL_TIM_PeriodElapsedCallback(TIM_HandleTypeDef *htim) {
    if (htim->Instance == TIM1) {
        float v_meas = ADC_ReadVoltage();
        float duty   = PID_Update(&vpid, v_setpoint, v_meas);
        __HAL_TIM_SET_COMPARE(&htim1, TIM_CHANNEL_1, (uint32_t)duty);
    }
}
```

## Tuning Values

| Parameter | Value | Notes |
|---|---|---|
| Kp | 0.8 | Fast proportional response |
| Ki | 0.02 | Eliminates steady-state error |
| Kd | 0.001 | Dampens overshoot |
| Sample rate | 50µs | 20kHz loop rate |
| Max integral | ±500 | Anti-windup clamp |

## Anti-Windup

```c
pid->integral += error;
if (pid->integral >  MAX_INTEGRAL) pid->integral =  MAX_INTEGRAL;
if (pid->integral < -MAX_INTEGRAL) pid->integral = -MAX_INTEGRAL;
```

## Soft-Start

```c
static uint32_t ss_count = 0;
if (ss_count < SOFTSTART_STEPS) {
    duty = (duty * ss_count) / SOFTSTART_STEPS;
    ss_count++;
}
```

## Performance Results

| Metric | Result |
|---|---|
| Steady-state error | < ±10mV |
| Load step response | < 1ms settle |
| Loop bandwidth | ~2kHz |
