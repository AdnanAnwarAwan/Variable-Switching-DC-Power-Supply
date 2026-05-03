# PCB Design Rules

## 4-Layer Stackup

| Layer | Purpose |
|---|---|
| 1 Top | Signal, MCU, control ICs, analog sense |
| 2 (inner) | Solid ground plane — never broken |
| 3 (inner) | Power distribution |
| 4 Bottom | MOSFETs, high-current traces, heatsink copper |

## Critical Rules

### Switching Loop
- Q1→L2→C2→GND loop area < 1 cm²
- Wide copper pours, not traces
- C2 physically adjacent to switch node

### Trace Width
- Minimum 2mm per amp of continuous current
- Copper pours for all currents > 3A

### Ground Strategy
- Single star ground — power, analog, digital GND meet at one point
- No switching return currents under analog circuitry
- L2 ground plane is completely unbroken

### Decoupling
- 100nF ceramic within 3mm of every STM32 VDD pin
- 10µF bulk cap per domain (3.3V, 5V)

### EMC
- EMI filter components at board entry point
- Ground stitching vias around board perimeter
- Ferrite bead on debug connector ground return

## DRC Minimums

| Rule | Value |
|---|---|
| Signal trace width | 0.15mm min |
| Power trace width | 2.0mm per amp |
| Clearance | 0.15mm |
| Via drill | 0.3mm |
| AC-to-DC creepage | 4.0mm |
| AC-to-DC clearance | 2.0mm |
