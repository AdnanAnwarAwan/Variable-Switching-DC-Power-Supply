# Power Stage Simulation

`buck_powerstage.cir` is a runnable ngspice netlist of the synchronous buck power stage
using the real BOM values: 45 V bus, 200 kHz, 100 µH, 470 µF (50 mΩ ESR),
IRF540N RDS(on) = 44 mΩ, 200 ns dead-time with body-diode conduction.

```bash
sudo apt install ngspice        # or brew install ngspice
ngspice -b buck_powerstage.cir
```

## Verified results (ngspice 42, 30 ms transient, D = 0.28 open-loop)

| Measurement | Simulated | Hand calculation | Hardware measured |
|---|---|---|---|
| Vout (half load, open loop) | 12.52 V | D·Vin − I·(Ron+DCR) ≈ 12.5 V | 12.00 V (closed loop) |
| Inductor ripple ΔIL | 0.456 A | Vout(1−D)/(L·f) = 0.45 A | — |
| Output ripple | **22.6 mVpp** | ESR-dominated: ΔIL × 50 mΩ = 23 mV | **< 30 mVpp** ✅ |
| Load step 2.5→5 A droop (open loop) | −1.02 V dip | — | < 60 mV closed loop |

## What each result taught the design

1. **Ripple is ESR-dominated, not capacitance-dominated.** Capacitive term
   ΔIL/(8·f·C) ≈ 0.6 mV vs. 23 mV from ESR. Adding more µF does nothing; a lower-ESR
   cap (or polymer + MLCC bank) is the correct lever. Predicting 23 mV and measuring
   < 30 mV on hardware closes the model-to-measurement loop.
2. **The open-loop load step droops 1.0 V; the closed-loop hardware holds < 60 mV.**
   That delta *is* the PID loop's value, quantified.
3. **Startup rings at the LC resonance (~730 Hz) for milliseconds open-loop** — the
   simulation demonstrates exactly why the firmware soft-start ramp (5 ms) exists.
4. **Dead-time conduction:** during the 200 ns dead-time the low-side body diode
   conducts (visible as a −0.7 V excursion on the SW node) — this is the loss the
   synchronous FET eliminates for the rest of the cycle, and the reason dead-time
   should be minimized but never zero (shoot-through).

## Reproducing in LTspice (for interview demo)

1. Draw the same stage; use `IRF540` from LTspice's library (or the switch model here).
2. Complementary PULSE sources, 200 ns dead-time, D = 0.28, 5 µs period.
3. `.tran 0 30m 0 50n` — plot V(out), I(L1), V(sw).
4. Extensions worth showing live: sweep ESR (`.step param resr 10m 100m 30m`) to show
   the ripple lever; add an input LC filter and demonstrate the undamped filter
   interacting with the converter's negative input impedance (Middlebrook criterion),
   then damp it.

## What is deliberately NOT simulated

The PID loop. The control loop runs in firmware; simulating it in SPICE would model
my model, not my code. Loop behavior is verified on hardware (load-step scope capture,
test §5) — simulate what you can't easily measure, measure what you can.
