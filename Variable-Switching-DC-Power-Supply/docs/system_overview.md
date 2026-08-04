# System Overview

## Design Goals

Values below are **targets**; the "Status" column reflects analysis/simulation,
not bench measurement, except where a measured figure has been recorded.

| Goal | Target | Status |
|---|---|---|
| Output voltage range | 1.25–30V | Met by design |
| Output current | 0–5A | Met by design |
| Efficiency | >85% | SPICE/hand-calc ~89% (bench pending) |
| Ripple | <30mV | SPICE 22.6 mVpp (bench pending) |
| Regulation | ±0.5% | Model prediction (bench pending) |
| Protection | OVP, OCP, thermal | Implemented in firmware + INA226 ALERT |

## Topology Selection — Why Synchronous Buck?

- **vs Linear regulator:** a linear pass element dissipates (Vin−Vout)×I → well
  under 50% efficiency at these ratios. A buck switches energy → high efficiency.
- **vs Non-synchronous buck:** a Schottky freewheel diode drops ~0.4 V. The
  IRF540N low-side FET (RDS(on) ≈ 44 mΩ) drops ≈ 44 mΩ × 5 A = 0.22 V at full
  load — roughly half the Schottky loss, so synchronous rectification saves on
  the order of ~1 W here. (An earlier draft cited 8 mΩ for this FET, which is
  wrong for an IRF540N; the real benefit is smaller than that implied. A modern
  low-RDS(on) FET would widen the gap — see trade study TS-4.)
- **vs SEPIC/flyback:** buck is simpler for a single-rail output and easier EMC.

## Signal Flow

```
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
```

## Protection Architecture

| Fault | Detection | Response | Firmware-independent? | Recovery |
|---|---|---|---|---|
| Over-voltage | Vout via ADC (firmware) | Assert /SD → IR2104 off | No (firmware path) | Auto when Vout drops |
| Over-current (fast) | INA226 ALERT pin threshold | EXTI → /SD low | Partly (see note) | Manual restart |
| Over-current (coarse) | INA226 I2C poll ~1 kHz | CC fold / shutdown | No | Soft restart |
| Short circuit | INA226 ALERT | Immediate PWM disable | Partly | Manual restart |
| Over-temperature | NTC 10kΩ + ADC | Fan ramp → shutdown >85°C | No | Auto after cooling |
| Input surge | MOV 275V clamp | Energy absorbed | Yes (passive) | Transparent |
