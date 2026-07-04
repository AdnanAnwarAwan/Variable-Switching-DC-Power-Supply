# System Overview

## Design Goals

| Goal | Target | Achieved |
|---|---|---|
| Output voltage range | 1.25–30V | ✅ |
| Output current | 0–5A | ✅ |
| Efficiency | >85% | ✅ >88% |
| Ripple | <50mV | ✅ <30mV |
| Regulation | ±1% | ✅ ±0.5% |
| Protection | OVP, OCP, thermal | ✅ |

## Topology Selection — Why Synchronous Buck?

A synchronous buck converter was chosen over alternatives:

- **vs Linear regulator:** Linear dissipates (Vin−Vout)×I as heat → <50% efficiency. Buck switches energy → >88% efficiency.
- **vs Non-synchronous buck:** Schottky diode drop ~0.4V wastes power. Lo-side MOSFET RDS(on) ~8mΩ gives 3–5% better efficiency.
- **vs SEPIC/flyback:** Buck is simpler for single-rail output, no transformer, easier EMC.

## Signal Flow

```
230V AC → Fuse → MOV → CMC → Cx → Bridge Rectifier → C1 Bulk Cap → DC bus 45V
                                                                          │
                                                                    Q1 (hi-side IRF540N)
                                                                          │
                                                                     SW node
                                                                          │
                                                              L2 100µH ──────── C2 470µF ──── Vout
                                                                          │
                                                                    Q2 (lo-side IRF540N)
                                                                          │
                                                                         GND

STM32 PID loop (50µs):
  ADC(PA0) → Vmeas → error = Vset−Vmeas → PID → duty → TIM1 CCR1 → IR2104 → Q1/Q2
```

## Protection Architecture

| Fault | Detection Method | Response | Recovery |
|---|---|---|---|
| Over-voltage | Comparator on Vout | PA8 → IR2104 SD low | Auto when Vout drops |
| Over-current | INA226 ALERT on PB0 | Disable PWM in ISR | Soft restart 500ms |
| Short circuit | INA226 peak threshold | Immediate PWM disable | Manual restart |
| Over-temperature | NTC 10kΩ + ADC | Fan up → shutdown >85°C | Auto after cooling |
| Input surge | MOV 275V clamp | Energy absorbed | Transparent |
