"""
Unit tests for psu_test.analysis — pure maths, no instruments.

These are the tests that catch the class of bug the design document shipped:
a formula that looks right, is never executed, and quietly produces a number
two orders of magnitude off.
"""

from __future__ import annotations

import math

import numpy as np
import pytest

from psu_test.analysis import (
    analyse_transient,
    efficiency_percent,
    load_regulation_percent,
    response_time_s,
    ripple_vpp,
    setpoint_error_percent,
)


class TestRegulation:
    def test_flat_output_is_perfect_regulation(self):
        assert load_regulation_percent([12.0] * 5, 12.0) == pytest.approx(0.0)

    def test_spread_is_measured_not_offset(self):
        """
        A supply 0.4% low but perfectly flat has zero load regulation.

        The design document's formula, abs(min_v - 12)/12*100, scores this
        as 0.4% regulation and would send you tuning the PID when the actual
        problem is sense-divider calibration.
        """
        flat_but_low = [11.952] * 6
        assert load_regulation_percent(flat_but_low, 12.0) == pytest.approx(0.0)
        assert setpoint_error_percent(11.952, 12.0) == pytest.approx(-0.4, abs=1e-9)

    def test_droop_across_sweep(self):
        v = [12.00, 11.99, 11.98, 11.97, 11.96]
        assert load_regulation_percent(v, 12.0) == pytest.approx(0.0400 / 12 * 100)

    def test_single_point_rejected(self):
        with pytest.raises(ValueError):
            load_regulation_percent([12.0])


class TestEfficiency:
    def test_normal(self):
        assert efficiency_percent(60.0, 68.0) == pytest.approx(88.235, abs=1e-3)

    def test_zero_input_is_nan_not_zero(self):
        """
        NaN propagates visibly; the document's 0 silently plots as a datum
        and drags the minimum of the efficiency column to zero.
        """
        assert math.isnan(efficiency_percent(10.0, 0.0))
        assert math.isnan(efficiency_percent(10.0, -1.0))

    def test_nan_is_skipped_by_min(self):
        vals = np.array([88.0, efficiency_percent(1, 0), 91.0])
        assert np.nanmin(vals) == pytest.approx(88.0)


class TestTransient:
    @staticmethod
    def _step(dip=0.30, zeta=0.6, fn=3e3, n=4000, span=4e-3, v0=12.0,
              v_final=11.98):
        t = np.linspace(-span / 4, 3 * span / 4, n)
        wn = 2 * math.pi * fn
        wd = wn * math.sqrt(1 - zeta ** 2)
        v = np.full(n, v0)
        post = t >= 0
        v[post] = v_final - dip * np.exp(-zeta * wn * t[post]) * np.cos(wd * t[post])
        return t, v

    def test_finds_undershoot(self):
        t, v = self._step(dip=0.30)
        r = analyse_transient(t, v)
        assert r.undershoot_percent < 0
        assert r.undershoot_percent == pytest.approx(-0.30 / 11.98 * 100, abs=0.6)

    def test_settling_time_is_in_the_right_decade(self):
        """
        The document's transient script builds its time axis from the
        per-division timebase, producing a settling time 100x too large.
        A 3 kHz, zeta=0.6 response settles in well under a millisecond.
        """
        t, v = self._step()
        r = analyse_transient(t, v)
        assert r.settling_time_s is not None
        assert 1e-5 < r.settling_time_s < 2e-3

    def test_last_exit_not_first_entry(self):
        """A ringing trace must not be called settled at its first crossing."""
        t, v = self._step(zeta=0.05, dip=0.4)
        r = analyse_transient(t, v)
        first_cross = t[np.flatnonzero((t >= 0)
                                       & (np.abs(v - r.v_final)
                                          <= abs(r.v_final) * 0.01))[0]]
        assert r.settling_time_s > first_cross

    def test_rejects_short_record(self):
        with pytest.raises(ValueError):
            analyse_transient([0, 1], [12, 12])


class TestResponseTime:
    def test_finds_collapse(self):
        t = np.linspace(-10e-6, 50e-6, 6000)
        v = np.where(t < 0, 12.0, 12.0 * np.exp(-np.maximum(t, 0) / 4e-6))
        dt = response_time_s(t, v, threshold=1.2)
        assert dt == pytest.approx(4e-6 * math.log(10), rel=0.05)

    def test_none_when_never_crossed(self):
        t = np.linspace(0, 1e-3, 100)
        assert response_time_s(t, np.full(100, 12.0), threshold=1.0) is None


class TestRipple:
    def test_peak_to_peak(self):
        t = np.linspace(0, 1e-3, 10000)
        v = 0.011 * np.sin(2 * math.pi * 200e3 * t)
        assert ripple_vpp(v) == pytest.approx(0.022, abs=5e-4)

    def test_trimming_hides_spikes(self):
        v = np.zeros(1000)
        v[500] = 1.0
        assert ripple_vpp(v) == pytest.approx(1.0)
        assert ripple_vpp(v, trim_fraction=0.01) == pytest.approx(0.0)
