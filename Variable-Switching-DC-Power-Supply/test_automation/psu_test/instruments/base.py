"""
Block 2 — Generic instrument class.

Adds three things the design document's version left out:
  * context-manager support, so a crashed test still closes the VISA session;
  * an `expect_float` query that raises a typed error instead of letting a
    ValueError from float() surface with no instrument context;
  * `opc()` — a *OPC? synchronisation barrier. Without it, a set_voltage()
    followed immediately by a measurement can read the pre-change value on
    instruments that buffer commands.
"""

from __future__ import annotations

import logging

from ..session import open_resource

log = logging.getLogger(__name__)


class InstrumentError(RuntimeError):
    """Raised when an instrument returns something unparseable."""


class BenchInstrument:
    """Base wrapper around a SCPI-speaking bench instrument."""

    #: Human name used in logs and error messages.
    kind = "instrument"

    def __init__(self, resource_string: str, *, simulate: bool = False,
                 timeout_ms: int = 5000):
        self.resource_string = resource_string
        self.simulate = simulate
        self.inst = open_resource(resource_string, simulate=simulate,
                                  timeout_ms=timeout_ms)

    # ── plumbing ──────────────────────────────────────────────────────
    def write(self, cmd: str) -> None:
        log.debug("%s <- %s", self.kind, cmd)
        self.inst.write(cmd)

    def query(self, cmd: str) -> str:
        resp = self.inst.query(cmd).strip()
        log.debug("%s -> %s", self.kind, resp)
        return resp

    def query_float(self, cmd: str) -> float:
        raw = self.query(cmd)
        try:
            return float(raw)
        except ValueError as exc:
            raise InstrumentError(
                f"{self.kind} at {self.resource_string} returned "
                f"{raw!r} for {cmd!r}, expected a number"
            ) from exc

    # ── IEEE-488 common commands ──────────────────────────────────────
    def idn(self) -> str:
        return self.query("*IDN?")

    def reset(self) -> None:
        self.write("*RST")
        self.opc()

    def clear_status(self) -> None:
        self.write("*CLS")

    def opc(self) -> None:
        """Block until the instrument has finished pending operations."""
        self.query("*OPC?")

    # ── lifecycle ─────────────────────────────────────────────────────
    def close(self) -> None:
        try:
            self.inst.close()
        except Exception:  # noqa: BLE001 - closing must never mask a test error
            log.warning("Failed to close %s", self.resource_string, exc_info=True)

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()
        return False

    def __repr__(self) -> str:
        tag = " [SIM]" if self.simulate else ""
        return f"<{type(self).__name__} {self.resource_string}{tag}>"
