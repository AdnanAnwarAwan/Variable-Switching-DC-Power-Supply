# Schematics

## power_supply_circuit.png

Complete circuit schematic covering all three stages:

1. **Power stage** — AC input (fuse, MOV, common-mode choke, X-cap), bridge
   rectifier (GBU806), bulk capacitor C1 (on the DC bus after the rectifier),
   hi-side MOSFET Q1, lo-side MOSFET Q2, IR2104 gate driver, inductor L2,
   output capacitor C2, regulated DC output.
2. **STM32 control core** — pin connections, crystal, LDO, SWD header.
3. **Sensing and UI** — voltage divider, INA226 (with ALERT), OLED, rotary
   encoder, status LEDs, fan driver.

**Note:** the IR2104 is driven from a single STM32 PWM output (PA8 → IR2104 IN);
the driver generates the complementary gate signals and dead-time. If your
schematic instead shows two separate gate signals from the MCU, it was drawn for
a dual-input driver (e.g. IR2110) — reconcile it with the firmware pin map in
`firmware/Core/Inc/main.h` and see `docs/design_review_findings.md` DR-1.
