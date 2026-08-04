# Variable Switching DC Power Supply
### STM32-based Synchronous Buck Converter | 1.25–30V | 0–5A | >88% Efficiency (target)

![License](https://img.shields.io/badge/license-MIT-blue.svg)
![MCU](https://img.shields.io/badge/MCU-STM32F103C8T6-brightgreen)
![Topology](https://img.shields.io/badge/Topology-Synchronous%20Buck-orange)
![Status](https://img.shields.io/badge/results-simulated%20%2F%20target-yellow)

---

## Overview

A fully digital, high-efficiency bench power supply built around an STM32F103C8T6
and a synchronous buck converter. Mains AC is stepped down, rectified, and
regulated to an adjustable DC output by a software PID loop running at 50 µs
(20 kHz).

The repo covers the full engineering lifecycle: requirements, trade studies,
schematic and 4-layer PCB design, embedded firmware, worst-case analysis, and a
validation plan.

---
## Status of results (read first)
Performance figures in this repo are design targets backed by hand-calculation and SPICE simulation (see simulation/). Rows in the test procedure marked [PENDING] are awaiting bench measurement; drop measured values in as they are taken. Nothing here is claimed as hardware-verified until that column is filled. 

## Key Specifications (targets)

| Parameter | Value |
|---|---|
| AC Input | 220–240 V, 50/60 Hz |
| DC Output Voltage | 1.25 V – 30 V (adjustable) |
| DC Output Current | 0 – 5 A continuous |
| Switching Frequency | 200 kHz |
| Control-loop rate | 50 µs (20 kHz) |
| Output Ripple | < 30 mVpp (SPICE: 22.6 mVpp) |
| Load Regulation | ±0.5% (target) |
| Efficiency | > 88% at full load (target) |
| Display | 128×64 OLED (SSD1306, I2C) |
| Interface | Rotary encoder + push button |

---

## System Architecture

```
AC Mains (220–240V)
    ├── F1 (2A slow-blow) ── MOV (275V) ── L1 (CM choke) ── Cx (X2)
    ▼
T1 Step-Down Transformer (230V:32V, 250VA toroidal)   ← galvanic isolation (SELV)
    ▼
Bridge Rectifier (GBU806) ── Bulk Cap C1 (4700µF/63V) ── DC bus ~45V
    ▼
Synchronous Buck
    ├── Q1 IRF540N  (hi-side)      ├── L2 100µH (≥6.8A Isat)
    ├── Q2 IRF540N  (lo-side)      └── C2 470µF/50V
    └── IR2104 gate driver (single PWM in; makes HO/LO + internal dead-time)
    ▼
Regulated DC Output (1.25–30V, 0–5A)
    ├── Voltage sense → PA0  ADC1_IN0 (100k/12k divider)
    ├── Current sense → INA226 → I2C (PB6/PB7), ALERT → PB0
    └── Temp sense    → PA1  ADC1_IN1 (NTC 10kΩ)
    ▼
STM32F103C8T6  (PID loop, PWM, display, protection)
```

Gate drive uses a **single** STM32 PWM output to the IR2104 `IN` pin; the IR2104
generates the complementary high/low-side drive and its own dead-time. The STM32
does **not** produce a complementary pair — see `docs/design_review_findings.md`
(DR-1) for why the earlier complementary-PWM description was inconsistent with an
IR2104.

---

## Repository Structure

```
Variable-Switching-DC-Power-Supply/
├── README.md
├── LICENSE
├── CHANGES.md                       Corrections applied to this repo
├── docs/
│   ├── requirements.md              Numbered requirements + verification matrix
│   ├── trade_studies.md             Topology, control, sensing trade studies
│   ├── system_overview.md           Architecture & design decisions
│   ├── component_derating_wcca.md   Derating & worst-case analysis
│   ├── pid_control.md               PID theory, tuning, anti-windup
│   ├── pcb_design_rules.md          4-layer stackup, layout rules, EMC
│   ├── prototyping_guide.md         Staged, current-limited bring-up
│   ├── wiring_harness.md            Harness design (IPC/WHMA-A-620)
│   └── test_procedure.md            Validation checklist with pass criteria
├── simulation/
│   ├── buck_powerstage.cir          ngspice netlist (verified)
│   ├── Buck_Converter_Transient_Response.png
│   ├── Transient_Response_Data.xlsx
│   └── README.md
├── hardware/
│   ├── schematics/
│   │   ├── power_supply_circuit.png
│   │   └── README.md
│   ├── bom/BOM.csv
│   └── pcb/pcb_design_notes.md
└── firmware/
    ├── Core/
    │   ├── Src/  main.c  pid.c  adc.c  display.c  ina226.c
    │   └── Inc/  main.h  pid.h  adc.h  display.h  ina226.h
    └── README.md
```

---

## STM32 Pin Assignment

| Pin | Peripheral | Function |
|---|---|---|
| PA0 | ADC1_IN0 | Output voltage sense |
| PA1 | ADC1_IN1 | NTC temperature sense |
| PA4 | GPIO out | FAULT LED (red) |
| PA5 | GPIO in | Encoder push button |
| PA6 | TIM3_CH1 | Encoder A |
| PA7 | TIM3_CH2 | Encoder B |
| PA8 | TIM1_CH1 | 200 kHz PWM → IR2104 IN |
| PA9 | USART1_TX | Debug telemetry |
| PB0 | EXTI0 | INA226 ALERT (fast OCP) |
| PB6 | I2C1_SCL | INA226 + OLED |
| PB7 | I2C1_SDA | INA226 + OLED |
| PB9 | TIM4_CH4 | Fan PWM |
| PB12 | GPIO out | IR2104 /SD (shutdown) |
| PC13 | GPIO out | CV status LED |
| PC14 | GPIO out | CC status LED |

---

## PID Control Loop

TIM1 runs the 200 kHz switching PWM; its update interrupt is divided by the
repetition counter (RCR = 9) to fire the PID at 20 kHz (50 µs). This is what
makes the ADC-in-ISR budget viable — at the raw 200 kHz update rate a ~21 µs ADC
read would not fit.

```c
float error  = v_setpoint - ADC_ReadVoltage();
pid.integral = CLAMP(pid.integral + error, -MAX_INT, MAX_INT);
float duty   = Kp*error + Ki*pid.integral + Kd*(error - pid.prev_error);
__HAL_TIM_SET_COMPARE(&htim1, TIM_CHANNEL_1, (uint32_t)CLAMP(duty, 0, MAX_DUTY));
```

---

## Building the Firmware

- STM32CubeIDE 1.13 (or arm-none-eabi-gcc) with STM32CubeF1 HAL
- ST-Link V2 via SWD
- SSD1306 OLED library (afiskon/stm32-ssd1306) vendored or as a submodule

See `firmware/README.md` for the full build and dependency notes.

---

## License

MIT — see [LICENSE](LICENSE).

## Author

**Adnan Anwar Awan** — Electrical Engineer (PCB · Embedded · Power Electronics)
GitHub: [@AdnanAnwarAwan](https://github.com/AdnanAnwarAwan)
