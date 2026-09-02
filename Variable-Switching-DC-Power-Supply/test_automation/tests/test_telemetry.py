"""
Telemetry parser tests.

The first test in this file is the one that matters: it pins the fact that
the firmware's actual output format is not the format the design document
specifies, so that if someone later "simplifies" the parser back to a plain
CSV split, CI catches it instead of a silent column of None in the results.
"""

from __future__ import annotations

import time

import pytest

from psu_test.config import BenchConfig
from psu_test.session import clear_simulated
from psu_test.simulator import BuckModel, build_bench
from psu_test.telemetry import STM32Telemetry, parse_line


class TestParser:
    def test_firmware_keyvalue_format(self):
        """This is what firmware/Core/Src/main.c actually prints at 10 Hz."""
        line = "Vset=12.00 Vout=11.98 Iout=2.50 T=41.2C [CV]"
        s = parse_line(line)
        assert s is not None
        assert s.source_format == "keyvalue"
        assert s.v_set == pytest.approx(12.00)
        assert s.v_meas == pytest.approx(11.98)
        assert s.i_meas == pytest.approx(2.50)
        assert s.temp == pytest.approx(41.2)
        assert s.mode == "CV"
        assert s.duty is None, "stock firmware does not transmit duty cycle"

    def test_documented_csv_format(self):
        s = parse_line("12.000,11.980,2.500,26.62,41.2,OK")
        assert s is not None
        assert s.source_format == "csv"
        assert s.duty == pytest.approx(26.62)
        assert s.status == "OK"

    def test_naive_csv_split_would_fail_on_real_firmware(self):
        """
        The document's parser: line.split(',') then require len == 6.
        Against the firmware's real output that yields one field.
        """
        line = "Vset=12.00 Vout=11.98 Iout=2.50 T=41.2C [CV]"
        assert len(line.split(",")) == 1
        assert parse_line(line) is not None   # ours copes; the document's does not

    @pytest.mark.parametrize("line", [
        "", "   ",
        "Variable Switching DC PSU - Adnan Anwar Awan",
        "Vset=12.00V  Ilim=5.00A",
        "garbage,garbage,garbage,garbage,garbage,garbage",
    ])
    def test_noise_returns_none(self, line):
        assert parse_line(line) is None

    def test_cc_mode(self):
        s = parse_line("Vset=12.00 Vout=9.50 Iout=5.30 T=55.0C [CC]")
        assert s.mode == "CC"


class TestReaderAgainstSimulator:
    @pytest.fixture(autouse=True)
    def _clean(self):
        clear_simulated()
        yield
        clear_simulated()

    def _read_one(self, csv_format: bool):
        cfg = BenchConfig()
        cfg.simulate = True
        bench = build_bench(cfg, csv_telemetry=csv_format)
        bench.model.bus_voltage = 45.0
        bench.model.bus_output_on = True
        with STM32Telemetry(cfg.stm32_port, simulate=True) as t:
            sample = t.wait_for_sample(timeout=3.0)
        return sample

    def test_reads_csv_firmware(self):
        s = self._read_one(csv_format=True)
        assert s is not None and s.source_format == "csv"
        assert s.duty is not None

    def test_reads_stock_firmware_and_reports_missing_duty(self):
        s = self._read_one(csv_format=False)
        assert s is not None and s.source_format == "keyvalue"
        assert s.duty is None

    def test_fault_line_is_captured(self):
        cfg = BenchConfig()
        cfg.simulate = True
        bench = build_bench(cfg, csv_telemetry=False)
        bench.model.bus_voltage = 45.0
        bench.model.bus_output_on = True
        with STM32Telemetry(cfg.stm32_port, simulate=True) as t:
            t.wait_for_sample(timeout=3.0)
            bench.model.trip("OVER CURRENT")
            assert t.wait_for_status("FAULT", timeout=3.0)
            assert t.fault_events

    def test_commands_are_discarded_by_stock_firmware(self):
        """
        Reproduces the real limitation: the stock firmware never reads RX,
        so SETV has no effect. A harness that assumed otherwise would report
        a false OVP pass.
        """
        cfg = BenchConfig()
        cfg.simulate = True
        bench = build_bench(cfg, csv_telemetry=False, accepts_commands=False)
        bench.model.bus_voltage = 45.0
        bench.model.bus_output_on = True
        with STM32Telemetry(cfg.stm32_port, simulate=True) as t:
            t.send_command("SETV 35.0")
            time.sleep(0.2)
            assert bench.model.fault is None
            assert bench.model.v_setpoint == pytest.approx(12.0)
