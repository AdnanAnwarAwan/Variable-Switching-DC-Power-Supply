# Test & Validation Harness

Python implementation of the thirteen code blocks in
`docs/Python_Code_Descriptions.pdf` and `docs/Python_Based_Testing_and_Validation.pdf`,
structured around the phase gates in `docs/Testing_and_Validation_Framework.pdf`.

The design documents describe this harness; nothing in the repository
implemented it. This directory is that implementation, with the errors in
those documents fixed rather than transcribed. Every deviation is listed at
the bottom of this file.

---

## Run it right now, with no hardware

```bash
pip install -r requirements.txt
python scripts/run_bench.py all --simulate --report --yes --outdir results
pytest
```

`--simulate` swaps a behavioural model of the converter and four fake SCPI
instruments in behind the same interfaces. Every script, plot, CSV and Word
report is produced end-to-end. This exists because none of the code in the
design documents could ever have been executed — it needs four instruments
and a built board — which is precisely why its bugs survived into the PDFs.

A simulated run is stamped `[SIMULATED]` on every plot and in the report
heading. Simulated output must never be presentable as measured data.

## Run it against real hardware

```bash
python -m psu_test.discover                     # list VISA resources
cp config/bench.example.yaml config/bench.yaml  # paste them in
python scripts/run_bench.py regulation          # prompts before energising
pytest --hardware --bench-config config/bench.yaml
```

---

## Layout

| Path | Doc block | Contents |
|---|---|---|
| `psu_test/discover.py` | 1 | VISA resource discovery with `*IDN?` identification |
| `psu_test/instruments/base.py` | 2 | `BenchInstrument`: SCPI plumbing, `*OPC?` sync, context manager |
| `psu_test/instruments/psu.py` | 3 | DC supply, with a per-model voltage/current envelope check |
| `psu_test/instruments/eload.py` | 4 | Electronic load, including the built-in transient generator |
| `psu_test/instruments/dmm.py` | 5 | DMM with NPLC control and averaged reads that report their own noise |
| `psu_test/instruments/scope.py` | 6 | Scope, incl. preamble-based waveform scaling to real volts and seconds |
| `psu_test/telemetry.py` | 7 | STM32 UART reader, parses both the documented and the actual firmware format |
| `firmware_patch/telemetry.{c,h}` | 8 | Firmware CSV emitter **and** the UART command parser the harness needs |
| `psu_test/procedures.py` | 9, 10, 11 | Load regulation sweep, load transient, OVP injection, ripple |
| `tests/test_bench_regression.py` | 12 | pytest suite, hardware-marked |
| `psu_test/report.py` | 13 | Word report with per-row PASS/FAIL and recorded bench conditions |
| `psu_test/analysis.py` | — | Regulation, efficiency, overshoot, settling, response time (pure functions) |
| `psu_test/simulator.py` | — | Buck model and fake instruments |
| `psu_test/config.py` | — | Bench config, so resource strings are not hard-coded in scripts |

`tests/test_analysis.py` and `tests/test_telemetry.py` need no hardware and
no simulator setup; they are the CI gate.

---

## Deviations from the design documents

These are corrections, not preferences. Each one would produce wrong numbers
or a silent no-op if implemented as written.

### 1. The telemetry parser matches no firmware that exists

The documents specify `Vset,Vmeas,Imeas,Duty,Temp,Status` and parse with
`line.split(',')` requiring six fields. `firmware/Core/Src/main.c` prints:

```
Vset=12.00 Vout=11.98 Iout=2.50 T=41.2C [CV]
```

One field, not six. The documented parser matches nothing, `latest` stays
empty forever, no exception is ever raised, and every telemetry column in
the results CSV comes out blank. A green run with a silently empty column is
the worst available failure mode.

`psu_test/telemetry.py` parses both formats and reports which it detected.
`firmware_patch/telemetry.c` makes the firmware emit the documented CSV.

### 2. The OVP test cannot pass against this firmware, for two reasons

Block 11 sends `SETV 35.0` over the UART and expects an over-voltage trip.

* The firmware never reads the UART. `MX_USART1_Init()` sets `UART_MODE_TX_RX`
  but PA10 is never configured and no RX interrupt or poll exists. The
  command is discarded.
* There is no OVP check anywhere in the firmware. `Fault_Shutdown()` is
  reached only from over-current and over-temperature. Even a parsed command
  would be clamped to `V_MAX = 30.0f` by the setpoint limiter, and nothing
  would trip.

The procedure is implemented, documents this in its own docstring, and the
hardware protection tests are `skip`ped with the reason rather than left to
look passing. `firmware_patch/telemetry.c` supplies the command parser and
shows the ISR-level OVP check to add.

Separately: a firmware-mediated trip runs at the 50 µs control period, so it
**cannot** meet the "< 20 µs" figure in the framework document's Phase 6
table. That needs a hardware comparator on IR2104 `/SD`. Decide which before
that number goes into a report.

### 3. The transient script's time axis is 100× wrong and has no volts axis

Block 10 does:

```python
vout = np.array(scope.get_waveform(1))              # raw 0-255 ADC codes
time_axis = np.linspace(0, len(vout) * 100e-6, len(vout))
```

`100e-6` is the timebase **per division**, not per sample. A 1200-point
record on 12 divisions spans 1.2 ms; that formula returns 120 ms. And raw
bytes are not volts. Settling time and overshoot computed from this are
unusable, which is why the plot is labelled "Output Voltage (raw)".

