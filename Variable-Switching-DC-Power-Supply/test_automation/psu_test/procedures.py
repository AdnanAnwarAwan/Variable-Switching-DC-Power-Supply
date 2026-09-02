"""
Blocks 9-11 — the automated test procedures.

Every procedure here follows the same contract:
  * takes a BenchConfig, opens instruments, and guarantees a safe shutdown
    in a finally block (load input off before PSU output off — the reverse
    order dumps the bulk capacitor into an unloaded output);
  * returns data plus an explicit pass/fail, never prints a verdict and
    swallows it;
  * works identically against real hardware and the simulator.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass

import numpy as np
import pandas as pd

from .analysis import (
    analyse_transient,
    efficiency_percent,
    load_regulation_percent,
    response_time_s,
)
from .config import BenchConfig
from .instruments import DCPowerSupply, DMM, ElectronicLoad, Oscilloscope
from .telemetry import STM32Telemetry

log = logging.getLogger(__name__)


def _sim_waveform_mode(scope: Oscilloscope, mode: str) -> None:
    """
    Tell the simulated scope which waveform to synthesise.

    No-op against real hardware. Note this sets the attribute on the
    underlying simulated resource (scope.inst), not on the wrapper — setting
    it on the wrapper would silently do nothing, which is exactly the kind of
    quiet no-op this harness is meant to eliminate.
    """
    inst = getattr(scope, "inst", None)
    if inst is not None and hasattr(inst, "mode"):
        inst.mode = mode


@dataclass
class ProcedureResult:
    """Uniform return type: the data, the verdict, and why."""

    name: str
    passed: bool
    data: object
    findings: list[str]
    artifacts: list[str]

    def report(self) -> str:
        head = f"{self.name}: {'PASS' if self.passed else 'FAIL'}"
        return "\n".join([head, *(f"  - {f}" for f in self.findings)])


# ── Block 9 ───────────────────────────────────────────────────────────
def load_regulation_sweep(cfg: BenchConfig, *,
                          currents: list[float] | None = None,
                          output_csv: str = "load_reg_results.csv",
                          plot_png: str = "load_regulation_plot.png",
                          show: bool = False) -> ProcedureResult:
    """
    Phase 5A: fix the output, sweep the load, log everything.

    Differences from the documented script:
      * config-driven rather than hard-coded resource strings;
      * checks the bench supply has not fallen into current limit at each
        point — efficiency measured while the source is in CC is fiction;
      * averages the DMM and records the standard deviation, so a noisy
        point is visible in the data rather than hidden by a single read;
      * waits for a fresh telemetry sample instead of sleeping and hoping;
      * verdict is computed from the data and returned, not printed.
    """
    import matplotlib
    if not show:
        matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    cfg.sanity_check()
    lim = cfg.limits
    currents = currents or [round(0.5 * i, 2) for i in range(0, 11)]
    findings: list[str] = []

    psu = DCPowerSupply(cfg.psu, simulate=cfg.simulate)
    load = ElectronicLoad(cfg.load, simulate=cfg.simulate,
                          max_current=lim.i_max + 1.0)
    dmm = DMM(cfg.dmm, simulate=cfg.simulate)
    telem = None
    if cfg.stm32_port:
        telem = STM32Telemetry(cfg.stm32_port, cfg.baudrate,
                               simulate=cfg.simulate).start()

    rows = []
    try:
        psu.reset()
        load.reset()
        dmm.configure_dc_voltage(range_val=100 if lim.v_nominal > 10 else 10,
                                 nplc=1)

        psu.set_voltage(cfg.psu_channel, cfg.dc_bus_voltage)
        psu.set_current(cfg.psu_channel, cfg.dc_bus_current_limit)
        psu.output_on(cfg.psu_channel)
        load.set_mode("CURRENT")
        load.input_off()
        time.sleep(cfg.settle_delay_s)

        log.info("Sweeping load 0 to %.1f A at %.2f V", max(currents),
                 lim.v_nominal)
        for current in currents:
            load.set_current(current)
            load.input_on()
            time.sleep(cfg.settle_delay_s)

            v_mean, v_sd = dmm.read_averaged(cfg.dmm_averages)
            vin = psu.measure_voltage(cfg.psu_channel)
            iin = psu.measure_current(cfg.psu_channel)
            vout_load = load.measure_voltage()
            iout_load = load.measure_current()
            p_in, p_out = vin * iin, vout_load * iout_load
            # Efficiency at zero output power is 0% by arithmetic and
            # meaningless by physics — the converter is doing no work, not
            # doing it badly. NaN keeps it out of the curve and out of any
            # min()/mean() a reader might take.
            eff = (efficiency_percent(p_out, p_in) if current >= 0.05
                   else float("nan"))

            in_cc = psu.in_current_limit(cfg.psu_channel)
            if in_cc:
                findings.append(
                    f"Bench supply hit its {cfg.dc_bus_current_limit} A limit "
                    f"at {current} A load — efficiency from this point on is "
                    "invalid, raise the limit and re-run."
                )

            t = {}
            if telem:
                sample = telem.wait_for_sample(timeout=2.0)
                t = sample.as_dict() if sample else {}
                if not t:
                    findings.append(
                        f"No telemetry decoded at {current} A "
                        f"(detected format: {telem.detected_format})."
                    )

            rows.append({
                "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
                "load_current_set": current,
                "vout_dmm": v_mean,
                "vout_dmm_sd": v_sd,
                "vout_load": vout_load,
                "iout_load": iout_load,
                "vin": vin, "iin": iin,
                "pin": p_in, "pout": p_out,
                "efficiency": eff,
                "psu_in_current_limit": in_cc,
                **t,
            })
            log.info("Iload=%.2f A  Vout=%.4f V (sd %.4f)  eff=%.2f%%",
                     current, v_mean, v_sd, eff)

        df = pd.DataFrame(rows)
        df.to_csv(output_csv, index=False)

        # ── verdict ────────────────────────────────────────────────────
        reg = load_regulation_percent(df["vout_dmm"], lim.v_nominal)
        if reg > lim.regulation_percent:
            findings.append(
                f"Load regulation {reg:.3f}% exceeds the {lim.regulation_percent}% spec."
            )
        worst_err = float((df["vout_dmm"] - lim.v_nominal).abs().max()
                          / lim.v_nominal * 100)
        if worst_err > lim.regulation_percent:
            findings.append(
                f"Worst setpoint error {worst_err:.3f}% exceeds "
                f"{lim.regulation_percent}% — this is a calibration issue, "
                "distinct from regulation."
            )
        full = df[df["load_current_set"] == max(currents)]
        if not full.empty and full["efficiency"].notna().any():
            eff_full = float(full["efficiency"].iloc[0])
            if eff_full < lim.efficiency_percent:
                findings.append(
                    f"Efficiency at full load {eff_full:.2f}% is below the "
                    f"{lim.efficiency_percent}% target."
                )

        # ── plots ──────────────────────────────────────────────────────
        fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(10, 8), sharex=True)
        band = lim.v_nominal * lim.regulation_percent / 100
        ax1.errorbar(df["load_current_set"], df["vout_dmm"],
                     yerr=df["vout_dmm_sd"], fmt="b-o", capsize=3,
                     label="Vout (DMM, mean +/- sd)")
        ax1.axhline(lim.v_nominal, color="r", ls="--",
                    label=f"Target {lim.v_nominal} V")
        ax1.axhspan(lim.v_nominal - band, lim.v_nominal + band,
                    color="g", alpha=0.12,
                    label=f"+/-{lim.regulation_percent}% band")
        ax1.set_ylabel("Output voltage (V)")
        ax1.set_title(f"Load regulation at {lim.v_nominal} V"
                      + (" [SIMULATED]" if cfg.simulate else ""))
        ax1.legend(); ax1.grid(True, alpha=0.3)

        ax2.plot(df["load_current_set"], df["efficiency"], "r-s",
                 label="Efficiency")
        ax2.axhline(lim.efficiency_percent, color="k", ls="--",
                    label=f"Target {lim.efficiency_percent}%")
        ax2.set_xlabel("Load current (A)")
        ax2.set_ylabel("Efficiency (%)")
        ax2.set_title("Efficiency vs load")
        ax2.legend(); ax2.grid(True, alpha=0.3)

        fig.tight_layout()
        fig.savefig(plot_png, dpi=150)
        if show:
            plt.show()
        plt.close(fig)

        return ProcedureResult(
            name="Phase 5A load regulation",
            passed=not findings,
            data=df,
            findings=findings or [
                f"Regulation {reg:.3f}%, worst setpoint error {worst_err:.3f}%."
            ],
            artifacts=[output_csv, plot_png],
        )
    finally:
        # Order matters: unload last would leave the output unloaded while
        # the bulk cap is still charged.
        try:
            load.input_off()
        finally:
            psu.output_off(cfg.psu_channel)
            if telem:
                telem.stop()
            for inst in (load, dmm, psu):
                inst.close()
            log.info("Instruments safely shut down.")


# ── Block 10 ──────────────────────────────────────────────────────────
def load_transient(cfg: BenchConfig, *, i_low: float = 0.0,
                   i_high: float | None = None,
                   output_png: str = "transient_response.png",
                   show: bool = False) -> ProcedureResult:
    """
    Phase 5B: capture the output during a fast load step.

    Differences from the documented script:
      * uses the electronic load's own transient generator, so the step edge
        is set by the load's slew rate rather than USB command latency
        (which is 100x too slow to measure a 1 ms settling spec);
      * triggers on the DC-coupled output with an offset, not an 11.5 V level
        on an AC-coupled trace, which can never fire;
      * waits for the trigger to actually complete before downloading;
      * scales the waveform through the preamble and reports real volts and
        real seconds, so overshoot and settling time are numbers rather than
        an unlabelled picture.
    """
    import matplotlib
    if not show:
        matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    lim = cfg.limits
    i_high = lim.i_max if i_high is None else i_high
    findings: list[str] = []

    scope = Oscilloscope(cfg.scope, simulate=cfg.simulate)
    load = ElectronicLoad(cfg.load, simulate=cfg.simulate,
                          max_current=lim.i_max + 1.0)
    try:
        scope.reset()
        scope.set_timebase(100e-6)             # 1.2 ms record on 12 divisions
        scope.set_timebase_offset(-200e-6)     # pre-trigger baseline
        scope.set_coupling(1, "DC")
        scope.set_channel_scale(1, 0.5)
        scope.set_channel_offset(1, lim.v_nominal)    # centre the trace
        scope.set_bandwidth_limit(1, True)

        # Trigger just below the regulation band so only a real dip fires it.
        trigger_level = lim.v_nominal * (1 - 2 * lim.regulation_percent / 100)
        scope.configure_edge_trigger(1, trigger_level, slope="NEGative")
        scope.single()

        load.set_mode("CURRENT")
        load.set_slew_rate(0.5)                # 0.5 A/us -> 10 us for 0-5 A
        load.set_transient(i_low, i_high, frequency=100.0, duty_percent=50.0)
        load.input_on()
        time.sleep(0.2)
        load.trigger_transient()

        if not scope.wait_for_trigger(timeout_s=5.0):
            findings.append(
                "Scope never triggered — the captured record is stale. Check "
                "the trigger level against the actual dip depth."
            )
        scope.stop()
        t, v = scope.get_waveform_scaled(1)

        result = analyse_transient(t, v, settle_band_percent=1.0)
        settle_ms = (result.settling_time_s * 1e3
                     if result.settling_time_s is not None else None)

        if settle_ms is None:
            findings.append(
                "Output had not settled by the end of the record — increase "
                "the timebase and re-run."
            )
        elif settle_ms > lim.settling_time_ms:
            findings.append(
                f"Settling time {settle_ms:.3f} ms exceeds the "
                f"{lim.settling_time_ms} ms spec."
            )
        if result.worst_deviation_percent > lim.overshoot_percent:
            findings.append(
                f"Worst deviation {result.worst_deviation_percent:.2f}% "
                f"exceeds the {lim.overshoot_percent}% spec "
                f"(undershoot {result.undershoot_percent:.2f}%, "
                f"overshoot {result.overshoot_percent:.2f}%)."
            )

        fig, ax = plt.subplots(figsize=(12, 5))
        ax.plot(t * 1e3, v, lw=0.9)
        ax.axvline(0, color="r", ls="--", label="Load step")
        ax.axhline(result.v_final, color="k", ls=":", label="Final value")
        band = abs(result.v_final) * 0.01
        ax.axhspan(result.v_final - band, result.v_final + band,
                   color="g", alpha=0.12, label="+/-1% settling band")
        if settle_ms is not None:
            ax.axvline(settle_ms, color="m", ls="-.",
                       label=f"Settled at {settle_ms:.3f} ms")
        ax.set_xlabel("Time (ms)")
        ax.set_ylabel("Output voltage (V)")
        ax.set_title(f"Load transient {i_low} A -> {i_high} A"
                     + (" [SIMULATED]" if cfg.simulate else ""))
        ax.grid(True, alpha=0.3); ax.legend()
        fig.tight_layout()
        fig.savefig(output_png, dpi=150)
        if show:
            plt.show()
        plt.close(fig)

        summary = (f"Undershoot {result.undershoot_percent:.2f}%, "
                   f"overshoot {result.overshoot_percent:.2f}%, settling "
                   + (f"{settle_ms:.3f} ms" if settle_ms is not None
                      else "not reached"))
        return ProcedureResult(
            name="Phase 5B load transient",
            passed=not findings,
            data=result,
            findings=findings or [summary],
            artifacts=[output_png],
        )
    finally:
        try:
            load.input_off()
        finally:
            for inst in (load, scope):
                inst.close()


# ── Block 11 ──────────────────────────────────────────────────────────
def ovp_response(cfg: BenchConfig, *, command_voltage: float = 35.0,
                 output_png: str = "ovp_response.png",
                 show: bool = False) -> ProcedureResult:
    """
    Phase 6: inject an over-voltage fault and measure the shutdown time.

    READ THIS BEFORE RUNNING ON HARDWARE. The documented method — send
    "SETV 35.0" over the UART and expect an OVP trip — cannot work against
    the firmware in this repository, for two independent reasons:

      1. The firmware never reads the UART. USART1 is initialised in TX_RX
         mode but PA10 is not configured and no RX interrupt or poll exists,
         so the command is discarded.
      2. There is no OVP check anywhere in the firmware. Fault_Shutdown() is
         reached only from over-current and over-temperature. Even a
         successfully parsed SETV 35.0 would be clamped to V_MAX = 30 V by
         the setpoint limiter and nothing would trip.

    So this procedure tests firmware that does not exist yet. Applying
    firmware_patch/telemetry.c (UART command parser) and adding an OVP
    comparison in the PID ISR makes it real. Until then it passes only
    against the simulator, and it says so.

    The physically honest hardware method is the one in the framework
    document's own table: override the feedback divider with an external
    source so the MCU *sees* an over-voltage, rather than politely asking
    the MCU to exceed its own limit.
    """
    import matplotlib
    if not show:
        matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    lim = cfg.limits
    findings: list[str] = []

    scope = Oscilloscope(cfg.scope, simulate=cfg.simulate)
    telem = STM32Telemetry(cfg.stm32_port, cfg.baudrate,
                           simulate=cfg.simulate).start()
    try:
        scope.reset()
        _sim_waveform_mode(scope, "protection")   # sim: synthesise a collapse
        scope.set_timebase(10e-6)              # 120 us record
        scope.set_coupling(1, "DC")
        scope.set_channel_scale(1, 5.0)
        scope.configure_edge_trigger(1, lim.v_nominal * 0.9, slope="NEGative")
        scope.single()

        time.sleep(0.3)
        telem.send_command(f"SETV {command_voltage}")
        tripped = telem.wait_for_status("FAULT", timeout=1.0)

        if not tripped:
            findings.append(
                "No FAULT status within 1 s. Against stock firmware this is "
                "the expected result: there is no UART command parser and no "
                "OVP check. See this function's docstring."
            )

        scope.wait_for_trigger(timeout_s=2.0)
        scope.stop()
        t, v = scope.get_waveform_scaled(1)

        threshold = lim.v_nominal * 0.1
        t_resp = response_time_s(t, v, threshold=threshold, from_time=0.0)
        if t_resp is None:
            findings.append("Output never collapsed below 10% within the record.")
        else:
            t_us = t_resp * 1e6
            if t_us > lim.ovp_response_us:
                findings.append(
                    f"Shutdown took {t_us:.2f} us, above the "
                    f"{lim.ovp_response_us} us requirement."
                )

        fig, ax = plt.subplots(figsize=(10, 4.5))
        ax.plot(t * 1e6, v, lw=1.0)
        ax.axvline(0, color="r", ls="--", label="Fault injected")
        ax.axhline(threshold, color="g", ls=":", label="10% of nominal")
        if t_resp is not None:
            ax.axvline(t_resp * 1e6, color="m", ls="-.",
                       label=f"Collapsed in {t_resp * 1e6:.2f} us")
        ax.set_xlabel("Time (us)")
        ax.set_ylabel("Output voltage (V)")
        ax.set_title("OVP shutdown response"
                     + (" [SIMULATED]" if cfg.simulate else ""))
        ax.grid(True, alpha=0.3); ax.legend()
        fig.tight_layout()
        fig.savefig(output_png, dpi=150)
        if show:
            plt.show()
        plt.close(fig)

        detail = (f"Collapsed in {t_resp * 1e6:.2f} us"
                  if t_resp is not None else "No collapse detected")
        return ProcedureResult(
            name="Phase 6 OVP response",
            passed=not findings,
            data={"response_s": t_resp, "tripped": tripped,
                  "faults": list(telem.fault_events)},
            findings=findings or [detail],
            artifacts=[output_png],
        )
    finally:
        telem.stop()
        scope.close()


def ripple_measurement(cfg: BenchConfig, *, load_current: float | None = None
                       ) -> ProcedureResult:
    """
    Phase 5A ripple check. Split out from the sweep because it needs the
    scope, AC coupling and a 20 MHz bandwidth limit — the DMM the design
    document assigns to this measurement integrates 200 kHz ripple to
    approximately zero and will report a pass no matter how bad it is.
    """
    lim = cfg.limits
    load_current = lim.i_max if load_current is None else load_current

    scope = Oscilloscope(cfg.scope, simulate=cfg.simulate)
    load = ElectronicLoad(cfg.load, simulate=cfg.simulate,
                          max_current=lim.i_max + 1.0)
    try:
        _sim_waveform_mode(scope, "ripple")
        scope.set_channel_scale(1, 0.01)
        load.set_mode("CURRENT")
        load.set_current(load_current)
        load.input_on()
        time.sleep(cfg.settle_delay_s)

        vpp_v = scope.measure_ripple_vpp(1)
        vpp_mv = vpp_v * 1e3
        findings = []
        if vpp_mv > lim.ripple_mvpp:
            findings.append(
                f"Ripple {vpp_mv:.1f} mVpp exceeds the {lim.ripple_mvpp} mVpp "
                "limit."
            )
        findings.append(
            "Probe technique dominates this number: use a ground spring, not "
            "a 6 inch ground lead, or you are measuring pickup."
        )
        return ProcedureResult(
            name="Phase 5A output ripple",
            passed=vpp_mv <= lim.ripple_mvpp,
            data={"ripple_mvpp": vpp_mv, "load_current": load_current},
            findings=findings,
            artifacts=[],
        )
    finally:
        try:
            load.input_off()
        finally:
            load.close()
            scope.close()
