# Wiring Harness Design

Internal harnesses for the enclosed supply, built to IPC/WHMA-A-620 workmanship.

## Harness list

| # | Harness | Conductors | Wire | Termination |
|---|---|---|---|---|
| H1 | IEC inlet → fuse/switch → T1 primary | L, N, PE | 18 AWG, 300 V rated, HAR/UL1015 | Insulated 6.3 mm spade (crimped), PE ring lug to chassis stud — **PE is the first wire connected, last disconnected, and mechanically independent** |
| H2 | T1 secondary → PCB AC-in | 2 × 32 VAC | 16 AWG (5 A + rectifier ripple current form factor ~1.6× ⇒ ~8 A RMS) | Crimped ferrules into screw terminals |
| H3 | PCB DC-out → front binding posts | +OUT, −OUT | 14 AWG silicone (5 A with margin, flexible) | Ring lugs, torque-checked |
| H4 | Front panel: OLED + encoder → PCB | I2C ×2, enc A/B/SW, 3V3, GND ×2 | 26 AWG, 7-way | JST-XH, keyed |
| H5 | Fan → PCB | +12 V, PWM/GND | 24 AWG | JST-XH 2-pos |

## Design rules applied

1. **Crimp, never solder, stranded wire into terminals** — solder wicks up strands and
   creates a stress riser at the flex point (IPC-A-620 class rule). Use the correct
   crimp tool with a positioner; pull-test one sample per batch.
2. **Current-based gauge selection with derating:** wire rated ≥ 2× continuous current
   in bundled/enclosed conditions (free-air ratings don't apply inside a chassis).
3. **I2C in H4 is the EMI-sensitive run:** keep < 15 cm, route away from T1 and the
   power stage, twist SDA/SCL with a ground return; 4.7 kΩ pull-ups already on PCB.
4. **Service loops** at both ends of every harness; strain relief at every connector;
   no conductor supports its own connector's weight.
5. **Keying and labeling:** every connector keyed or unique; both harness ends labeled.
   H2 and H3 use different connector families so they physically cannot be swapped.
6. **Separation:** mains harness (H1) bundled and routed apart from H4/H5; where
   crossing is unavoidable, cross at 90°.
7. **Safety spacing:** H1 maintains creepage to SELV wiring; primary-side terminals
   covered (finger-safe) since the enclosure may be opened for service.
