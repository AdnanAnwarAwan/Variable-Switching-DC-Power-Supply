# Repo Punch-List — Variable-Switching-DC-Power-Supply

Ordered by how much each item costs you under technical scrutiny, not by effort.
Fix top-down.

---

## FORK DECISION (make this first)

Half the P0/P1 items below resolve differently depending on your answer:

- **(A) Ship real firmware** — commit the actual CubeMX-generated init + working
  drivers, keep the "measured on hardware" claims. More work, strongest result.
- **(B) Keep the skeleton** — then every "✅ verified on hardware" result must be
  relabelled **simulated / target**, and the firmware must be labelled a reference
  skeleton, not a build.

Items tagged **[FORK]** below have a different fix under A vs B.

---

## P0 — Credibility killers (claim-vs-reality)

- [ ] **P0-1 [FORK] — Empty peripheral init.** `firmware/Core/Src/main.c`:
  `SystemClock_Config`, `MX_GPIO_Init`, `MX_ADC1_Init`, `MX_I2C1_Init`,
  `MX_TIM2_Init`, `MX_TIM3_Init`, `MX_USART1_Init` are all empty `{ }` stubs. No
  clock, no GPIO, no ADC, no I2C → the firmware cannot run as committed.
  A: paste the real CubeMX code. B: rename them clearly as stubs and state the repo
  ships skeleton firmware.

- [ ] **P0-2 [FORK] — OLED never renders.** `display.c` `Display_Update` writes into
  `line` three times (each `snprintf` overwrites the last) then discards it with
  `(void)line`. `Display_ShowFault` is `(void)msg`. So the live V/I/T display —
  requirement FUN-4 — is not implemented. A: integrate the font/buffer library the
  comment points to and actually push pixels. B: mark FUN-4 as not-yet-implemented.

- [ ] **P0-3 [FORK] — Results claimed as measured.** `README.md`,
  `docs/test_procedure.md`, `docs/system_overview.md` mark efficiency >88%, ripple
  <30 mV, load regulation, and all protection tests as "✅ verified on hardware."
  A skeleton with no init did not produce these. A: keep only if real firmware +
  real bench data exist. B: relabel every ✅ as *simulated* or *target*.

- [ ] **P0-4 — Claimed hardware protection path is absent.** PRT-3 / PRT-5 promise a
  short-circuit kill via the INA226 ALERT pin (PB0 EXTI) that does **not** depend on
  firmware. There is no PB0 EXTI handler / ALERT ISR anywhere in `main.c`. Either
  implement the EXTI callback that pulls the IR2104 SD pin, or stop claiming a
  firmware-independent protection path.

---

## P1 — Technical contradictions a sharp reviewer catches

- [ ] **P1-1 — Loop rate contradicts the timer.** Docs (`README`, `pid_control.md`,
  the ISR comment) say the PID runs at **50 µs / 20 kHz**. But `MX_TIM1_Init` sets
  prescaler 0, period 359, `RepetitionCounter = 0` on 72 MHz → update ISR fires at
  **5 µs / 200 kHz**. Fix one of: set `RepetitionCounter = 9` (gives true 20 kHz),
  or change the docs to 200 kHz.

- [ ] **P1-2 — ADC can't fit the ISR.** Tied to P1-1: the ISR does a blocking
  `ADC_ReadVoltage()` the code itself calls "~21 µs". That's impossible inside a
  5 µs window and is 42% of a 50 µs window. Resolve P1-1 first, then justify the ADC
  timing against the *actual* loop period.

- [ ] **P1-3 — Inductor saturation vs. clean full-load claims.**
  `component_derating_wcca.md` correctly flags L2 (SRR1260, 5 A Isat) saturating at
  peak 5.23 A at full load. Yet the headline claims pristine >88% efficiency and
  <30 mV ripple *at full load*. Both can't be true. Either swap to the ≥6.8 A Isat
  part the WCCA already recommends (SRP1265A-101M) and update the BOM + results, or
  stop claiming clean full-load numbers.

- [ ] **P1-4 — RDS(on) figure is wrong and undercuts your own argument.**
  `system_overview.md` says "Lo-side MOSFET RDS(on) ~8 mΩ gives 3–5% better
  efficiency." The IRF540N is ~44 mΩ (your own `simulation/buck_powerstage.cir` uses
  `Ron = 0.044`). At 44 mΩ × 5 A ≈ 0.22 V, the sync-vs-Schottky (0.4 V) benefit is
  real but roughly *half* what an 8 mΩ part would give. Correct the number and the
  efficiency delta.

- [ ] **P1-5 — OVP "comparator" path is actually firmware.** `system_overview.md`
  protection table lists OVP as "Comparator on Vout → PA8 → IR2104 SD." There is no
  comparator in the BOM/schematic; PA8 is a firmware-driven GPIO asserted in
  `Fault_Shutdown`. That means the IR2104 SD pin is pulled by firmware, contradicting
  PRT-5 ("at least one shutdown path shall not depend on firmware"). Add a real
  analog comparator, or downgrade the PRT-5 claim.

- [ ] **P1-6 — PER-3 (±0.5% setpoint) fails as-shipped.** The WCCA itself concludes
  single-point gain calibration is *required* (uncalibrated ≈ ±1.8%). But
  `ADC_ReadVoltage()` uses only the nominal `VDIV_RATIO` — no calibration constant
  exists in the firmware. Either add the calibration constant the WCCA says is
  mandatory, or mark PER-3 as unmet without calibration.

---

## P2 — Broken references & repo hygiene

- [ ] **P2-1 — Dangling cross-references (worse than dead README lines, because other
  docs cite them):**
  - `docs/prototyping_guide.md` — cited by `test_procedure.md` §0.5
  - `docs/design_review_findings.md` — cited **twice** by `trade_studies.md`
  - `presentation/README.md` — listed in README structure
  Either write these files or delete every reference to them.

- [ ] **P2-2 — Schematic filename mismatch.** README calls it
  `power_supply_circuit.jpg`; the file on disk is
  `Variable Switching DC voltage supply.png`. Rename the file or fix the reference
  (and drop the space in the filename).

- [ ] **P2-3 — Stray nested duplicate folder.** The entire project sits inside
  `Variable-Switching-DC-Power-Supply 2/`; the top-level `README.md` contains only an
  image tag. Flatten it — move the project up one level and delete the " 2" wrapper.

---

## P3 — Polish

- [ ] **P3-1 — Current limit isn't user-settable.** `i_limit` is fixed at 5.0 A; the
  encoder only adjusts voltage. FUN-3 / the UI imply an adjustable CC limit. Add the
  UI or scope the claim.

- [ ] **P3-2 — SET-current on display is hardcoded 0.00 A.** `Display_Update` passes
  `0.0f` for the set current, but the layout comment shows a real value. Wire it or
  remove the field.

- [ ] **P3-3 — Dead-time 194 vs 200 ns.** `DEADTIME_COUNTS = 14` → 194 ns.
  `test_procedure.md` §3 says 200 ns. Pick one number everywhere.

- [ ] **P3-4 — Divider comment.** `adc.h` comment says "100k / 12k" but `VDIV_RATIO`
  uses 112k/12k (R1+R2)/R2. The math is right; the comment is misleading. Clarify.

- [ ] **P3-5 — C1 high-line derating in BOM.** WCCA flags 4700 µF/50 V at 96% at
  240 VAC high line and recommends a 63 V part. BOM still lists 50 V. If you keep the
  aerospace-relevance framing, reflect the fix (or note it as a known open item).
