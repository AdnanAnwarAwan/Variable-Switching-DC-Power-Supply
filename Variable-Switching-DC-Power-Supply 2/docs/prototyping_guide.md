# Prototyping Guide — Staged Bring-Up Strategy

Rule 1: **switching power stages are never built on solderless breadboards.** Breadboard
contact inductance (~20 nH/row) and capacitance turn a 200 kHz hard-switched node into
an oscillator/EMI source, and 5 A exceeds breadboard contact ratings. Knowing what
*not* to breadboard is the difference between a tinkerer and a fire.

Rule 2: **the mains section is never prototyped loose.** Transformer, fuse, MOV, and
rectifier go straight to an enclosed/guarded chassis mock-up, or are bypassed entirely
during development (see DC-injection below).

## Stage 1 — Control core on breadboard (safe, low-voltage)
- STM32F103 Blue Pill / Nucleo, SSD1306 OLED, EC11 encoder, INA226 breakout, NTC divider.
- Everything runs at 3.3/5 V — ideal breadboard territory.
- Milestone: encoder changes setpoint on OLED; INA226 reads a known current through a
  power resistor; UART telemetry streams; PWM pair visible on scope with correct
  dead-time (200 ns) **before any power stage exists**.

## Stage 2 — Gate drive + power stage on copper (perfboard/protoboard or first PCB)
- IR2104 + FETs + LC dead-bug or Manhattan-style on copper-clad, tight hot loop; or go
  straight to a cheap first-spin PCB (correct answer in 2026 — a 4-layer proto is < $50).
- **DC injection:** power the DC bus from a current-limited bench supply
  (e.g. Rigol DP832: start 15 V / 200 mA limit) — NOT from the mains section.
  Every fault during development then trips a bench current limit, not a fuse or a FET.
- Milestone: open-loop fixed duty from Stage-1 firmware; verify SW node waveform,
  no shoot-through (measure both gate signals simultaneously), Vout ≈ D·Vin.

## Stage 3 — Close the loop, still on DC injection
- Enable PID at low bus voltage (15 V) and light load; verify soft-start ramp on scope.
- Raise bus voltage in steps 15 → 30 → 45 V, raising the bench current limit only as
  each step passes. Load steps with electronic load; tune Kp/Ki/Kd per firmware README.

## Stage 4 — Mains section, last
- Only after Stages 1–3 pass: connect transformer/rectifier/bulk cap. Safety in
  `test_procedure.md` §0 applies (isolation is provided by T1, but treat the primary
  side as lethal always).

## Why this order (interview articulation)
Each stage adds exactly one unknown. If Stage 3 misbehaves, the control core and power
stage are individually proven — the fault space is the *interaction*, not either block.
That is root-cause discipline designed into the build order, not applied after the fire.
