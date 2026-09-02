"""
Resource layer: opens either a real PyVISA resource or a simulated one.

Everything above this module talks to an object with .write(), .query(),
.query_binary_values() and .close(). That is the entire contract, which is
what makes `--simulate` possible without touching any test logic.

PyVISA and pyserial are imported lazily so the simulated path runs on a
machine with no instrument drivers installed.
"""

from __future__ import annotations

import logging
from typing import Any, Protocol

log = logging.getLogger(__name__)


class Resource(Protocol):
    """Minimal duck-type shared by pyvisa resources and SimResource."""

    def write(self, cmd: str) -> Any: ...
    def query(self, cmd: str) -> str: ...
    def query_binary_values(self, cmd: str, datatype: str = "B") -> list: ...
    def close(self) -> None: ...


_SIM_REGISTRY: dict[str, Any] = {}


def register_simulated(resource_string: str, sim_obj: Any) -> None:
    """Bind a resource string to a simulated instrument instance."""
    _SIM_REGISTRY[resource_string] = sim_obj


def clear_simulated() -> None:
    _SIM_REGISTRY.clear()


def open_resource(resource_string: str, *, simulate: bool = False,
                  timeout_ms: int = 5000) -> Resource:
    """
    Open a VISA resource by string.

    simulate=True looks the string up in the simulation registry instead of
    touching hardware. Raises KeyError if nothing is registered under it,
    which is deliberate: a silent fallback to a fake instrument during a real
    bench run would produce plausible-looking but fabricated test data.
    """
    if simulate:
        if resource_string not in _SIM_REGISTRY:
            raise KeyError(
                f"No simulated instrument registered for {resource_string!r}. "
                "Call psu_test.simulator.build_bench() first."
            )
        log.debug("Opening SIMULATED resource %s", resource_string)
        return _SIM_REGISTRY[resource_string]

    import pyvisa  # noqa: PLC0415 - lazy so simulation needs no VISA install

    rm = pyvisa.ResourceManager()
    inst = rm.open_resource(resource_string)
    inst.timeout = timeout_ms
    log.debug("Opening REAL resource %s", resource_string)
    return inst


def open_serial(port: str, baudrate: int = 115200, timeout: float = 1.0,
                *, simulate: bool = False):
    """Open a serial port, or return the registered simulated STM32."""
    if simulate:
        if port not in _SIM_REGISTRY:
            raise KeyError(
                f"No simulated serial device registered for {port!r}."
            )
        return _SIM_REGISTRY[port]

    import serial  # noqa: PLC0415

    return serial.Serial(port, baudrate, timeout=timeout)
