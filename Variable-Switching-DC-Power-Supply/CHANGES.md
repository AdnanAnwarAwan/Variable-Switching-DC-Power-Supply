# Changes — Consistency & Correctness Pass

This revision makes the repo internally consistent and honest about what has been
proven. No hardware measurements were invented: unverified performance figures are
labelled as simulation/target, with `[PENDING]` slots in `test_procedure.md` to be
filled from real bench data.

## Firmware (was a non-functional skeleton → now a coherent program)
- Implemented all peripheral init (clock 72 MHz, GPIO, ADC1, I2C1, TIM1, TIM3
  encoder, TIM4 fan, USART1, IWDG). Previously empty `{ }` stubs.
- **Control-loop rate fixed:** TIM1 RepetitionCounter = 9 → update ISR at 20 kHz
  (50 µs), matching the docs. Previously the config gave a 5 µs ISR that could not
  host the ADC read. (DR-4)
- **Gate-drive topology fixed:** single PWM (PA8) → IR2104 IN; removed the
  complementary-output / TIM1 dead-time code that was incompatible with an IR2104.
  (DR-1)
- **Pin conflicts resolved:** encoder → TIM3/PA6-PA7, fan → TIM4/PB9, IR2104 /SD →
  PB12. Previously PA8 and PA0/PA1 were double-assigned. (DR-2)
- **OLED renders for real:** `display.c` now uses the SSD1306 library instead of
  formatting strings and discarding them.
- **INA226 driver added** (`ina226.c/.h`): configuration, calibration, and an
  ALERT over-current threshold.
- **Fast over-current EXTI added** (`HAL_GPIO_EXTI_Callback` on the ALERT pin).
- **Voltage calibration hook added** (`VCAL_GAIN`/`VCAL_OFFSET`) — required to
  meet the ±0.5% setpoint spec.
- Added `main.h`, printf-over-UART retarget, and the required IRQ handlers.
- `adc.h` divider comment corrected (112k/12k ratio, not "100k/12k").

## Documentation
- **Results relabelled** from "verified on hardware" to simulation/target with
  `[PENDING]` measurement slots. (DR-5)
- **RDS(on) corrected** from 8 mΩ to ~44 mΩ for the IRF540N, and the
  synchronous-rectification efficiency claim rescaled. (system_overview, TS-1)
- **OVP "comparator" claim corrected** to firmware-based detection; PRT-5
  independent-path requirement listed as an open hardware item. (DR-3)
- **Dead-time** described consistently as IR2104-internal (~520 ns), not TIM1
  194/200 ns. (README, trade_studies, test_procedure)
- Added the two docs other files referenced but that were missing:
  `prototyping_guide.md`, `design_review_findings.md`.
- Removed dangling references (`firefly_jd_mapping.md`, `presentation/README.md`).

## Hardware / BOM
- L2 → SRP1265A-101M (6.8 A Isat) — the 5 A part saturated at full load.
- C1 → 63 V — the 50 V part sat at 96% at 240 VAC high line.
- C2 → 50 V — the 35 V part exceeded the 80% derating target.
- WCCA verdict table updated with before/after margins. (DR-6)

## Repo hygiene
- Flattened the stray nested `Variable-Switching-DC-Power-Supply 2/` folder.
- Renamed the schematic to `power_supply_circuit.png` (was a spaced filename that
  didn't match the README reference).

## Still open (need your hardware decision — see design_review_findings.md)
- DR-1: confirm IR2104 (single-input) vs IR2110 (dual-input) — firmware assumes
  IR2104.
- DR-3: wire ALERT (or a comparator) directly to /SD for a truly
  firmware-independent trip.
- Fill the `[PENDING]` bench measurements in `test_procedure.md`.
