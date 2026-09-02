"""
Test and validation harness for the Variable Switching DC Power Supply.

Implements the thirteen code blocks described in docs/Python_Code_Descriptions.pdf
and the phase gates in docs/Testing_and_Validation_Framework.pdf, with the
errors in those documents corrected (see README.md, "Deviations from the
design documents").
"""

from .analysis import (
    TransientResult,
    analyse_transient,
    efficiency_percent,
    line_regulation_percent,
    load_regulation_percent,
    response_time_s,
    ripple_vpp,
    setpoint_error_percent,
)
from .config import BenchConfig, Limits
from .instruments import DCPowerSupply, DMM, ElectronicLoad, Oscilloscope
from .telemetry import STM32Telemetry, TelemetrySample, parse_line

__version__ = "0.1.0"

__all__ = [
    "BenchConfig",
    "Limits",
    "DCPowerSupply",
    "ElectronicLoad",
    "DMM",
    "Oscilloscope",
    "STM32Telemetry",
    "TelemetrySample",
    "parse_line",
    "TransientResult",
    "analyse_transient",
    "efficiency_percent",
    "load_regulation_percent",
    "line_regulation_percent",
    "setpoint_error_percent",
    "response_time_s",
    "ripple_vpp",
]
