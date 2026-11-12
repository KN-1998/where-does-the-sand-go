# -*- coding: utf-8 -*-
"""Single-run driver.

Usage (documented in CODER_SPEC §3 and START_HERE.md)::

    python -m exp.run_one --config configs/base.yaml --strategy none \
        --out results/E0_local

Optional overrides: ``--scenario``, ``--bc``, ``--seed``, ``--t-end``, ``--dx``,
``--dt``, ``--label``, ``--baseline`` (run and save the paired baseline too),
``--no-fields``.
"""
from __future__ import annotations

import argparse
import time
from dataclasses import replace
from pathlib import Path

from sim.model import run_model
from sim.params import load_config
from sim.storms import build_event_table

from .common import REPO_ROOT, load_json, retention_curve, save


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Run one scenario/strategy realisation")
    p.add_argument("--config", default=str(REPO_ROOT / "configs" / "base.yaml"))
    p.add_argument("--out", required=True)
    p.add_argument("--strategy", default=None)
    p.add_argument("--scenario", default=None)
    p.add_argument("--bc", default=None)
    p.add_argument("--seed", type=int, default=None)
    p.add_argument("--t-end", type=float, default=None)
    p.add_argument("--dx", type=float, default=None)
    p.add_argument("--dt", type=float, default=None)
    p.add_argument("--label", default=None)
    p.add_argument("--baseline", action="store_true",
                   help="also run and save the paired no-nourishment baseline")
    p.add_argument("--no-fields", action="store_true")
    p.add_argument("--quiet", action="store_true")
    return p


def main(argv=None) -> int:
    args = build_parser().parse_args(argv)
    params, scenario, run = load_config(args.config)
    if args.scenario is not None:
        from sim.params import Scenario
        scenario = Scenario(args.scenario, params, run.overrides)
        run.scenario = args.scenario
        run.forced_events = list(scenario.forced_events)
    over = {}
    for key, value in (("strategy", args.strategy), ("bc", args.bc),
                       ("seed", args.seed), ("t_end", args.t_end),
                       ("dx", args.dx), ("dt", args.dt), ("label", args.label)):
        if value is not None:
            over[key] = value
    if over:
        run = replace(run, **over)
    run.label = run.label or Path(args.out).name

    t0 = time.time()
    table = build_event_table(scenario, run.seed, run.t_end, run.Lb,
                              run.phi_shape, run.forced_events)
    nour = run_model(params, scenario, run, events=table,
                     store_fields=not args.no_fields)
    runtime = time.time() - t0

    retention = None
    if args.baseline:
        base_run = replace(run, strategy="none", placements=None,
                           label=run.label + "_base")
        base = run_model(params, scenario, base_run, events=table, store_fields=False)
        H = float(params["H_dep"])
        times = [t for t in (1.0, 5.0, 15.0) if t <= run.t_end + 1e-9]
        retention = retention_curve(nour, base, times, H)
        save(Path(args.out) / "baseline", base, runtime_s=None, write_fields=False)

    res = save(Path(args.out), nour, retention=retention, runtime_s=runtime,
               write_fields=not args.no_fields)
    if not args.quiet:
        print(f"[run_one] {args.out}: residual_rel_max={res['mass']['residual_rel_max']:.2e} "
              f"placed={res['mass']['placed']:.3e} m3 finished in {runtime:.2f}s")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
