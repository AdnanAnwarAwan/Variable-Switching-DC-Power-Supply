# PCB Design Notes

## Board Specifications
- Size: 120mm × 80mm
- Layers: 4
- Copper weight: 2oz top/bottom, 1oz inner
- Surface finish: HASL or ENIG
- Solder mask: Green
- Silkscreen: White both sides

## Component Placement Priority

1. **MOSFETs (Q1, Q2)** — bottom layer, over heatsink copper pour
2. **Switching loop (Q1→Q2→L2→C2)** — minimise loop, centre-board
3. **IR2104** — adjacent to MOSFET gates, short gate traces
4. **STM32** — top layer, separated from power section
5. **INA226** — near shunt resistor Rs, short Kelvin sense traces
6. **EMI filter (F1, MOV, L1, Cx)** — at AC input edge

## Heatsink Design
- Bottom copper pour: 40mm × 30mm under MOSFETs
- Thermal vias: 0.3mm drill, 8 vias per MOSFET pad, filled or plugged
- External heatsink: M3 standoffs at corners of copper pour
- Thermal interface material: Bergquist GP3000 or equivalent

## Creepage & Clearance (IEC 60950)
- AC Live to DC+: 4.0mm creepage, 2.0mm clearance
- AC neutral to chassis: 4.0mm creepage
- Add physical slot in PCB between AC and DC sections if needed

## Test Points
- TP1: Q1 gate (G1)
- TP2: Q2 gate (G2)
- TP3: Switch node (SW)
- TP4: Vout
- TP5: 3.3V rail
- TP6: GND
