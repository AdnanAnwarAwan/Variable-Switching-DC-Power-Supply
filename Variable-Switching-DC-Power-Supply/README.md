# Variable Switching DC Power Supply
### STM32-based Synchronous Buck Converter | 1.25–30V | 0–5A | >88% Efficiency (target)

![License](https://img.shields.io/badge/license-MIT-blue.svg)
![MCU](https://img.shields.io/badge/MCU-STM32F103C8T6-brightgreen)
![Topology](https://img.shields.io/badge/Topology-Synchronous%20Buck-orange)
![Status](https://img.shields.io/badge/results-simulated%20%2F%20target-yellow)

---

## Status of results (read first)

Performance figures in this repo are **design targets backed by hand-calculation
and SPICE simulation** (see `simulation/`). Rows in the test procedure marked
*[PENDING]* are awaiting bench measurement; drop measured values in as they are
taken. Nothing here is claimed as hardware-verified until that column is filled.
This keeps the documentation honest about what has and hasn't been proven on
metal. See `CHANGES.md` for the full list of corrections applied to this repo.

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

## Key Specifications (targets)

| Parameter | Value |
|---|---|
| AC Input | 220V to 240 V System Overview
Design Goals
Values below are targets; the "Status" column reflects analysis/simulation, not bench measurement, except where a measured figure has been recorded.
Goal	Target	Status
Output voltage range	1.25–30V	Met by design
Output current	0–5A	Met by design
Efficiency	>85%	SPICE/hand-calc ~89% (bench pending)
Ripple	<30mV	SPICE 22.6 mVpp (bench pending)
Regulation	±0.5%	Model prediction (bench pending)
Protection	OVP, OCP, thermal	Implemented in firmware + INA226 ALERT

Topology Selection — Why Synchronous Buck?
•	vs Linear regulator: a linear pass element dissipates (Vin−Vout)×I → well under 50% efficiency at these ratios. A buck switches energy → high efficiency.
•	vs Non-synchronous buck: a Schottky freewheel diode drops ~0.4 V. The IRF540N low-side FET (RDS(on) ≈ 44 mΩ) drops ≈ 44 mΩ × 5 A = 0.22 V at full load — roughly half the Schottky loss, so synchronous rectification saves on the order of ~1 W here. (An earlier draft cited 8 mΩ for this FET, which is wrong for an IRF540N; the real benefit is smaller than that implied. A modern low-RDS(on) FET would widen the gap — see trade study TS-4.)
•	vs SEPIC/flyback: buck is simpler for a single-rail output and easier EMC.
Signal Flow
AC → Fuse → MOV → CMC → Cx → Bridge → C1 bulk → DC bus ~45V
                                                      │
                                                Q1 (hi-side)
                                                      │  SW node
                                        L2 100µH ──────────── C2 ──── Vout
                                                      │
                                                Q2 (lo-side)
                                                      │
                                                     GND

STM32 PID (50µs): ADC(PA0) → error = Vset−Vmeas → PID → duty → TIM1 CH1
                  → IR2104 IN → (IR2104 makes HO/LO + dead-time) → Q1/Q2
Protection Architecture
Fault	Detection	Response	Firmware-independent?	Recovery
Over-voltage	Vout via ADC (firmware)	Assert /SD → IR2104 off	No (firmware path)	Auto when Vout drops
Over-current (fast)	INA226 ALERT pin threshold	EXTI → /SD low	Partly (see note)	Manual restart
Over-current (coarse)	INA226 I2C poll ~1 kHz	CC fold / shutdown	No	Soft restart
Short circuit	INA226 ALERT	Immediate PWM disable	Partly	Manual restart
Over-temperature	NTC 10kΩ + ADC	Fan ramp → shutdown >85°C	No	Auto after cooling
Input surge	MOV 275V clamp	Energy absorbed	Yes (passive)	Transparent

Note on PRT-5 (independent shutdown path): as wired, the INA226 ALERT pin goes to an MCU EXTI, so even the "fast" over-current path is firmware-mediated (ALERT → MCU → /SD). A genuinely firmware-independent trip requires wiring ALERT (or a dedicated comparator) directly to the IR2104 /SD pin in hardware. This is an open hardware item — see design_review_findings.md DR-3. The previous version of this document described OVP as an analog "comparator on Vout"; there is no comparator in the BOM, so that claim has been corrected to reflect the firmware-based detection that actually exists.

<img width="482" height="675" alt="image" src="https://github.com/user-attachments/assets/9509c8cf-d0d4-4485-ac06-283db0146c9b" />
System Overview
Design Goals
Values below are targets; the "Status" column reflects analysis/simulation, not bench measurement, except where a measured figure has been recorded.
Goal	Target	Status
Output voltage range	1.25–30V	Met by design
Output current	0–5A	Met by design
Efficiency	>85%	SPICE/hand-calc ~89% (bench pending)
Ripple	<30mV	SPICE 22.6 mVpp (bench pending)
Regulation	±0.5%	Model prediction (bench pending)
Protection	OVP, OCP, thermal	Implemented in firmware + INA226 ALERT

Topology Selection — Why Synchronous Buck?
•	vs Linear regulator: a linear pass element dissipates (Vin−Vout)×I → well under 50% efficiency at these ratios. A buck switches energy → high efficiency.
•	vs Non-synchronous buck: a Schottky freewheel diode drops ~0.4 V. The IRF540N low-side FET (RDS(on) ≈ 44 mΩ) drops ≈ 44 mΩ × 5 A = 0.22 V at full load — roughly half the Schottky loss, so synchronous rectification saves on the order of ~1 W here. (An earlier draft cited 8 mΩ for this FET, which is wrong for an IRF540N; the real benefit is smaller than that implied. A modern low-RDS(on) FET would widen the gap — see trade study TS-4.)
•	vs SEPIC/flyback: buck is simpler for a single-rail output and easier EMC.
Signal Flow
AC → Fuse → MOV → CMC → Cx → Bridge → C1 bulk → DC bus ~45V
                                                      │
                                                Q1 (hi-side)
                                                      │  SW node
                                        L2 100µH ──────────── C2 ──── Vout
                                                      │
                                                Q2 (lo-side)
                                                      │
                                                     GND

STM32 PID (50µs): ADC(PA0) → error = Vset−Vmeas → PID → duty → TIM1 CH1
                  → IR2104 IN → (IR2104 makes HO/LO + dead-time) → Q1/Q2
Protection Architecture
Fault	Detection	Response	Firmware-independent?	Recovery
Over-voltage	Vout via ADC (firmware)	Assert /SD → IR2104 off	No (firmware path)	Auto when Vout drops
Over-current (fast)	INA226 ALERT pin threshold	EXTI → /SD low	Partly (see note)	Manual restart
Over-current (coarse)	INA226 I2C poll ~1 kHz	CC fold / shutdown	No	Soft restart
Short circuit	INA226 ALERT	Immediate PWM disable	Partly	Manual restart
Over-temperature	NTC 10kΩ + ADC	Fan ramp → shutdown >85°C	No	Auto after cooling
Input surge	MOV 275V clamp	Energy absorbed	Yes (passive)	Transparent

Note on PRT-5 (independent shutdown path): as wired, the INA226 ALERT pin goes to an MCU EXTI, so even the "fast" over-current path is firmware-mediated (ALERT → MCU → /SD). A genuinely firmware-independent trip requires wiring ALERT (or a dedicated comparator) directly to the IR2104 /SD pin in hardware. This is an open hardware item — see design_review_findings.md DR-3. The previous version of this document described OVP as an analog "comparator on Vout"; there is no comparator in the BOM, so that claim has been corrected to reflect the firmware-based detection that actually exists.

<img width="482" height="675" alt="image" src="https://github.com/user-attachments/assets/fc2cbf39-4ad4-4939-aad5-d7f2eeb0c8bf" />
–240 V, 50/60 Hz |
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
AC Mains (90–240V)
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
│   ├── design_review_findings.md    Self-review: issues found + fixes
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
