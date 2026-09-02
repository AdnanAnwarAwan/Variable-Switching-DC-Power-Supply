"""
pytest fixtures for the bench.

The design document's fixture (Block 12) opens three instruments and yields
them, with teardown after the yield. Two problems it does not address:

  1. If DCPowerSupply(...) raises — instrument busy, wrong resource string —
     the yield is never reached, teardown never runs, and any instrument that
     *did* open is left energised. ExitStack below closes whatever opened.

  2. The tests it defines assert on a 12 V output without ever commanding
     12 V. They pass or fail based on whatever the DUT happened to be set to
     when the operator walked away. The `dut_at_nominal` fixture makes the
     precondition explicit.

Hardware tests are marked and deselected by default, so `pytest` on a laptop
runs the analysis and simulator suites and exits clean.
"""

from __future__ import annotations

import contextlib
import sys
import time
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from psu_test.config import BenchConfig                # noqa: E402
from psu_test.instruments import (                     # noqa: E402
    DCPowerSupply, DMM, ElectronicLoad, Oscilloscope,
)
from psu_test.session import clear_simulated           # noqa: E402
from psu_test.simulator import build_bench             # noqa: E402
from psu_test.telemetry import STM32Telemetry          # noqa: E402


def pytest_addoption(parser):
    parser.addoption("--hardware", action="store_true", default=False,
                     help="Run tests that require the physical bench")
    parser.addoption("--bench-config", default=None,
                     help="Path to bench.yaml for hardware runs")


def pytest_configure(config):
    config.addinivalue_line("markers",
                            "hardware: requires the physical bench and DUT")


def pytest_collection_modifyitems(config, items):
    if config.getoption("--hardware"):
        return
    skip = pytest.mark.skip(reason="needs --hardware and a connected bench")
    for item in items:
        if "hardware" in item.keywords:
            item.add_marker(skip)


@pytest.fixture(scope="session")
def config(request) -> BenchConfig:
    """Real bench config when --hardware is given, otherwise simulated."""
    if request.config.getoption("--hardware"):
        cfg = BenchConfig.load_file(request.config.getoption("--bench-config"))
        cfg.simulate = False
    else:
        cfg = BenchConfig()
        cfg.simulate = True
    cfg.settle_delay_s = 0.0 if cfg.simulate else cfg.settle_delay_s
    return cfg


@pytest.fixture(scope="function")
def bench(config):
    """A freshly built simulated bench, or None on hardware runs."""
    if not config.simulate:
        yield None
        return
    clear_simulated()
    yield build_bench(config, csv_telemetry=True, accepts_commands=True)
    clear_simulated()


@pytest.fixture(scope="function")
def instruments(config, bench):
    """
    Open the instrument set with guaranteed cleanup.

    ExitStack registers each close() as soon as the instrument opens, so a
    failure part-way through construction still shuts down what exists.
    """
    with contextlib.ExitStack() as stack:
        psu = stack.enter_context(
            DCPowerSupply(config.psu, simulate=config.simulate))
        load = stack.enter_context(
            ElectronicLoad(config.load, simulate=config.simulate,
                           max_current=config.limits.i_max + 1.0))
        dmm = stack.enter_context(DMM(config.dmm, simulate=config.simulate))
        scope = stack.enter_context(
            Oscilloscope(config.scope, simulate=config.simulate))
        stack.callback(load.input_off)
        stack.callback(psu.all_outputs_off)
        yield {"psu": psu, "load": load, "dmm": dmm, "scope": scope}


@pytest.fixture(scope="function")
def telemetry(config):
    if not config.stm32_port:
        pytest.skip("No STM32 serial port configured")
    t = STM32Telemetry(config.stm32_port, config.baudrate,
                       simulate=config.simulate).start()
    yield t
    t.stop()


@pytest.fixture(scope="function")
def dut_at_nominal(config, instruments):
    """
    Bring the DUT to a known state before asserting anything about it.

    This is the precondition the design document's tests assume but never
    establish.
    """
    psu, load = instruments["psu"], instruments["load"]
    dmm = instruments["dmm"]
    psu.reset()
    load.reset()
    dmm.configure_dc_voltage(range_val=100, nplc=1)
    psu.set_voltage(config.psu_channel, config.dc_bus_voltage)
    psu.set_current(config.psu_channel, config.dc_bus_current_limit)
    psu.output_on(config.psu_channel)
    load.set_mode("CURRENT")
    load.set_current(0.0)
    load.input_on()
    time.sleep(config.settle_delay_s)
    return instruments
