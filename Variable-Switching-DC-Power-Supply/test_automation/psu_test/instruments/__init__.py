"""Instrument wrappers (design document blocks 2-6)."""

from .base import BenchInstrument, InstrumentError
from .dmm import DMM
from .eload import ElectronicLoad
from .psu import DCPowerSupply
from .scope import Oscilloscope

__all__ = [
    "BenchInstrument",
    "InstrumentError",
    "DCPowerSupply",
    "ElectronicLoad",
    "DMM",
    "Oscilloscope",
]
