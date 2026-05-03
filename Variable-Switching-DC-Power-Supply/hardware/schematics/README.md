# Schematics

## power_supply_circuit.jpg

Complete circuit schematic covering all three stages:

1. **Power stage** — AC input (fuse, MOV, CMC, Cx), bridge rectifier (GBU806),
   bulk capacitor C1 (correctly placed after rectifier on DC bus),
   hi-side MOSFET Q1, lo-side MOSFET Q2, IR2104 gate driver,
   inductor L2, output capacitor C2, regulated DC output

2. **STM32 control core** — all pin connections, crystal, LDO, SWD header

3. **Sensing and UI** — voltage divider, INA226, OLED, rotary encoder,
   status LEDs, fan driver

## Corrections from Original Design

The following errors from a common reference schematic were identified and corrected:

| Component | Wrong position | Correct position |
|---|---|---|
| F1 Fuse | Inside combined EMI block | First on AC phase wire |
| MOV | After choke | Before choke, across L-N |
| Cx cap | Before choke | After choke, before rectifier |
| C1 Bulk cap | Before bridge rectifier (AC side) | After bridge rectifier (DC bus) |
