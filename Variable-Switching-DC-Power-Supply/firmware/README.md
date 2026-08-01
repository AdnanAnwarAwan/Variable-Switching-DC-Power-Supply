# Firmware

STM32F103C8T6 @ 72 MHz. Application code lives in `Core/Src` and `Core/Inc`.

## Toolchain
- STM32CubeIDE 1.13 (or arm-none-eabi-gcc + Makefile)
- STM32CubeF1 HAL v1.8.x
- ST-Link V2 via SWD (SWDIO = PA13, SWDCLK = PA14)
- Flash: 64 KB; application ~32 KB

## Key tuning parameters (main.c)

| Constant | Default | Effect |
|---|---|---|
| `SWITCHING_FREQ_HZ` | 200000 | PWM frequency |
| `CTRL_DIVIDER` | 10 | RCR+1; sets the 20 kHz control-ISR rate |
| `SOFTSTART_STEPS` | 100 | 100 × 50 µs = 5 ms ramp |
| `FAN_ON_TEMP_C` | 50.0 | Fan start temperature |
| `SHUTDOWN_TEMP_C` | 85.0 | Thermal shutdown |
| `I_ALERT_AMPS` | 5.5 | INA226 hardware over-current trip |
| PID `Kp` / `Ki` / `Kd` | 0.8 / 0.02 / 0.001 | Loop gains |

## Calibration (required for PER-3)

Set `VCAL_GAIN` / `VCAL_OFFSET` in `Core/Inc/adc.h` from a one-time bench
calibration against a reference DMM. Uncalibrated divider tolerance (~±1.8%)
fails the ±0.5% setpoint spec.

## PID tuning guide
1. Ki = 0, Kd = 0; raise Kp until the output oscillates.
2. Set Kp to ~50% of the oscillation value.
3. Raise Ki until steady-state error is gone.
4. Add small Kd to damp overshoot on load steps.
5. Verify a 0 → 5 A step settles < 1 ms.

## Debug output (USART1, 115200 8N1)
```
Variable Switching DC PSU - Adnan Anwar Awan
Vset=12.00 Vout=11.97 Iout=1.85 T=42.3C [CV]
```
