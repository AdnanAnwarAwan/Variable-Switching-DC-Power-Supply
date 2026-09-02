"""
Block 4 — Programmable electronic load.

Additions over the documented version:
  * `max_current` guard so a typo cannot command 50 A into a 5 A design;
  * `set_transient` for the Phase 5B load-step test — stepping current by
    re-issuing CURRent in a Python loop gives you a step edge governed by
    USB latency (~1-10 ms), which is 100x too slow to measure a converter
    whose spec is "settling < 1 ms". The load's own transient generator
    produces the <10 us edge the framework document asks for.
"""

from __future__ import annotations

from .base import BenchInstrument


class ElectronicLoad(BenchInstrument):
    """Constant-current sink used for regulation, efficiency and transients."""

    kind = "eload"

    def __init__(self, resource_string: str, *, simulate: bool = False,
                 max_current: float = 6.0, **kw):
        super().__init__(resource_string, simulate=simulate, **kw)
        self.max_current = max_current

    # ── mode / setpoint ───────────────────────────────────────────────
    def set_mode(self, mode: str = "CURRENT") -> None:
        mode = mode.upper()
        if mode not in {"CURRENT", "VOLTAGE", "RESISTANCE", "POWER"}:
            raise ValueError(f"Unsupported load mode {mode!r}")
        self.write(f":SOURce:FUNCtion {mode}")

    def set_current(self, current: float) -> None:
        if not 0 <= current <= self.max_current:
            raise ValueError(
                f"{current} A exceeds the configured load ceiling of "
                f"{self.max_current} A"
            )
        self.write(f":SOURce:CURRent {current}")

    def set_slew_rate(self, amps_per_us: float) -> None:
        """Current slew for the load step. 0.5 A/us gives a 10 us 0->5 A edge."""
        self.write(f":SOURce:CURRent:SLEW {amps_per_us}")

    def set_transient(self, low: float, high: float, frequency: float,
                      duty_percent: float = 50.0) -> None:
        """
        Configure the load's built-in transient generator (list/pulse mode).

        This is what produces a genuine fast load step. `trigger_transient`
        arms it; the scope should be triggered from the load's TRIG OUT or
        from the current-monitor channel, not from a Python timestamp.
        """
        for value in (low, high):
            if not 0 <= value <= self.max_current:
                raise ValueError(f"{value} A exceeds load ceiling")
        self.write(":SOURce:CURRent:MODE TRANsient")
        self.write(f":SOURce:CURRent:TRANsient:ALOW {low}")
        self.write(f":SOURce:CURRent:TRANsient:AHIGh {high}")
        self.write(f":SOURce:CURRent:TRANsient:FREQuency {frequency}")
        self.write(f":SOURce:CURRent:TRANsient:DCYCle {duty_percent}")

    def trigger_transient(self) -> None:
        self.write(":TRIGger:TRANsient")

    # ── connection ────────────────────────────────────────────────────
    def input_on(self) -> None:
        self.write(":INPut ON")

    def input_off(self) -> None:
        self.write(":INPut OFF")

    # ── readback ──────────────────────────────────────────────────────
    def measure_voltage(self) -> float:
        return self.query_float(":MEASure:VOLTage:DC?")

    def measure_current(self) -> float:
        return self.query_float(":MEASure:CURRent:DC?")

    def measure_power(self) -> float:
        """Output power P_out at the load terminals."""
        return self.measure_voltage() * self.measure_current()
