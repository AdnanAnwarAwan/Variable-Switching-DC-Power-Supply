"""
Block 3 — Programmable DC power supply.

NOTE ON THE DOCUMENTED EXAMPLE: the design document names a Rigol DP832 and
then commands it to 45 V. A DP832 tops out at 30 V on CH1/CH2 and 5 V on
CH3, so that combination cannot exist. `set_voltage` therefore enforces a
per-model channel envelope and raises before the command is sent, rather
than letting the supply silently clamp and every downstream efficiency
number come out wrong.

Use a supply that actually reaches the DC-bus voltage you intend to inject
(e.g. Keysight E3634A 50 V/4 A, or a 60 V/5 A Korad/Rigol DP811-class unit)
for Phase 3 bring-up at 45 V.
"""

from __future__ import annotations

from .base import BenchInstrument

#: (min_v, max_v, max_i) per channel, keyed by model substring in *IDN?.
CHANNEL_LIMITS = {
    "DP832": {1: (0.0, 30.0, 3.0), 2: (0.0, 30.0, 3.0), 3: (0.0, 5.0, 3.0)},
    "DP811": {1: (0.0, 20.0, 10.0), 2: (0.0, 40.0, 5.0)},
    "E3634A": {1: (0.0, 50.0, 4.0)},
}
#: Used when the model is unknown or simulated.
DEFAULT_LIMITS = {1: (0.0, 60.0, 5.0), 2: (0.0, 60.0, 5.0), 3: (0.0, 60.0, 5.0)}


class DCPowerSupply(BenchInstrument):
    """Bench DC supply used to inject a controlled DC bus into the DUT."""

    kind = "psu"

    def __init__(self, resource_string: str, *, simulate: bool = False,
                 limits: dict | None = None, **kw):
        super().__init__(resource_string, simulate=simulate, **kw)
        self.limits = limits if limits is not None else self._detect_limits()

    def _detect_limits(self) -> dict:
        try:
            idn = self.idn().upper()
        except Exception:  # noqa: BLE001 - unknown model is not fatal
            return DEFAULT_LIMITS
        for model, lim in CHANNEL_LIMITS.items():
            if model in idn:
                return lim
        return DEFAULT_LIMITS

    def _check(self, channel: int, voltage: float | None = None,
               current: float | None = None) -> None:
        if channel not in self.limits:
            raise ValueError(f"Channel {channel} does not exist on this supply")
        vmin, vmax, imax = self.limits[channel]
        if voltage is not None and not (vmin <= voltage <= vmax):
            raise ValueError(
                f"{voltage} V is outside CH{channel} range {vmin}-{vmax} V. "
                "This supply cannot produce the requested DC bus."
            )
        if current is not None and not (0 <= current <= imax):
            raise ValueError(
                f"{current} A is outside CH{channel} limit of {imax} A"
            )

    # ── setpoints ─────────────────────────────────────────────────────
    def set_voltage(self, channel: int, voltage: float) -> None:
        self._check(channel, voltage=voltage)
        self.write(f":SOURce{channel}:VOLTage {voltage}")

    def set_current(self, channel: int, current: float) -> None:
        """Set the current *limit* (compliance), not a forced current."""
        self._check(channel, current=current)
        self.write(f":SOURce{channel}:CURRent {current}")

    def output_on(self, channel: int) -> None:
        self.write(f":OUTPut CH{channel},ON")

    def output_off(self, channel: int) -> None:
        self.write(f":OUTPut CH{channel},OFF")

    def all_outputs_off(self) -> None:
        for ch in self.limits:
            try:
                self.output_off(ch)
            except Exception:  # noqa: BLE001 - best-effort safety shutdown
                pass

    # ── readback ──────────────────────────────────────────────────────
    def measure_voltage(self, channel: int) -> float:
        return self.query_float(f":MEASure:VOLTage:DC? CH{channel}")

    def measure_current(self, channel: int) -> float:
        return self.query_float(f":MEASure:CURRent:DC? CH{channel}")

    def measure_power(self, channel: int) -> float:
        """Input power P_in = V_in x I_in, from the supply's own sense."""
        return self.measure_voltage(channel) * self.measure_current(channel)

    def in_current_limit(self, channel: int, tolerance: float = 0.02) -> bool:
        """
        True if the supply has fallen out of CV into CC.

        Efficiency data taken while the source is in current limit is
        meaningless — the DUT is being starved, not regulated.
        """
        prog = self.query_float(f":SOURce{channel}:CURRent?")
        return self.measure_current(channel) >= prog * (1 - tolerance)
