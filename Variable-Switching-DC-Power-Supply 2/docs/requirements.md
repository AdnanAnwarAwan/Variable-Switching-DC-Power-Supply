# Requirements Specification

Requirements were captured **before** topology selection. Each requirement has an ID,
a quantified value, and a verification method — every "shall" is tested in
[`test_procedure.md`](test_procedure.md). This document is the contract the design
is verified against.

## Functional Requirements

| ID | Requirement | Value | Verification |
|---|---|---|---|
| FUN-1 | Output voltage shall be adjustable | 1.25 – 30 V, 0.1 V steps | Test §4 |
| FUN-2 | Output current capability | 0 – 5 A continuous | Test §5 |
| FUN-3 | Operating mode | CV with automatic CC limiting | Test §9 |
| FUN-4 | User interface | Local set (encoder) + live V/I/T display | Inspection |

## Performance Requirements

| ID | Requirement | Value | Verification |
|---|---|---|---|
| PER-1 | Output ripple | < 30 mVpp, 20 MHz BW, full load | Test §6 |
| PER-2 | Load regulation | ±0.5 % (no-load → full-load) | Test §5 |
| PER-3 | Setpoint accuracy | ±0.5 % of setting | Test §4 |
| PER-4 | Efficiency | > 85 % at full load (achieved > 88 %) | Test §7 |
| PER-5 | Load-step recovery | < 1 ms settle, 0→5 A step | Test §5 |
| PER-6 | Control loop rate | 20 kHz (50 µs), no ISR overrun | Scope on GPIO toggle |

## Interface Requirements

| ID | Requirement | Value | Verification |
|---|---|---|---|
| INT-1 | AC input | 90–240 V, 50/60 Hz, IEC inlet | Inspection |
| INT-2 | Mains isolation | Galvanic (transformer T1), SELV output | Hipot / continuity |
| INT-3 | DC output | Screw terminals, 5 A rated | Inspection |
| INT-4 | Debug | USART1 115200 telemetry + SWD | Test §2 |

## Protection Requirements

| ID | Requirement | Value | Verification |
|---|---|---|---|
| PRT-1 | Over-voltage protection | Hardware shutdown < 100 µs | Test §9 |
| PRT-2 | Over-current protection | CC fold at limit; hard trip at limit +0.5 A | Test §9 |
| PRT-3 | Short-circuit | Immediate PWM kill via INA226 ALERT (hardware path) | Test §9 |
| PRT-4 | Over-temperature | Fan @ 50 °C, shutdown @ 85 °C | Test §8 |
| PRT-5 | Protection independence | At least one shutdown path shall not depend on firmware (IR2104 SD pin) | Design review |
| PRT-6 | Watchdog | MCU hang shall force reset + soft restart within 1 s | Fault injection |

## Environmental / Safety Requirements

| ID | Requirement | Value | Verification |
|---|---|---|---|
| ENV-1 | Thermal | MOSFET case < 85 °C after 30 min full load | Test §8 |
| ENV-2 | Creepage/clearance | 4.0 mm / 2.0 mm mains-to-SELV (IEC 60950 basis) | Layout DRC |
| ENV-3 | Component derating | Per [`component_derating_wcca.md`](component_derating_wcca.md) | Analysis |

## Requirement-writing rules used here (interview talking point)

1. Every requirement is **quantified** — "low ripple" is not a requirement, "< 30 mVpp at 20 MHz BW" is.
2. Every requirement names its **verification method** (test, analysis, inspection, demonstration).
3. Requirements state **what**, never **how** — topology (buck) appears in the trade study, not here.
4. Protection requirements demand a **non-software path** (PRT-5) — the same philosophy avionics standards require.
