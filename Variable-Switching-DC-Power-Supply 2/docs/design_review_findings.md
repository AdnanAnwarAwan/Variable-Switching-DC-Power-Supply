# Design Review Findings & Corrective Actions

A self-conducted design review of the released repository, run the way a peer review
board would run it. Every finding has a severity, root cause, and corrective action.
Shipping hardware without a review like this is how escapes reach the field.

| # | Severity | Finding | Root cause | Corrective action | Status |
|---|---|---|---|---|---|
| DR-1 | **Critical (doc)** | Documentation showed 230 VAC → bridge → "45 V bus" with no transformer. Rectified 230 VAC is ~325 V DC — would destroy the 50 V bulk caps and 100 V FETs. The physical build includes T1; the docs omitted it. | Block diagram drawn from memory, never cross-checked against BOM/hardware | T1 (230:32 V, 250 VA) added to README architecture, BOM, and schematic corrections table | ✅ Closed |
| DR-2 | **Critical (fw)** | Blocking I2C read of INA226 (~70–100 µs at 400 kHz) inside the 50 µs PID ISR → guaranteed ISR overrun, jittering the control loop | Sensor reads grouped by function ("read all sensors") instead of by timing budget | Current sampling moved to main loop (~1 kHz); microsecond OCP delegated to INA226 ALERT hardware pin (PB0 EXTI); ISR now reads only the ~21 µs ADC | ✅ Closed |
| DR-3 | **Major (hw)** | L2 Isat = 5 A but worst-case peak inductor current = 5.23 A (5 A load + ΔIL/2, SPICE-verified) → saturation at full load | Inductor selected on RMS current, not peak; no derating pass | BOM change to ≥ 6.8 A Isat part; derating rule added (Isat ≥ 1.3× peak) — see `component_derating_wcca.md` | 📋 Open (BOM rev) |
| DR-4 | **Major (hw)** | C1 (50 V) at 96 % of rating at 240 VAC high line | Rated against nominal 230 VAC, not the INT-1 requirement of 240 VAC | 63 V part specified for next revision | 📋 Open (BOM rev) |
| DR-5 | Minor (fw) | Fault handler wrote PA8 twice (copy-paste); fault LED never driven | No code review; no HIL test of fault indication | Fault LED assigned PA4, handler corrected | ✅ Closed |
| DR-6 | Minor (fw) | No watchdog — a hung main loop (I2C lockup) would leave the converter free-running | Watchdog deferred as "later" | IWDG added, 1 s timeout, refreshed in main loop; recovery re-enters soft-start | ✅ Closed |
| DR-7 | Minor (doc) | PCB rules simultaneously specified "single star ground" and "solid unbroken plane" — contradictory | Rules copied from two different design traditions (audio vs. SMPS) without reconciliation | Solid-plane strategy adopted; star retained only for the chassis bond | ✅ Closed |
| DR-8 | Observation | Setpoint accuracy requirement (±0.5 %) unreachable uncalibrated (±1.8 % RSS from divider/Vref tolerances) | Requirement written without tolerance analysis | Single-point gain calibration made mandatory in test §4; production fix: 0.1 % divider + external Vref | ✅ Closed |

## Why this document exists (interview framing)

Interviewers do not expect flawless first-revision designs — nobody ships one. They
expect engineers who **find their own escapes before the review board (or the launch
pad) does**. DR-1 through DR-3 are exactly the class of error that worst-case analysis,
timing budgets, and doc-vs-hardware cross-checks exist to catch; this table is evidence
those processes ran.
