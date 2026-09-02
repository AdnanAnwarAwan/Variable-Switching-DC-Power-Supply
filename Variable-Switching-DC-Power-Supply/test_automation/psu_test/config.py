"""
Bench configuration, kept out of the test code.

Section 10 of the design document lists "separate test config from code" as a
best practice and then hard-codes VISA resource strings in every script. This
module is that best practice actually applied: resource strings, limits and
pass/fail thresholds live in config/bench.yaml.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import yaml

DEFAULT_CONFIG_PATH = Path(__file__).resolve().parent.parent / "config" / "bench.yaml"


@dataclass
class Limits:
    """Pass/fail thresholds, from the Testing & Validation Framework."""

    v_nominal: float = 12.0
    regulation_percent: float = 0.5      # Phase 5A
    efficiency_percent: float = 88.0     # Phase 5C target at 12 V / 5 A
    ripple_mvpp: float = 30.0            # Phase 5A
    settling_time_ms: float = 1.0        # Phase 5B
    overshoot_percent: float = 5.0       # Phase 5B
    ovp_response_us: float = 20.0        # Phase 6
    ocp_alert_response_us: float = 10.0  # Phase 6
    i_max: float = 5.0
    v_max: float = 30.0
    v_min: float = 1.25


@dataclass
class BenchConfig:
    """Everything the harness needs to find and safely drive the bench."""

    psu: str = "USB0::0x1AB1::0x0E11::DP8C000000000::INSTR"
    load: str = "GPIB0::5::INSTR"
    dmm: str = "USB0::0x2A8D::0x1301::MY00000000::INSTR"
    scope: str = "USB0::0x1AB1::0x04CE::DS1Z000000000::INSTR"
    stm32_port: str | None = "/dev/ttyUSB0"
    baudrate: int = 115200

    dc_bus_voltage: float = 45.0
    dc_bus_current_limit: float = 2.5
    psu_channel: int = 1
    settle_delay_s: float = 0.5
    dmm_averages: int = 8

    simulate: bool = False
    limits: Limits = field(default_factory=Limits)

    @classmethod
    def load_file(cls, path: str | Path | None = None) -> "BenchConfig":
        path = Path(path) if path else DEFAULT_CONFIG_PATH
        if not path.exists():
            raise FileNotFoundError(
                f"No bench config at {path}. Copy config/bench.example.yaml "
                "to config/bench.yaml and fill in your VISA resource strings "
                "(run `python -m psu_test.discover` to list them)."
            )
        raw = yaml.safe_load(path.read_text()) or {}
        limits = Limits(**(raw.pop("limits", {}) or {}))
        return cls(limits=limits, **raw)

    def sanity_check(self) -> None:
        """Fail fast on a config that would command the DUT out of spec."""
        lim = self.limits
        if not lim.v_min <= lim.v_nominal <= lim.v_max:
            raise ValueError(
                f"v_nominal {lim.v_nominal} V is outside the design envelope "
                f"{lim.v_min}-{lim.v_max} V"
            )
        if self.dc_bus_voltage <= lim.v_nominal:
            raise ValueError(
                f"DC bus {self.dc_bus_voltage} V must exceed the output "
                f"setpoint {lim.v_nominal} V — a buck converter cannot step up"
            )
        headroom = self.dc_bus_current_limit * self.dc_bus_voltage
        needed = lim.v_nominal * lim.i_max / 0.80  # assume 80% worst case
        if headroom < needed:
            raise ValueError(
                f"DC bus current limit {self.dc_bus_current_limit} A at "
                f"{self.dc_bus_voltage} V gives {headroom:.0f} W, but full "
                f"load needs about {needed:.0f} W. The supply will drop into "
                "current limit and every efficiency point will be wrong."
            )
