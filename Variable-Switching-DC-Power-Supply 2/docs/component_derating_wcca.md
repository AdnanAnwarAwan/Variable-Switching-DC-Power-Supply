# Component Derating & Worst-Case Analysis

Aerospace-style stress analysis applied to the existing BOM. Derating philosophy per
NASA EEE-INST-002 / MIL-STD-975 guidance: parts operate at a fraction of their rating
across the full environment, so end-of-life drift, tolerance stacking, and transients
never push a part past its limit.

## Derating targets used

| Part class | Parameter | Target |
|---|---|---|
| Capacitors (electrolytic) | Voltage | ≤ 80 % of rating |
| Capacitors (ceramic) | Voltage | ≤ 50–60 % of rating |
| MOSFETs | VDS | ≤ 75 % ; junction temp ≤ 110 °C |
| Resistors | Power | ≤ 50 % of rating |
| Diodes/bridge | Reverse voltage | ≤ 70 % ; current ≤ 50 % |
| Inductor | Current | Isat ≥ 130 % of peak current |

## Stress analysis of the as-built BOM

| Part | Rating | Worst-case stress | Margin | Verdict |
|---|---|---|---|---|
| Q1/Q2 IRF540N | 100 V, 33 A | VDS = 45 V bus + ~10 V switching ring = 55 V; ID = 5 A + 0.23 A ripple | 55 % of VDS rating | ✅ PASS |
| C1 4700 µF/50 V | 50 V | 45 V nominal; 48 V at 240 VAC high-line (32 VAC ×1.06 ×√2) | **96 % of rating at high line** | ⚠️ **MARGINAL — flight/production fix: 63 V part** |
| C2 470 µF/35 V | 35 V | 30 V max output | 86 % | ⚠️ Marginal by aerospace rules (target ≤ 80 %) → 50 V part |
| GBU806 | 600 V, 8 A | 64 V peak reverse, 5 A avg | 11 % / 63 % | ✅ PASS |
| L2 100 µH/5 A | Isat spec 5 A | Peak IL = 5 + ΔIL/2 ≈ 5.23 A | **Peak exceeds Isat** | ❌ **FAIL — inductor saturates at full load + ripple. Fix: 6.8 A Isat part (e.g. SRP1265A-101M)** |
| R4 shunt 10 mΩ/5 W | 5 W | I²R = 25 × 0.01 = 0.25 W | 5 % | ✅ PASS |
| MOV S14K275 | 275 VAC | 240 VAC high line | 87 % | ✅ PASS (MOVs are rated for this use) |
| AMS1117-3.3 | 15 V in, 1 A | 5 V in, ~150 mA | Large | ✅ PASS (but no thermal pad — fine at this load) |
| IR2104 bootstrap | VB−VS abs max 625 V | 45 V bus | Large | ✅ PASS; check bootstrap refresh at D→100 % (firmware caps duty at MAX_DUTY, leaving refresh time — deliberate) |

## Findings 
1. **L2 saturation at full load is a genuine design escape.** ΔIL = 0.456 A (SPICE-verified),
   peak = 5.23 A against a 5 A Isat part. Saturating inductance collapses → ripple current
   spikes → efficiency and OCP behavior degrade at exactly max load. Corrective action:
   BOM change to ≥ 6.8 A Isat.
2. **C1 at 96 % of voltage rating at 240 VAC high line** violates even commercial practice.
   The 50 V rating was chosen against 230 VAC nominal; requirement INT-1 says 240 VAC.
   This is a classic requirement-vs-implementation gap that WCCA exists to catch.
3. Everything else passes commercial derating; two parts fail *aerospace* derating —
   which is precisely the difference between a bench design and a flight design.

## Worst-case tolerance stack — voltage setpoint accuracy (PER-3)

Divider 100k/12k (1 %), Vref = 3.3 V (±1 % LDO), ADC ±2 LSB INL:
- Divider gain error: ±1.4 % (RSS) → dominates
- Total RSS error at 12 V: ≈ ±1.8 % **uncalibrated** → PER-3 (±0.5 %) fails without calibration
- **Conclusion:** single-point gain calibration against a bench DMM is *required*, not optional.
  Stored as a firmware constant. For production: 0.1 % divider resistors + external 0.5 % Vref.
