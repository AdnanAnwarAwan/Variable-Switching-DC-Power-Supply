# Component Derating & Worst-Case Analysis

This analysis originally ran against the first-pass BOM and caught three parts
that failed derating. The BOM has since been **corrected** (L2, C1, C2); both the
original finding and the applied fix are shown so the engineering judgement is
visible.

## Derating targets used

| Part class | Parameter | Target |
|---|---|---|
| Capacitors (electrolytic) | Voltage | ≤ 80% of rating |
| Capacitors (ceramic) | Voltage | ≤ 50–60% of rating |
| MOSFETs | VDS | ≤ 75%; junction ≤ 110 °C |
| Resistors | Power | ≤ 50% of rating |
| Diodes/bridge | Reverse voltage | ≤ 70%; current ≤ 50% |
| Inductor | Current | Isat ≥ 130% of peak current |

## Stress analysis (corrected BOM)

| Part | Rating | Worst-case stress | Margin | Verdict |
|---|---|---|---|---|
| Q1/Q2 IRF540N | 100 V, 33 A | 55 V incl. ring; 5.23 A peak | 55% VDS | PASS |
| C1 4700 µF **/63 V** | 63 V | 48 V at 240 VAC high line | 76% | PASS (was 50 V → 96%, FAIL) |
| C2 470 µF **/50 V** | 50 V | 30 V max output | 60% | PASS (was 35 V → 86%, marginal) |
| GBU806 | 600 V, 8 A | 64 V peak reverse, 5 A avg | 11% / 63% | PASS |
| L2 100 µH **6.8 A Isat** (SRP1265A-101M) | 6.8 A | peak IL = 5 + ΔIL/2 ≈ 5.23 A | Isat/peak = 1.30 | PASS (was 5 A Isat → FAIL, saturated) |
| R4 shunt 10 mΩ/5 W | 5 W | 0.25 W | 5% | PASS |
| MOV S14K275 | 275 VAC | 240 VAC high line | 87% | PASS |
| AMS1117-3.3 | 15 V in, 1 A | 5 V in, ~150 mA | large | PASS |
| IR2104 bootstrap | 625 V abs max | 45 V bus | large | PASS; duty capped at MAX_DUTY leaves bootstrap refresh time |

## Findings and corrective actions

1. **L2 saturation (was the critical escape).** ΔIL = 0.456 A (SPICE-verified),
   peak 5.23 A. The original 5 A-Isat part saturated at full load, collapsing
   inductance and degrading ripple/OCP at exactly max load. **Fixed:** BOM changed
   to SRP1265A-101M (6.8 A Isat → 1.30× margin on peak).
2. **C1 at 96% of rating at 240 VAC high line** violated even commercial practice
   (the 50 V part was sized against 230 VAC, but INT-1 specifies 240 VAC).
   **Fixed:** BOM changed to a 63 V part (76%).
3. **C2 at 86%** exceeded the ≤80% target. **Fixed:** 35 V → 50 V part (60%).

## Worst-case tolerance stack — setpoint accuracy (PER-3)

Divider 100k/12k (1%), Vref 3.3 V (±1% LDO), ADC ±2 LSB INL:
- Divider gain error ±1.4% (RSS) dominates
- Total ≈ ±1.8% **uncalibrated** → PER-3 (±0.5%) fails without calibration
- **Action:** single-point gain calibration against a bench DMM is **required**,
  stored as `VCAL_GAIN`/`VCAL_OFFSET` in `firmware/Core/Inc/adc.h`. For
  production: 0.1% divider resistors + external 0.5% Vref.
