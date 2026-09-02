"""
Block 5 — Digital multimeter, the golden reference for DC accuracy.

Additions over the documented version:
  * explicit NPLC control. A 34461A defaults to 10 NPLC on *RST, which is
    ~200 ms per reading at 50 Hz — fine for accuracy, painful in a 100-point
    sweep. Setting it consciously makes the accuracy/speed trade visible.
  * `read_averaged` with standard deviation, so a noisy reading is reported
    as noisy instead of being silently rounded into a pass.
  * NOTE: the design document lists the DMM as the instrument for ripple
    measurement. It is not. A 34461A's DC path is a several-hundred-ms
    integrator; 30 mVpp of 200 kHz ripple averages to approximately zero in
    it. Ripple is a scope measurement — see scope.measure_ripple_vpp().
"""

from __future__ import annotations

import statistics

from .base import BenchInstrument


class DMM(BenchInstrument):
    """High-accuracy DC voltage / resistance reference meter."""

    kind = "dmm"

    def configure_dc_voltage(self, range_val: float | str = 10,
                             nplc: float = 1.0) -> None:
        """
        Set DC volts range and integration time.

        range_val may be a number or "AUTO". Fixing the range is preferred in
        a sweep: autoranging adds a range-change delay mid-measurement and can
        land you on a different accuracy spec between points.
        """
        rng = "AUTO" if str(range_val).upper() == "AUTO" else f"{float(range_val)}"
        self.write(f"CONFigure:VOLTage:DC {rng}")
        self.write(f"SENSe:VOLTage:DC:NPLC {nplc}")

    def configure_4wire_resistance(self, range_val: float | str = "AUTO") -> None:
        """4-wire Kelvin resistance — for shunt and trace resistance."""
        rng = "AUTO" if str(range_val).upper() == "AUTO" else f"{float(range_val)}"
        self.write(f"CONFigure:FRESistance {rng}")

    def read(self) -> float:
        return self.query_float("READ?")

    def read_averaged(self, n: int = 8) -> tuple[float, float]:
        """
        Return (mean, sample stdev) over n readings.

        The stdev is the useful half: if it is a large fraction of your
        +/-0.5% regulation window, the mean is not evidence of anything.
        """
        if n < 2:
            raise ValueError("read_averaged needs n >= 2 to report a stdev")
        samples = [self.read() for _ in range(n)]
        return statistics.fmean(samples), statistics.stdev(samples)
