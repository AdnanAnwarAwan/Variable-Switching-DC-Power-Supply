# Mapping to Hardware Design Engineer II — Firefly Aerospace

Line-by-line mapping from the job description to evidence in this repository, plus the
flight-evolution path showing how this bench design becomes an avionics power module.

## JD requirement → repository evidence

| JD language | Evidence here |
|---|---|
| "Own end-to-end circuit card development: schematic capture and layout for complex **digital/analog/power** designs" | One board: 200 kHz power stage (power), Kelvin-sensed shunt + ADC dividers + NTC (analog), STM32 control/UI/telemetry (digital). Schematic in `hardware/schematics/`, layout rules in `docs/pcb_design_rules.md`, 4-layer stackup in `hardware/pcb/` |
| "**EEE component selection**" | `hardware/bom/BOM.csv` with manufacturer P/Ns + `docs/component_derating_wcca.md` — stress/derating pass that caught two escapes (DR-3, DR-4) |
| "**Electrical simulations**" | `simulation/buck_powerstage.cir` — runnable, results verified against hand calculations and hardware (23 mV predicted / <30 mV measured) |
| "**Rapid prototyping** for flight, qualification" | `docs/prototyping_guide.md` — staged bring-up, DC-injection development, one-unknown-per-stage |
| "Perform technical **trade studies**, **requirement capture**" | `docs/trade_studies.md` (4 weighted trades with accepted costs), `docs/requirements.md` (numbered, quantified, verification-linked) |
| "Lead **troubleshooting and root-cause analysis** using standard test equipment" | `docs/test_procedure.md` staged bring-up with pass criteria; `docs/design_review_findings.md` — 8 findings with root causes and corrective actions |
| "Understand and implement **aerospace guidelines** for electronic assemblies" | Derating per EEE-INST-002 philosophy, protection-independent-of-software rule (PRT-5), IPC-A-610/620 workmanship in `docs/wiring_harness.md`, watchdog + soft-start recovery |
| "Experienced using **test equipment** to verify component and circuit functionality" | Full procedure exercised on Rigol DP832, ≥100 MHz scope, electronic load, IR camera — ripple measured with ground-spring technique at 20 MHz BW |
| "Proficiency with **Altium** (or similar) preferred" | Schematic/layout executed in KiCad; concepts (hierarchical sheets, DRC, hot-loop layout, stackup) are tool-independent — see interview note below |

## Flight evolution: bench supply → 28 V avionics power module

If this design were re-targeted as a launch-vehicle secondary power / telemetry card:

| Subsystem | Bench version (this repo) | Flight version |
|---|---|---|
| Input | 230 VAC → T1 → 45 V bus | 28 V vehicle bus (22–36 V, MIL-STD-704-style), reverse-polarity PFET, TVS, damped input filter (Middlebrook-checked) |
| Power stage | Discrete IRF540N + IR2104, 200 kHz | Automotive/space-grade integrated buck (e.g. LMR336xx-Q1 class), fixed rails, higher f, smaller magnetics |
| Control | Firmware PID (adjustability was the requirement) | Analog control IC or hardened fixed-duty regulation — software out of the fast loop entirely |
| Telemetry | OLED + UART | CAN bus (rolling counter + CRC), per-rail V/I/T at 10 Hz; MCU on an always-on housekeeping rail so a latched fault can still be *reported* |
| Protection | INA226 ALERT + IR2104 SD + firmware | Same layered philosophy plus hardware high-side switches with autonomous current limit (e.g. TPS1H100-Q1) |
| Parts | Commercial | -Q1 minimum for qual units; derating to EEE-INST-002; WCCA formalized |
| Verification | Bench test procedure | Qualification flow: functional → thermal cycle → random vibe → functional; conformal coat; released drawings; harness DWV |

## Interview delivery notes

1. **Open with the honest frame:** "This is a bench instrument I designed, built, and
   validated end-to-end. Here is the documented path from it to a flight power module."
2. **Lead with DR-1/DR-2/DR-3** when asked about debugging or mistakes — a critical doc
   escape, a real-time firmware timing violation, and an inductor saturation escape,
   each with root cause and closure. Root-cause stories beat success stories.
3. **Altium question:** "The repo is KiCad; the transferable skills are hierarchical
   design, DRC discipline, and switching layout. I've walked through Altium's workflow
   and expect days, not months, to be productive." (Then make that true before the
   interview — 2 hours in the Altium trial.)
4. **Numbers to know cold:** ΔIL = Vout(1−D)/(L·f) = 0.45 A; ripple = ΔIL·ESR = 23 mV;
   dead-time 194 ns = 14 counts @ 72 MHz; loop rate 20 kHz, bandwidth ~2 kHz;
   efficiency >88 %; the 1.0 V open-loop vs 60 mV closed-loop load-step delta.
