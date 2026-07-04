# Trade Studies

Each major architecture decision was made by weighted comparison, not habit.
Format: options → criteria → decision → what was given up (every trade has a cost).

## TS-1: Power topology

| Criterion (weight) | Linear reg | Non-sync buck | **Sync buck** | Flyback |
|---|---|---|---|---|
| Efficiency at 12 V/5 A (×3) | ~27 % | ~84 % | **~89 %** | ~82 % |
| Component count (×1) | Lowest | Low | **Medium** | High (transformer design) |
| Output noise (×2) | Best | Medium | **Medium** | Worst |
| Control complexity (×1) | None | Simple | **Medium (dead-time)** | Medium |
| Wide Vout range 1.25–30 V (×2) | Yes but thermal-limited | Yes | **Yes** | Re-design per range |

**Decision:** synchronous buck. **Cost accepted:** dead-time management and shoot-through
risk — mitigated by TIM1 hardware dead-time insertion (194 ns) and the IR2104's internal
interlock. At 5 A, the low-side FET (8 mΩ) saves ~1.8 W over a Schottky (0.4 V drop):
2 W × $0 vs. one extra FET + driver complexity — worth it above ~2 A, not below.

## TS-2: Control — analog IC vs. digital (MCU PID)

| Criterion | Analog controller (e.g. UC3843) | **STM32 digital PID** |
|---|---|---|
| Loop bandwidth | 10s of kHz — better | ~2 kHz — adequate for a bench supply |
| Adjustability (Vset, Ilim, soft-start, UI) | Fixed by resistors | **Firmware — the product requirement** |
| Telemetry/display | None | **Built in** |
| Failure modes | Simple, predictable | Needs watchdog + hardware protection backstop |

**Decision:** digital. **Cost accepted:** lower loop bandwidth (load-step recovery ~1 ms
instead of ~100 µs) and a software failure mode — mitigated by requirement PRT-5
(hardware shutdown path) and PRT-6 (watchdog). For a variable bench supply, the UI and
adjustability requirements dominate; for a fixed-rail flight converter I would choose
the analog controller or a hybrid.

## TS-3: Current sensing

| Criterion | Low-side shunt + op-amp | **INA226 (digital, I2C)** | Hall sensor |
|---|---|---|---|
| Accuracy | Depends on op-amp offset | **16-bit, factory-calibrated, 0.1 %** | 1–2 % |
| Bandwidth | High | Low (I2C sample rate) | Medium |
| Fast OCP | Needs comparator | **ALERT pin — hardware threshold** | Needs comparator |
| Ground disturbance | Breaks ground reference | **High-side — none** | None |

**Decision:** INA226. **Cost accepted:** slow readout over I2C — which drove a firmware
architecture rule: I2C reads happen in the main loop (~1 kHz), never in the 50 µs PID ISR;
microsecond-class over-current protection is delegated to the ALERT hardware pin.
(See `design_review_findings.md` — the first firmware revision violated this.)

## TS-4: Switching frequency — 200 kHz

Higher f → smaller L and C, faster loop, but switching losses rise linearly with f and
the IRF540N's high gate charge (~71 nC) makes it a poor high-frequency switch.
- 100 kHz: L doubles (bigger, costlier), ripple current control harder
- **200 kHz: ΔIL = Vout(1−D)/(L·f) ≈ 0.45 A (9 % of full load) with the 100 µH part — verified in `simulation/`**
- 500 kHz: gate-drive loss ≈ Qg·Vgs·f ≈ 71n × 10 × 500k ≈ 0.36 W/FET plus switching loss — efficiency target fails

**Decision:** 200 kHz. **Cost accepted:** physically large LC. A modern FET
(e.g. 60 V NexFET, Qg < 10 nC) would allow 500 kHz+ and shrink the board — listed as
an improvement in `firefly_jd_mapping.md`.
