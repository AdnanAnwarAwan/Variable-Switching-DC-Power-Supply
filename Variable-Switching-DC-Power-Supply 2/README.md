# Variable Switching DC Power Supply
### STM32-based Synchronous Buck Converter | 1.25–30V | 0–5A | >88% Efficiency

![License](https://img.shields.io/badge/license-MIT-blue.svg)
![MCU](https://img.shields.io/badge/MCU-STM32F103C8T6-brightgreen)
![Topology](https://img.shields.io/badge/Topology-Synchronous%20Buck-orange)
![Efficiency](https://img.shields.io/badge/Efficiency->88%25-success)

---

## Overview

A fully digital, high-efficiency bench power supply built from scratch using an STM32F103C8T6 microcontroller and a synchronous buck converter topology. The supply converts 90–240V AC mains to a stable, adjustable DC output regulated by a software PID control loop running at 50µs intervals.

This project covers the complete engineering lifecycle:
- **System architecture** and topology selection
- **Schematic design** — AC input protection, rectification, buck converter, sensing
- **PCB layout** — 4-layer stackup, EMC strategy, thermal management
- **Embedded firmware** — STM32 HAL, PID controller, ADC, I2C, PWM
- **Test and validation** — load regulation, ripple, efficiency, protection testing

---

## Key Specifications

| Parameter | Value |
|---|---|
| AC Input | 90–240V, 50/60Hz |
| DC Output Voltage | 1.25V – 30V (adjustable) |
| DC Output Current | 0 – 5A continuous |
| Switching Frequency | 200 kHz |
| Output Ripple | < 30mV peak-to-peak |
| Load Regulation | ±0.5% |
| Efficiency | > 88% at full load |
| PID Loop Rate | 50µs (20kHz) |
| Display | 128×64 OLED (SSD1306, I2C) |
| Interface | Rotary encoder + push button |

---

## System Architecture

```
AC Mains (230V)
    │
    ├── F1 (2A slow-blow fuse)
    ├── MOV (275V surge protection)
    ├── L1 (Common mode choke)
    ├── Cx (100nF X-capacitor)
    │
    ▼
T1 Step-Down Transformer (230V : 32V, 250VA toroidal)
    │         ← provides galvanic isolation from mains (SELV output)
    ▼
Bridge Rectifier (GBU806)
    │
    ▼
Bulk Capacitor C1 (4700µF / 50V)  ← DC bus ~45V  (32VAC × √2 ≈ 45V peak)
    │
    ▼
Buck Converter
    ├── Q1 IRF540N  (Hi-side MOSFET)
    ├── Q2 IRF540N  (Lo-side MOSFET)
    ├── IR2104      (Gate driver, dead-time insertion)
    ├── L2 100µH    (Power inductor)
    └── C2 470µF    (Output capacitor)
    │
    ▼
Regulated DC Output (1.25–30V, 0–5A)
    │
    ├── Voltage sense  → PA0 ADC1_IN0 (R-divider 100k/12k)
    ├── Current sense  → INA226 → I2C (PB6/PB7)
    └── Thermal sense  → PA1 ADC1_IN1 (NTC 10kΩ)
    │
    ▼
STM32F103C8T6 (PID control loop, PWM generation, display, protection)
```

---

## Repository Structure

```
Variable-Switching-DC-Power-Supply/
│
├── README.md
├── LICENSE
│
├── docs/
│   ├── requirements.md          Numbered requirements + verification matrix
│   ├── trade_studies.md         Topology, sensing, control trade studies
│   ├── system_overview.md       System architecture & design decisions
│   ├── component_derating_wcca.md  Derating analysis & worst-case notes
│   ├── pid_control.md           PID theory, tuning, and anti-windup
│   ├── pcb_design_rules.md      4-layer stackup, layout rules, EMC
│   ├── prototyping_guide.md     Staged prototyping & safe bring-up strategy
│   ├── wiring_harness.md        Harness design (IPC/WHMA-A-620 practices)
│   ├── design_review_findings.md  Self-review: known issues + corrective actions
│   ├── firefly_jd_mapping.md    Aerospace relevance & flight evolution path
│   └── test_procedure.md        Validation checklist with pass criteria
│
├── simulation/
│   ├── buck_powerstage.cir      ngspice netlist — verified, results in README
│   └── README.md                Simulation results & LTspice guidance
│
├── hardware/
│   ├── schematics/
│   │   └── power_supply_circuit.jpg    Complete circuit schematic
│   ├── bom/
│   │   └── BOM.csv                     Full bill of materials
│   └── pcb/
│       └── pcb_design_notes.md         Layer stackup & layout guidance
│
├── firmware/
│   ├── Core/
│   │   ├── Src/
│   │   │   ├── main.c           Main application loop
│   │   │   ├── pid.c            PID controller implementation
│   │   │   ├── adc.c            Voltage, current, temp sensing
│   │   │   └── display.c        SSD1306 OLED driver
│   │   └── Inc/
│   │       ├── pid.h
│   │       ├── adc.h
│   │       └── display.h
│   └── README.md                Firmware build instructions
│
└── presentation/
    └── README.md                Link to project presentation
```

---

## Hardware — Key Components

| Component | Part Number | Purpose |
|---|---|---|
| Microcontroller | STM32F103C8T6 | Main control, PWM, ADC, I2C |
| Hi-side MOSFET | IRF540N | Primary switching element |
| Lo-side MOSFET | IRF540N | Synchronous rectification |
| Gate Driver | IR2104 | Half-bridge driver with dead-time |
| Current Sensor | INA226 | 16-bit I2C current/power monitor |
| Bridge Rectifier | GBU806 | Full-wave AC rectification |
| Bulk Capacitor | 4700µF / 50V | DC bus energy storage |
| Inductor | 100µH / 5A | Buck converter LC filter |
| Output Capacitor | 470µF + 100nF | Output ripple filtering |
| Display | SSD1306 | 128×64 OLED, I2C addr 0x3C |
| Encoder | EC11 | Rotary encoder + push button |
| LDO Regulator | AMS1117-3.3 | 5V → 3.3V for STM32 |

---

## Firmware Overview

### STM32 Pin Assignment

| Pin | Peripheral | Function |
|---|---|---|
| PA0 | ADC1_IN0 | Output voltage sense |
| PA1 | ADC1_IN1 | NTC temperature sense |
| PA8 | GPIO out | FAULT shutdown signal |
| PA9 | USART1_TX | Debug serial output |
| PB0 | ADC2_IN8 | INA226 ALERT interrupt |
| PB1 | TIM3_CH4 | Fan PWM control |
| PB6 | I2C1_SCL | INA226 + OLED clock |
| PB7 | I2C1_SDA | INA226 + OLED data |
| TIM1_CH1 | Advanced timer | Hi-side PWM output |
| TIM1_CH1N | Advanced timer | Lo-side PWM (complementary) |
| TIM2_CH1/2 | Encoder mode | Rotary encoder A/B |

### PID Control Loop

The PID runs inside the TIM1 update interrupt service routine at 50µs intervals:

```c
float error      = v_setpoint - read_adc_voltage();
pid.integral     = CLAMP(pid.integral + error, -MAX_INT, MAX_INT);
float derivative = error - pid.prev_error;
pid.prev_error   = error;
float duty       = Kp*error + Ki*pid.integral + Kd*derivative;
__HAL_TIM_SET_COMPARE(&htim1, TIM_CHANNEL_1, (uint32_t)CLAMP(duty, 0, MAX_DUTY));
```

---

## PCB Design — 4-Layer Stackup

| Layer | Purpose |
|---|---|
| Top | Signal routing, MCU, control components |
| L2 | Solid ground plane |
| L3 | Power plane |
| Bottom | Power MOSFETs, heatsink copper, high-current traces |

### Critical Layout Rules
- Switching loop (Q1 → L2 → C2 → GND) area minimised
- Minimum 2mm trace width per amp of current
- Thermal vias under MOSFETs to bottom copper pour
- Single star ground point — analog, digital, power GND
- ADC input traces shielded from switching node
- 100nF decoupling cap within 3mm of every VDD pin

---

## Test & Validation

| Test | Procedure | Pass Criterion |
|---|---|---|
| Power-on | Check 3.3V and 5V rails with DMM | ±5% of nominal |
| PWM | Oscilloscope on gate signals | 200kHz, 200ns dead-time |
| Load regulation | Sweep 0→5A, measure Vout | ±0.5% deviation |
| Ripple | AC-couple scope on Vout | < 30mV peak-to-peak |
| Efficiency | Pin vs Pout at 25/50/75/100% load | > 88% at full load |
| Thermal | Full load 30 min, IR camera | < 85°C junction temp |
| Protection | Trigger OVP, OCP, short circuit | Shutdown + recovery |

---

## Building the Firmware

Requirements:
- STM32CubeIDE or arm-none-eabi-gcc toolchain
- STM32 HAL libraries (CubeMX generated)
- ST-Link V2 or SWD programmer

```bash
git clone https://github.com/AdnanAnwarAwan/Variable-Switching-DC-Power-Supply.git
cd Variable-Switching-DC-Power-Supply/firmware
# Open in STM32CubeIDE or build with Makefile
```

---


## License

MIT License — see [LICENSE](LICENSE) for details.

---

## Author

**Adnan Anwar Awan**
Electrical Engineer — PCB Design | Embedded Firmware | Power Electronics
GitHub: [@AdnanAnwarAwan](https://github.com/AdnanAnwarAwan)
