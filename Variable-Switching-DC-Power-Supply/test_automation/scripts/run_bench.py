#!/usr/bin/env python3
"""
Command-line runner for the bench procedures.

    python scripts/run_bench.py regulation --simulate
    python scripts/run_bench.py transient  --simulate
    python scripts/run_bench.py ovp        --simulate
    python scripts/run_bench.py all        --simulate --report

Drop --simulate to run against real instruments listed in config/bench.yaml.

Safety: anything that energises the DC bus requires either a --yes flag or an
interactive confirmation. Section 10 of the design document recommends
human-in-the-loop gates for dangerous tests and then never implements one.
"""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from psu_test.config import BenchConfig                     # noqa: E402
from psu_test.procedures import (                            # noqa: E402
    load_regulation_sweep,
    load_transient,
    ovp_response,
    ripple_measurement,
)


def build_config(args) -> BenchConfig:
    if args.config:
        cfg = BenchConfig.load_file(args.config)
    else:
        path = Path(__file__).resolve().parent.parent / "config" / "bench.yaml"
        cfg = BenchConfig.load_file(path) if path.exists() else BenchConfig()
    if args.simulate:
        cfg.simulate = True
    if args.voltage is not None:
        cfg.limits.v_nominal = args.voltage
    return cfg


def confirm(cfg: BenchConfig, args, what: str) -> bool:
    if cfg.simulate or args.yes:
        return True
    print(f"\nAbout to run: {what}")
    print(f"  DC bus      : {cfg.dc_bus_voltage} V, "
          f"{cfg.dc_bus_current_limit} A limit")
    print(f"  Output      : {cfg.limits.v_nominal} V nominal, "
          f"up to {cfg.limits.i_max} A")
    print("  Confirm the DUT is on the bench, mains is DISCONNECTED, and the")
    print("  transformer secondary is isolated before injecting the DC bus.")
    return input("Proceed? [y/N] ").strip().lower() in {"y", "yes"}


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("procedure",
                   choices=["regulation", "transient", "ovp", "ripple", "all"])
    p.add_argument("--config", help="Path to bench.yaml")
    p.add_argument("--simulate", action="store_true",
                   help="Run against the software bench, no hardware needed")
    p.add_argument("--voltage", type=float,
                   help="Override the nominal output setpoint, volts")
    p.add_argument("--outdir", default="results",
                   help="Directory for CSV, PNG and DOCX artifacts")
    p.add_argument("--report", action="store_true",
                   help="Generate a Word test report after the run")
    p.add_argument("--yes", action="store_true",
                   help="Skip the safety confirmation prompt")
    p.add_argument("-v", "--verbose", action="store_true")
    args = p.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s  %(levelname)-7s %(name)s: %(message)s",
    )

    cfg = build_config(args)
    outdir = Path(args.outdir)
    outdir.mkdir(parents=True, exist_ok=True)

    bench = None
    if cfg.simulate:
        from psu_test.simulator import build_bench
        bench = build_bench(cfg, csv_telemetry=True, accepts_commands=True)
        logging.getLogger(__name__).info(
            "SIMULATED RUN — results are not hardware measurements")

    wanted = (["regulation", "transient", "ovp", "ripple"]
              if args.procedure == "all" else [args.procedure])
    if not confirm(cfg, args, ", ".join(wanted)):
        print("Aborted.")
        return 130

    results, df = [], None
    for name in wanted:
        try:
            if name == "regulation":
                r = load_regulation_sweep(
                    cfg,
                    output_csv=str(outdir / "load_reg_results.csv"),
                    plot_png=str(outdir / "load_regulation_plot.png"))
                df = r.data
            elif name == "transient":
                r = load_transient(
                    cfg, output_png=str(outdir / "transient_response.png"))
            elif name == "ovp":
                r = ovp_response(
                    cfg, output_png=str(outdir / "ovp_response.png"))
            else:
                r = ripple_measurement(cfg)
        except Exception as exc:  # noqa: BLE001 - report and continue
            logging.exception("%s raised", name)
            print(f"\n{name}: ERROR — {exc}")
            results.append(None)
            continue
        results.append(r)
        print("\n" + r.report())

    if args.report and df is not None:
        from psu_test.report import generate_report
        plots = [a for r in results if r for a in r.artifacts
                 if a.endswith(".png")]
        notes = "\n".join(f"[{r.name}] {f}" for r in results if r
                          for f in r.findings)
        path = generate_report(
            df, cfg.limits, plots,
            output_doc=str(outdir / "Test_Report.docx"),
            instrument_ids={"Bench": "simulator" if cfg.simulate else "hardware"},
            simulated=cfg.simulate,
            notes=notes)
        print(f"\nReport written to {path}")

    ran = [r for r in results if r]
    failed = [r for r in ran if not r.passed]
    print(f"\n{'=' * 60}")
    print(f"{len(ran) - len(failed)}/{len(ran)} procedures passed")
    if bench is not None:
        print("Reminder: this was a simulated run.")
    return 1 if failed or len(ran) != len(results) else 0


if __name__ == "__main__":
    raise SystemExit(main())
