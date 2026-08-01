# Firmware

STM32F103C8T6 @ 72 MHz. Application code lives in `Core/Src` and `Core/Inc`.

## What's in the repo vs. what you regenerate

This repo contains the **application layer** (fully implemented, no stubs):
`main.c`, `pid.c`, `adc.c`, `display.c`, `ina226.c` and their headers. The
peripheral init functions in `main.c` are hand-maintained equivalents of the
CubeMX output so the project reads as a complete, coherent program.

To **build**, add the standard STM32 project scaffolding (not committed here to
avoid vendoring ST's libraries):
1. Create an STM32CubeMX project for the STM32F103C8T6, or drop in your own
   `.ioc`, and let it generate `Drivers/` (STM32F1 HAL + CMSIS), the startup
   `.s`, the linker `.ld`, and `system_stm32f1xx.c`.
2. Replace the generated `Core/Src` / `Core/Inc` with the files from this repo
   (or merge — the pin map in `main.h` matches the intended `.ioc`).
3. Add the SSD1306 OLED library (afiskon/stm32-ssd1306) under `Drivers/` or as a
   git submodule; `display.c` includes `ssd1306.h` / `ssd1306_fonts.h`.

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

Dead-time is **not** an STM32 parameter here — the IR2104 inserts it internally
(~520 ns typ). The STM32 emits a single PWM to the IR2104 `IN` pin.

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
