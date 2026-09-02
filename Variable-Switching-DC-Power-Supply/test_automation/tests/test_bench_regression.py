"""
Block 12 — Regression suite.

Runs against the simulator by default and against the physical bench with
`pytest --hardware --bench-config config/bench.yaml`.

What is different from the design document's version:

  * every test establishes its own preconditions. The document's
    `test_voltage_accuracy_12V` asserts the DMM reads 12 V without ever
    commanding 12 V, so it is really asserting "whatever the DUT was last
    left at". Here the `dut_at_nominal` fixture sets the state.

  * `test_efficiency_full_load` in the document is `pass` — a test body of
    `pass` is a green checkmark that measures nothing, which is worse than
    no test because it appears in the report as evidence. This one measures.

  * tests do not depend on each other's side effects. The document's
    `test_load_regulation_5A` leaves the load at 5 A on, so anything running
    after it silently inherits full load.

  * assertions carry the measured value AND the limit in the failure message,
    so a CI log is diagnosable without re-running.
"""

from __future__ import annotations

import time

import pytest

from psu_test.analysis import (
    analyse_transient,
    efficiency_percent,
    load_regulation_percent,
    setpoint_error_percent,
)


@pytest.fixture(autouse=True)
def _unload_after(instruments):
    """Return the DUT to no-load between tests so they stay independent."""
    yield
    instruments["load"].set_current(0.0)
    instruments["load"].input_off()


class TestStaticPerformance:
    """Phase 5A."""

    def test_instruments_respond(self, instruments):
        for name, inst in instruments.items():
            idn = inst.idn()
            assert idn and "," in idn, f"{name} returned a bad *IDN?: {idn!r}"

    def test_voltage_accuracy_at_nominal(self, config, dut_at_nominal):
        dmm = dut_at_nominal["dmm"]
        v_nom = config.limits.v_nominal
        mean, sd = dmm.read_averaged(config.dmm_averages)
        err = setpoint_error_percent(mean, v_nom)
        assert abs(err) <= config.limits.regulation_percent, (
            f"Setpoint error {err:+.3f}% ({mean:.4f} V vs {v_nom} V) exceeds "
            f"+/-{config.limits.regulation_percent}%"
        )
        assert sd < v_nom * 0.001, (
            f"Reading noise {sd * 1e3:.2f} mV is a large fraction of the "
            f"{v_nom * config.limits.regulation_percent / 100 * 1e3:.1f} mV "
            "spec window; the mean is not trustworthy"
        )

    def test_load_regulation_across_sweep(self, config, dut_at_nominal):
        load, dmm = dut_at_nominal["load"], dut_at_nominal["dmm"]
        v_nom, i_max = config.limits.v_nominal, config.limits.i_max
        voltages = []
        for i in [0.0, i_max / 4, i_max / 2, 3 * i_max / 4, i_max]:
            load.set_current(i)
            load.input_on()
            time.sleep(config.settle_delay_s)
            voltages.append(dmm.read())
        reg = load_regulation_percent(voltages, v_nom)
        assert reg <= config.limits.regulation_percent, (
            f"Load regulation {reg:.3f}% over 0-{i_max} A exceeds "
            f"{config.limits.regulation_percent}% "
            f"(spread {max(voltages) - min(voltages):.4f} V)"
        )

    def test_full_load_voltage_in_band(self, config, dut_at_nominal):
        load, dmm = dut_at_nominal["load"], dut_at_nominal["dmm"]
        v_nom = config.limits.v_nominal
        band = v_nom * config.limits.regulation_percent / 100
        load.set_current(config.limits.i_max)
        load.input_on()
        time.sleep(config.settle_delay_s)
        v = dmm.read()
        assert abs(v - v_nom) <= band, (
            f"Vout {v:.4f} V at {config.limits.i_max} A is outside "
            f"{v_nom} +/- {band:.4f} V"
        )

    def test_source_not_in_current_limit(self, config, dut_at_nominal):
        """
        Guard test. If the bench supply is in CC, every efficiency number
        from this session is garbage — catch it here rather than in the plot.
        """
        psu, load = dut_at_nominal["psu"], dut_at_nominal["load"]
        load.set_current(config.limits.i_max)
        load.input_on()
        time.sleep(config.settle_delay_s)
        assert not psu.in_current_limit(config.psu_channel), (
            f"Bench supply is in current limit at "
            f"{config.dc_bus_current_limit} A; raise it and re-run"
        )


class TestEfficiency:
    """Phase 5C."""

    def test_efficiency_at_full_load(self, config, dut_at_nominal):
        psu, load = dut_at_nominal["psu"], dut_at_nominal["load"]
        load.set_current(config.limits.i_max)
        load.input_on()
        time.sleep(config.settle_delay_s)

        p_in = psu.measure_power(config.psu_channel)
        p_out = load.measure_power()
        eff = efficiency_percent(p_out, p_in)

        assert eff == eff, "Efficiency is NaN — input power was zero or negative"
        assert eff <= 100.0, (
            f"Efficiency {eff:.2f}% exceeds 100%, which means a measurement "
            "error (sense leads, shunt calibration), not a good converter"
        )
        assert eff >= config.limits.efficiency_percent, (
            f"Efficiency {eff:.2f}% at {config.limits.i_max} A is below the "
            f"{config.limits.efficiency_percent}% target "
            f"(Pin {p_in:.2f} W, Pout {p_out:.2f} W, loss {p_in - p_out:.2f} W)"
        )

    @pytest.mark.parametrize("fraction", [0.2, 0.5, 1.0])
    def test_efficiency_is_physical(self, config, dut_at_nominal, fraction):
        """Efficiency above 100% at any load point means a wiring error."""
        psu, load = dut_at_nominal["psu"], dut_at_nominal["load"]
        load.set_current(config.limits.i_max * fraction)
        load.input_on()
        time.sleep(config.settle_delay_s)
        eff = efficiency_percent(load.measure_power(),
                                 psu.measure_power(config.psu_channel))
        assert 0 < eff <= 100, f"Non-physical efficiency {eff:.2f}%"


