# Prototyping & Safe Bring-Up Guide

The goal of staged bring-up is that **the first fault at every stage trips a bench
current limit, not a MOSFET or your hand.** Mains is connected last, after the
converter is already proven on a safe DC source.

## Stage 0 — Bare board, no power
- Visual + DMM: no solder bridges, correct orientation on Q1/Q2, C1, bridge.
- VDD–GND resistance > 100 Ω on every rail.
- Confirm AC section is physically isolated from the SELV section (open circuit
  Live → DC out).

## Stage 1 — Logic only (5 V bench supply into the 5 V rail)
- Bench supply 5.0 V, 100 mA limit. Confirm 3.3 V rail (2.97–3.43 V).
- Flash firmware via SWD. Confirm OLED init and USART banner.
- With `I_ALERT_AMPS`/PID disabled or output stage unpopulated, verify the MCU
  boots, the watchdog holds, and the encoder increments the setpoint.

## Stage 2 — Power stage on a current-limited DC bus (NO MAINS)
- Disconnect the T1 secondary. Feed the DC bus node directly from a
  current-limited bench supply.
- Start at **15 V, 200 mA limit.** Enable PWM. The converter should regulate a
  low output; any shoot-through or mis-wire trips the bench limit harmlessly.
- Scope the SW node and IR2104 HO/LO: confirm clean switching, no overlap.
- Raise the bus in steps **15 → 30 → 45 V**, increasing the current limit only
  after each step is clean. Check dead-time behaviour and thermals at each step.

## Stage 3 — Closed-loop on the DC bus
- Run the PID. Verify setpoint tracking and the 20 kHz ISR rate (toggle a spare
  GPIO in the ISR, scope it).
- Exercise protections deliberately: force the INA226 ALERT, force OVP, force
  over-temp (heat the NTC). Confirm /SD asserts and the FAULT LED lights.

## Stage 4 — Mains, behind isolation
- Only now connect the T1 secondary and energize the primary **through an
  isolation transformer / variac and a bench RCD.**
- Bring the variac up slowly; watch input current and DC-bus voltage.
- Differential probe only on the primary side; scope ground stays on SELV.

## Stage 5 — Full validation
- Run `test_procedure.md` end to end and record measured values in the
  `[PENDING]` slots.

## Rules that apply at every stage
- One hand near energized primary; no rings/watch.
- Bleed/verify C1 discharged before touching the power stage.
- If anything smells hot or a limit trips, stop and find the cause before raising
  voltage or current.
