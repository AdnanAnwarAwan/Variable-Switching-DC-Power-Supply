"""
Block 7 — STM32 serial telemetry reader.

FORMAT MISMATCH, READ THIS FIRST
--------------------------------
The design document specifies a CSV line:

    Vset,Vmeas,Imeas,Duty,Temp,Status

The firmware in firmware/Core/Src/main.c actually emits, at 10 Hz:

    Vset=12.00 Vout=11.98 Iout=2.50 T=41.2C [CV]

These are not the same thing. The document's parser does
`line.split(',')` and requires exactly 6 fields, so against the real
firmware it produces one field, matches nothing, and `latest` stays empty
forever — every telemetry column in the results CSV comes out as None and
no error is ever raised. That is the worst failure mode available: a green
test run with a silently blank column.

Two further gaps against the document:
  * duty cycle is never transmitted by the firmware, so the PID duty column
    the document promises cannot be populated at all;
  * there is no OK/FAULT token in the periodic line. `FAULT: <reason>` is
    printed once, asynchronously, by Fault_Shutdown().

This reader handles both formats and reports which one it saw. To get the
documented CSV (and the duty cycle), apply firmware_patch/telemetry.c.

Also fixed here: the document's `_read_loop` catches Exception and prints,
inside a `while self.running` loop with no delay. A disconnected USB-serial
adapter turns that into an unbounded error-printing spin. This version
counts errors and stops after a threshold.
"""

from __future__ import annotations

import logging
import queue
import re
import threading
import time
from dataclasses import dataclass, field

from .session import open_serial

log = logging.getLogger(__name__)

#: Vset=12.00 Vout=11.98 Iout=2.50 T=41.2C [CV]
_KV_RE = re.compile(
    r"Vset=(?P<v_set>-?[\d.]+)\s+"
    r"Vout=(?P<v_meas>-?[\d.]+)\s+"
    r"Iout=(?P<i_meas>-?[\d.]+)\s+"
    r"T=(?P<temp>-?[\d.]+)C\s+"
    r"\[(?P<mode>CV|CC)\]"
)
_FAULT_RE = re.compile(r"FAULT:\s*(?P<reason>.+)")


@dataclass
class TelemetrySample:
    """One decoded telemetry line."""

    t: float
    v_set: float
    v_meas: float
    i_meas: float
    duty: float | None = None
    temp: float | None = None
    status: str = "OK"
    mode: str | None = None          # "CV" / "CC" where available
    source_format: str = "unknown"   # "csv" | "keyvalue"
    raw: str = ""

    def as_dict(self) -> dict:
        return {
            "telem_t": self.t,
            "v_set_stm32": self.v_set,
            "v_meas_stm32": self.v_meas,
            "i_meas_stm32": self.i_meas,
            "duty_stm32": self.duty,
            "temp_stm32": self.temp,
            "status_stm32": self.status,
            "mode_stm32": self.mode,
        }


def parse_line(line: str) -> TelemetrySample | None:
    """
    Decode one telemetry line in either supported format.

    Returns None for banner text, blank lines and anything unrecognised.
    """
    line = line.strip()
    if not line:
        return None

    # Documented CSV: Vset,Vmeas,Imeas,Duty,Temp,Status
    parts = [p.strip() for p in line.split(",")]
    if len(parts) == 6:
        try:
            return TelemetrySample(
                t=time.time(),
                v_set=float(parts[0]),
                v_meas=float(parts[1]),
                i_meas=float(parts[2]),
                duty=float(parts[3]),
                temp=float(parts[4]),
                status=parts[5].upper(),
                source_format="csv",
                raw=line,
            )
        except ValueError:
            return None

    # Firmware's actual key=value line.
    m = _KV_RE.search(line)
    if m:
        g = m.groupdict()
        return TelemetrySample(
            t=time.time(),
            v_set=float(g["v_set"]),
            v_meas=float(g["v_meas"]),
            i_meas=float(g["i_meas"]),
            duty=None,                       # not transmitted by this firmware
            temp=float(g["temp"]),
            status="OK",
            mode=g["mode"],
            source_format="keyvalue",
            raw=line,
        )
    return None