class TestDynamicPerformance:
    """Phase 5B."""

    def test_load_step_settles_within_spec(self, config, dut_at_nominal):
        scope, load = dut_at_nominal["scope"], dut_at_nominal["load"]
        lim = config.limits
        scope.reset()
        scope.set_timebase(100e-6)
        scope.set_coupling(1, "DC")
        scope.set_channel_scale(1, 0.5)
        scope.set_channel_offset(1, lim.v_nominal)
        scope.configure_edge_trigger(
            1, lim.v_nominal * (1 - 2 * lim.regulation_percent / 100), "NEGative")
        scope.single()

        load.set_slew_rate(0.5)
        load.set_transient(0.0, lim.i_max, frequency=100.0)
        load.input_on()
        time.sleep(0.1)
        load.trigger_transient()
        scope.wait_for_trigger(timeout_s=5.0)
        scope.stop()

        t, v = scope.get_waveform_scaled(1)
        r = analyse_transient(t, v, settle_band_percent=1.0)

        assert r.settling_time_s is not None, (
            "Output had not settled by the end of the capture window"
        )
        assert r.settling_time_s * 1e3 <= lim.settling_time_ms, (
            f"Settling {r.settling_time_s * 1e3:.3f} ms exceeds "
            f"{lim.settling_time_ms} ms"
        )
        assert r.worst_deviation_percent <= lim.overshoot_percent, (
            f"Deviation {r.worst_deviation_percent:.2f}% exceeds "
            f"{lim.overshoot_percent}% (under {r.undershoot_percent:.2f}%, "
            f"over {r.overshoot_percent:.2f}%)"
        )


class TestTelemetryIntegrity:
    """
    Phase 4 / Phase 8. These do not test the converter — they test that the
    data the rest of the suite records is real.
    """

    def test_telemetry_decodes_at_all(self, telemetry):
        sample = telemetry.wait_for_sample(timeout=3.0)
        assert sample is not None, (
            "No telemetry line decoded in 3 s. Either the UART is silent or "
            "the format does not match either parser — check the baud rate "
            "and see psu_test/telemetry.py"
        )

    def test_telemetry_tracks_the_dmm(self, config, dut_at_nominal, telemetry):
        """
        Cross-check the firmware's own ADC against the golden reference.

        A large disagreement here means the sense divider or ADC calibration
        is off, which makes the PID regulate to the wrong voltage no matter
        how well tuned it is.
        """
        sample = telemetry.wait_for_sample(timeout=3.0)
        assert sample is not None
        v_dmm = dut_at_nominal["dmm"].read()
        err = abs(sample.v_meas - v_dmm) / max(v_dmm, 1e-6) * 100
        assert err < 2.0, (
            f"Firmware reports {sample.v_meas:.3f} V, DMM reads {v_dmm:.3f} V "
            f"({err:.2f}% apart) — ADC or divider calibration issue"
        )

    def test_duty_cycle_is_reported(self, telemetry):
        """
        Expected to FAIL against stock firmware, and that is the point.

        The design document promises a duty-cycle column in every results
        table. main.c does not transmit it. Apply firmware_patch/telemetry.c
        to make this pass rather than deleting the test.
        """
        sample = telemetry.wait_for_sample(timeout=3.0)
        assert sample is not None
        if sample.source_format == "keyvalue":
            pytest.xfail(
                "Stock firmware emits key=value lines with no duty cycle; "
                "apply firmware_patch/telemetry.c for the documented CSV"
            )
        assert sample.duty is not None
        assert 0.0 <= sample.duty <= 100.0


@pytest.mark.hardware
class TestProtection:
    """
    Phase 6. Marked hardware-only: fault injection on a simulator proves
    nothing about a real converter, and running it by accident on the bench
    with mains connected is genuinely dangerous.

    Read psu_test.procedures.ovp_response's docstring before enabling these
    — the stock firmware has no OVP check and no UART command parser, so
    they test firmware that does not exist yet.
    """

    def test_ovp_trips_within_spec(self, config, telemetry):
        pytest.skip(
            "Requires firmware with an OVP comparison and a UART command "
            "parser. See firmware_patch/ and docs. Do not enable this until "
            "the feedback-divider override method in the framework document "
            "Phase 6 table has been set up on the bench."
        )

    def test_ocp_foldback_point(self, config, dut_at_nominal):
        pytest.skip(
            "Requires a load capable of exceeding I_max and a verified "
            "current-sense calibration. Run manually first."
        )
