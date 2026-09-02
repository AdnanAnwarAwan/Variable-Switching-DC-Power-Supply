"""
Block 6 — Oscilloscope.

THE IMPORTANT FIX IN THIS FILE: the design document's `get_waveform` returns
the raw byte buffer and the transient script then plots those bytes directly,
labelling the y-axis "Output Voltage (raw)" and building the time axis as
`np.linspace(0, len(v) * 100e-6, len(v))`.

Both halves of that are wrong:
  * Raw bytes are 0-255 ADC codes. Volts require the waveform preamble:
        V = (code - Y_ORIGIN - Y_REFERENCE) * Y_INCREMENT
  * 100e-6 is the *per-division* timebase, not the per-sample interval. A
    1200-point Rigol record spans 12 divisions = 1.2 ms, but that formula
    produces 120 ms — a 100x error. Sample spacing is X_INCREMENT from the
    same preamble.

An overshoot or settling-time number computed from the document's version is
off by two orders of magnitude on the time axis and has no volts axis at all.
`get_waveform_scaled` below returns (time_seconds, volts) with the trigger
at t = 0.
"""

from __future__ import annotations

import numpy as np

from .base import BenchInstrument, InstrumentError


class Oscilloscope(BenchInstrument):
    """Time-domain capture for gate drive, SW node, ripple and transients."""

    kind = "scope"

    # ── setup ─────────────────────────────────────────────────────────
    def autoscale(self) -> None:
        self.write(":AUToscale")

    def set_timebase(self, seconds_per_div: float) -> None:
        self.write(f":TIMebase:MAIN:SCALe {seconds_per_div}")

    def set_timebase_offset(self, seconds: float) -> None:
        """Negative offset puts the trigger later in the record (pre-trigger)."""
        self.write(f":TIMebase:MAIN:OFFSet {seconds}")

    def set_channel_scale(self, ch: int, volts_per_div: float) -> None:
        self.write(f":CHANnel{ch}:SCALe {volts_per_div}")

    def set_channel_offset(self, ch: int, volts: float) -> None:
        self.write(f":CHANnel{ch}:OFFSet {volts}")

    def set_coupling(self, ch: int, coupling: str = "DC") -> None:
        coupling = coupling.upper()
        if coupling not in {"AC", "DC", "GND"}:
            raise ValueError(f"Bad coupling {coupling!r}")
        self.write(f":CHANnel{ch}:COUPling {coupling}")

    def set_bandwidth_limit(self, ch: int, on: bool = True) -> None:
        """20 MHz BW limit — required by the framework doc for ripple work."""
        self.write(f":CHANnel{ch}:BWLimit {'20M' if on else 'OFF'}")

    def configure_edge_trigger(self, ch: int, level: float,
                               slope: str = "NEGative") -> None:
        """
        Arm an edge trigger.

        Guard rail: an AC-coupled channel is centred on 0 V, so a trigger
        level of 11.5 V on an AC-coupled Vout (as the design document's
        transient script specifies) can never fire. This raises instead of
        hanging in SINGLE forever.
        """
        coupling = self.query(f":CHANnel{ch}:COUPling?").upper()
        if coupling.startswith("AC") and abs(level) > 5:
            raise ValueError(
                f"Trigger level {level} V on AC-coupled CH{ch}: an AC-coupled "
                "trace sits at 0 V, so this will never trigger. Either use DC "
                "coupling with an offset, or trigger on the load-step current "
                "channel / the load's TRIG OUT."
            )
        self.write(f":TRIGger:MODE EDGE")
        self.write(f":TRIGger:EDGe:SOURce CHANnel{ch}")
        self.write(f":TRIGger:EDGe:SLOPe {slope}")
        self.write(f":TRIGger:EDGe:LEVel {level}")

    # ── acquisition ───────────────────────────────────────────────────
    def run(self) -> None:
        self.write(":RUN")

    def stop(self) -> None:
        self.write(":STOP")

    def single(self) -> None:
        self.write(":SINGle")

    def trigger_status(self) -> str:
        return self.query(":TRIGger:STATus?").upper()

    def wait_for_trigger(self, timeout_s: float = 10.0,
                         poll_s: float = 0.05) -> bool:
        """
        Poll until the scope reports STOP (acquisition complete).

        The design document's transient script uses `time.sleep(0.1)` and then
        reads the buffer. If the trigger has not fired yet you download the
        previous acquisition and never know.
        """
        import time  # noqa: PLC0415

        deadline = time.monotonic() + timeout_s
        while time.monotonic() < deadline:
            if self.trigger_status().startswith("STOP"):
                return True
            time.sleep(poll_s)
        return False

    # ── built-in measurements ─────────────────────────────────────────
    def measure_vpp(self, ch: int) -> float:
        return self.query_float(f":MEASure:VPP? CHANnel{ch}")

    def measure_frequency(self, ch: int) -> float:
        return self.query_float(f":MEASure:FREQuency? CHANnel{ch}")

    def measure_ripple_vpp(self, ch: int, *, bw_limit: bool = True) -> float:
        """
        Ripple per the framework doc: AC coupled, 20 MHz BW limit.

        Still requires the physical ground-spring technique — a 6 inch probe
        ground lead will show you switching-noise pickup, not output ripple,
        and will typically read several times the true value.
        """
        self.set_coupling(ch, "AC")
        self.set_bandwidth_limit(ch, bw_limit)
        return self.measure_vpp(ch)

    # ── raw waveform ──────────────────────────────────────────────────
    def get_waveform(self, ch: int) -> list[int]:
        """Raw byte buffer, as in the design document. Prefer the scaled form."""
        self.write(f":WAVeform:SOURce CHANnel{ch}")
        self.write(":WAVeform:MODE NORMal")
        self.write(":WAVeform:FORMat BYTE")
        return self.inst.query_binary_values(":WAVeform:DATA?", datatype="B")

    def get_preamble(self, ch: int) -> dict:
        """
        Parse :WAVeform:PREamble? into scaling factors.

        Rigol/Keysight field order:
        format, type, points, count, xincrement, xorigin, xreference,
        yincrement, yorigin, yreference
        """
        self.write(f":WAVeform:SOURce CHANnel{ch}")
        fields = self.query(":WAVeform:PREamble?").split(",")
        if len(fields) < 10:
            raise InstrumentError(
                f"Preamble returned {len(fields)} fields, expected >= 10"
            )
        return {
            "format": int(float(fields[0])),
            "type": int(float(fields[1])),
            "points": int(float(fields[2])),
            "count": int(float(fields[3])),
            "xincrement": float(fields[4]),
            "xorigin": float(fields[5]),
            "xreference": float(fields[6]),
            "yincrement": float(fields[7]),
            "yorigin": float(fields[8]),
            "yreference": float(fields[9]),
        }

    def get_waveform_scaled(self, ch: int) -> tuple[np.ndarray, np.ndarray]:
        """
        Return (t_seconds, v_volts). t = 0 is the trigger instant.

        This is the function every downstream analysis should call.
        """
        self.write(f":WAVeform:SOURce CHANnel{ch}")
        self.write(":WAVeform:MODE NORMal")
        self.write(":WAVeform:FORMat BYTE")
        pre = self.get_preamble(ch)
        raw = np.asarray(
            self.inst.query_binary_values(":WAVeform:DATA?", datatype="B"),
            dtype=float,
        )
        volts = (raw - pre["yorigin"] - pre["yreference"]) * pre["yincrement"]
        idx = np.arange(raw.size, dtype=float)
        t = (idx - pre["xreference"]) * pre["xincrement"] + pre["xorigin"]
        return t, volts