@dataclass
class STM32Telemetry:
    """
    Background reader for the STM32 debug UART (PA9, USART1_TX, 115200 8N1).

    Usage:
        with STM32Telemetry("/dev/ttyUSB0") as t:
            sample = t.get_latest()
    """

    port: str = "/dev/ttyUSB0"
    baudrate: int = 115200
    simulate: bool = False
    max_consecutive_errors: int = 20

    ser: object = field(default=None, init=False, repr=False)
    latest: TelemetrySample | None = field(default=None, init=False)
    data_queue: "queue.Queue[TelemetrySample]" = field(
        default_factory=queue.Queue, init=False, repr=False
    )
    running: bool = field(default=False, init=False)
    detected_format: str | None = field(default=None, init=False)
    fault_events: list = field(default_factory=list, init=False)
    _thread: threading.Thread | None = field(default=None, init=False, repr=False)

    # ── lifecycle ─────────────────────────────────────────────────────
    def start(self) -> "STM32Telemetry":
        self.ser = open_serial(self.port, self.baudrate, timeout=1.0,
                               simulate=self.simulate)
        self.running = True
        self._thread = threading.Thread(target=self._read_loop, daemon=True,
                                        name="stm32-telemetry")
        self._thread.start()
        return self

    def stop(self) -> None:
        self.running = False
        if self._thread is not None:
            self._thread.join(timeout=2.0)
        if self.ser is not None:
            try:
                self.ser.close()
            except Exception:  # noqa: BLE001
                log.warning("Error closing %s", self.port, exc_info=True)

    def __enter__(self) -> "STM32Telemetry":
        return self.start()

    def __exit__(self, *exc):
        self.stop()
        return False

    # ── reader thread ─────────────────────────────────────────────────
    def _read_loop(self) -> None:
        errors = 0
        while self.running:
            try:
                raw = self.ser.readline()
                if not raw:
                    continue
                line = raw.decode("utf-8", errors="replace").strip()
                errors = 0

                fault = _FAULT_RE.search(line)
                if fault:
                    reason = fault.group("reason").strip()
                    self.fault_events.append((time.time(), reason))
                    if self.latest is not None:
                        self.latest.status = "FAULT"
                    log.warning("DUT reported fault: %s", reason)
                    continue

                sample = parse_line(line)
                if sample is None:
                    continue
                if self.detected_format is None:
                    self.detected_format = sample.source_format
                    log.info("Telemetry format detected: %s",
                             sample.source_format)
                self.latest = sample
                self.data_queue.put(sample)
            except Exception:  # noqa: BLE001
                errors += 1
                log.warning("Serial read error (%d/%d)", errors,
                            self.max_consecutive_errors, exc_info=True)
                if errors >= self.max_consecutive_errors:
                    log.error("Giving up on %s after repeated errors", self.port)
                    self.running = False
                    return
                time.sleep(0.1)

    # ── consumer API ──────────────────────────────────────────────────
    def get_latest(self) -> dict:
        """Most recent snapshot as a dict, or empty dict if nothing decoded."""
        return self.latest.as_dict() if self.latest else {}

    def wait_for_sample(self, timeout: float = 2.0) -> TelemetrySample | None:
        """Block for the next fresh sample. Use this instead of sleep()."""
        try:
            return self.data_queue.get(timeout=timeout)
        except queue.Empty:
            return None

    def drain(self) -> list[TelemetrySample]:
        """Pop everything currently queued."""
        out = []
        while True:
            try:
                out.append(self.data_queue.get_nowait())
            except queue.Empty:
                return out

    def send_command(self, command: str) -> None:
        """
        Send an ASCII command to the DUT (e.g. "SETV 12.0").

        Requires firmware_patch/telemetry.c — the stock firmware configures
        USART1 in TX_RX mode but never reads the RX register and does not
        route PA10, so commands sent to unpatched firmware are discarded.
        """
        if self.ser is None:
            raise RuntimeError("Telemetry not started")
        self.ser.write((command.rstrip() + "\n").encode("ascii"))

    def wait_for_status(self, status: str, timeout: float = 2.0) -> bool:
        """Wait until a sample reports the given status (e.g. 'FAULT')."""
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            if self.latest and self.latest.status.upper() == status.upper():
                return True
            if self.fault_events and status.upper() == "FAULT":
                return True
            time.sleep(0.01)
        return False
