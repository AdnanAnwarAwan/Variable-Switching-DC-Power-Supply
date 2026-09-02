"""
Measurement maths, kept free of instrument I/O so it can be unit-tested
without hardware or a simulator. tests/test_analysis.py exercises this file.

The design document computes regulation as `abs(min_v - 12) / 12 * 100`.
That is *voltage accuracy against the setpoint*, not load regulation. Load
regulation is the spread across the load sweep:

    (V_noload - V_fullload) / V_nominal * 100

A supply sitting 0.4% low but perfectly flat across 0-5 A has excellent load
regulation and mediocre accuracy. The document's formula scores it as poor
regulation, which would send you tuning the wrong thing (the PID, rather
than the sense-divider calibration).
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np


# ── static performance ────────────────────────────────────────────────
def load_regulation_percent(voltages, nominal: float | None = None) -> float:
    """
    Load regulation: full spread across the load sweep, as % of nominal.

    Pass voltages in load order (no-load first).
    """
    v = np.asarray(voltages, dtype=float)
    if v.size < 2:
        raise ValueError("Need at least two load points")
    ref = float(nominal) if nominal is not None else float(v[0])
    if ref == 0:
        raise ValueError("Nominal voltage cannot be zero")
    return float((v.max() - v.min()) / ref * 100.0)


def setpoint_error_percent(measured: float, setpoint: float) -> float:
    """Signed accuracy error against the commanded setpoint, in percent."""
    if setpoint == 0:
        raise ValueError("Setpoint cannot be zero")
    return float((measured - setpoint) / setpoint * 100.0)


def line_regulation_percent(voltages, nominal: float) -> float:
    """Output spread across an input-voltage sweep, as % of nominal."""
    return load_regulation_percent(voltages, nominal)


def efficiency_percent(p_out: float, p_in: float) -> float:
    """
    Efficiency in percent. Returns NaN rather than 0 when P_in is not usable.

    The design document returns 0 when p_in <= 0. A zero silently plots as a
    real datum and drags any mean or min down; NaN propagates visibly and is
    skipped by matplotlib.
    """
    if p_in is None or p_in <= 0 or p_out is None or p_out < 0:
        return float("nan")
    return float(p_out / p_in * 100.0)


# ── dynamic performance ───────────────────────────────────────────────
@dataclass
class TransientResult:
    """Outcome of a load-step analysis."""

    v_initial: float
    v_final: float
    v_min: float
    v_max: float
    undershoot_percent: float
    overshoot_percent: float
    settling_time_s: float | None
    step_index: int

    @property
    def worst_deviation_percent(self) -> float:
        return max(abs(self.undershoot_percent), abs(self.overshoot_percent))


def analyse_transient(t, v, *, settle_band_percent: float = 1.0,
                      step_time: float | None = None,
                      baseline_fraction: float = 0.1) -> TransientResult:
    """
    Extract undershoot, overshoot and settling time from a captured step.

    t : seconds, trigger at 0 (as returned by scope.get_waveform_scaled)
    v : volts
    settle_band_percent : the +/- band around the final value that counts as
        settled. Note this is NOT the same number as the +/-0.5% static
        regulation spec; a dynamic settling band is conventionally wider.

    Settling time is measured from the step instant to the last moment the
    trace leaves the band — measuring to the *first* entry into the band
    would report a ringing supply as settled on its first zero crossing.
    """
    t = np.asarray(t, dtype=float)
    v = np.asarray(v, dtype=float)
    if t.size != v.size or t.size < 10:
        raise ValueError("t and v must be the same length and non-trivial")

    step_index = (int(np.argmin(np.abs(t - step_time)))
                  if step_time is not None
                  else int(np.argmin(np.abs(t))))

    n_base = max(3, int(v.size * baseline_fraction))
    pre = v[:step_index] if step_index >= n_base else v[:n_base]
    v_initial = float(np.mean(pre[-n_base:])) if pre.size else float(v[0])

    post = v[step_index:]
    if post.size < n_base:
        raise ValueError("Not enough post-step samples to find a final value")
    v_final = float(np.mean(post[-n_base:]))

    v_min = float(post.min())
    v_max = float(post.max())
    ref = v_final if v_final != 0 else 1.0
    undershoot = (v_min - v_final) / ref * 100.0
    overshoot = (v_max - v_final) / ref * 100.0

    band = abs(v_final) * settle_band_percent / 100.0
    outside = np.abs(post - v_final) > band
    if not outside.any():
        settling = 0.0
    else:
        last_out = int(np.flatnonzero(outside)[-1])
        settling = (float(t[step_index + last_out] - t[step_index])
                    if last_out < post.size - 1 else None)

    return TransientResult(
        v_initial=v_initial,
        v_final=v_final,
        v_min=v_min,
        v_max=v_max,
        undershoot_percent=float(undershoot),
        overshoot_percent=float(overshoot),
        settling_time_s=settling,
        step_index=step_index,
    )


def response_time_s(t, v, *, threshold: float, from_time: float = 0.0) -> float | None:
    """
    Time from `from_time` until v first falls below `threshold`.

    Used for the Phase 6 OVP / OCP timing requirements (< 20 us, < 10 us).
    Returns None if the threshold is never crossed within the record.
    """
    t = np.asarray(t, dtype=float)
    v = np.asarray(v, dtype=float)
    mask = (t >= from_time) & (v < threshold)
    if not mask.any():
        return None
    return float(t[np.flatnonzero(mask)[0]] - from_time)


def ripple_vpp(v, *, trim_fraction: float = 0.0) -> float:
    """
    Peak-to-peak ripple from a captured trace.

    trim_fraction > 0 discards that fraction from each tail before taking
    the span, which suppresses single-sample probe-pickup spikes. Use it
    consciously: trimming a genuine switching spike out of your ripple number
    is how a 118 mVpp EMI problem gets reported as 22 mVpp.
    """
    v = np.asarray(v, dtype=float)
    if v.size == 0:
        raise ValueError("Empty waveform")
    if trim_fraction <= 0:
        return float(v.max() - v.min())
    lo = float(np.quantile(v, trim_fraction))
    hi = float(np.quantile(v, 1.0 - trim_fraction))
    return hi - lo