`scope.get_waveform_scaled()` reads `:WAVeform:PREamble?` and returns
`(seconds, volts)` with the trigger at t=0, using
`V = (code − Y_ORIGIN − Y_REFERENCE) × Y_INCREMENT` and `X_INCREMENT` for
sample spacing.

### 4. The transient trigger can never fire

Block 10 sets CH1 to 0.5 V/div **AC coupled** and then triggers on a level of
11.5 V. An AC-coupled trace is centred on 0 V; the level is unreachable and
`:SINGle` waits forever. `configure_edge_trigger()` raises on this
combination instead. The scope is also polled to confirm the trigger
actually fired — the documented script sleeps 100 ms and downloads whatever
is in the buffer, which may be the previous acquisition.

### 5. The load step is generated 100× too slowly to measure

Stepping current by re-issuing `CURRent` from Python gives an edge governed
by USB/GPIB latency, roughly 1–10 ms. The spec being measured is "settling
< 1 ms". The harness uses the load's own transient generator and slew-rate
setting for a ~10 µs edge.

### 6. A Rigol DP832 cannot produce 45 V

Block 9 names a DP832 and commands `set_voltage(1, 45.0)`. The DP832 is
30 V max on CH1/CH2, 5 V on CH3. On real hardware it clamps at 30 V, the
converter runs from the wrong bus, and every efficiency figure is wrong with
no error raised. `DCPowerSupply` carries a per-model envelope and refuses
before sending. Use a supply that actually reaches 45 V (E3634A, DP811 CH2
at reduced bus, or similar).

### 7. Load regulation was being computed as setpoint error

The report code uses `abs(min_v - 12) / 12 * 100` and labels it load
regulation. That is accuracy against the setpoint. Load regulation is the
**spread across the sweep**:

```
(V_max − V_min) / V_nominal × 100
```

A supply sitting 0.4% low but perfectly flat has excellent load regulation
and mediocre calibration. The documented formula scores it as a regulation
failure and sends you tuning the PID when the fix is the sense divider.
`analysis.py` computes and reports both, separately.

### 8. `test_efficiency_full_load` is `pass`

A test body of `pass` produces a green checkmark that measures nothing —
worse than no test, because it appears in a report as evidence. It is
implemented here, and includes an `efficiency <= 100%` assertion: a
converter reading 103% has a wiring or shunt-calibration error, and a
harness that reports it as an excellent result is not doing its job.

### 9. The pytest tests assert on a state they never establish

`test_voltage_accuracy_12V` asserts the DMM reads 12 V without ever
commanding 12 V. It is really asserting "whatever the DUT was last set to".
`test_load_regulation_5A` then leaves the load at 5 A and input on, so every
test after it silently inherits full load. The `dut_at_nominal` fixture sets
preconditions, and an autouse fixture unloads between tests.

The document's fixture also loses its teardown entirely if instrument
construction raises: the `yield` is never reached, and anything that did
open is left energised. `conftest.py` uses `ExitStack`, registering each
`close()` at the moment it opens.

### 10. Ripple is assigned to the wrong instrument

Section 5A lists the DMM as the ripple tool. A 34461A's DC path integrates
over hundreds of milliseconds; 30 mVpp of 200 kHz ripple averages to roughly
zero in it and will report a pass regardless of how bad the ripple is.
Ripple is a scope measurement, AC coupled with the 20 MHz bandwidth limit —
`procedures.ripple_measurement()`. Probe grounding dominates the result;
without a ground spring you are measuring pickup.

### 11. Smaller ones

* `efficiency` returns 0 when P_in ≤ 0 in the documents. 0 plots as a real
  datum and drags any `min()` to zero. NaN is returned instead. No-load
  efficiency is likewise NaN, not 0%: the converter is doing no work, not
  doing it badly.
* Settling time is measured to the **last** exit from the settling band. To
  the first entry, a ringing supply looks settled at its first crossing.
* The teardown order in Block 9 is safe by luck; here the load is
  disconnected before the source, explicitly.
* The documents recommend human-in-the-loop gates for dangerous tests and
  then never implement one. `run_bench.py` confirms before energising unless
  `--yes` is passed.
* The documents recommend separating config from code and then hard-code
  VISA strings in every script. `config/bench.yaml` holds them.
* The sweep checks whether the bench supply has fallen into current limit at
  each point. Efficiency measured while the source is in CC is fiction.
* The DMM read is averaged and its standard deviation recorded, so a noisy
  point is visible in the data instead of hidden behind a single reading.

---

## Honest limits of this work

* **Every number produced so far is simulated.** The buck model is a droop
  term, a loss model and a second-order step response — enough to exercise
  the harness, not a converter model. `simulation/buck_powerstage.cir` is
  the tool for circuit questions. No claim about the real hardware follows
  from any output in `results/`.
* **The instrument wrappers are written against documented SCPI, not tested
  against metal.** Command syntax varies between models even within a
  vendor's line. Expect to fix strings during first bring-up; that is what
  `--verbose` logs are for.
* **The firmware patch has not been compiled or flashed.** It is written
  against the HAL calls already used in `main.c`, but it has not been near a
  toolchain or a board.
* **`Test_Report.docx` is not a Phase 8 deliverable.** The framework document
  requires instrument serial numbers and calibration dates, ambient
  conditions, and a calibration certificate. The report records what the
  harness can observe automatically; the rest has to be entered by a human
  who was in the room.
