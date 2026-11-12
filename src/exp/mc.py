# -*- coding: utf-8 -*-
"""Monte-Carlo driver (CODER_SPEC §3, E0/E1/E2).

Seed rule (§3.5): realisation ``i`` uses ``seed_i = (seed * 1000003 + i) % 2**32``.
The same ``seed_i`` drives the storm table of the nourished run and of its paired
baseline, so retention is a paired difference.

Usage::

    python -m exp.mc --config configs/S2.yaml --strategy once --n 1000 --jobs 8 \
        --out results/MC_S2_once --pair
"""
from __future__ import annotations

import argparse
import json
import os
import time
from concurrent.futures import ProcessPoolExecutor, as_completed
from dataclasses import replace
from pathlib import Path
from typing import Any, Dict, List, Optional

import numpy as np

from sim.io import git_commit
from sim.model import run_model
from sim.params import RunConfig, Scenario, load_params
from sim.storms import build_event_table

from .common import REPO_ROOT, dump_json, retention_curve

SEED_MOD = 2 ** 32


def realisation_seed(base_seed: int, i: int) -> int:
    return int((int(base_seed) * 1000003 + int(i)) % SEED_MOD)


def _metrics_row(res, i: int, seed_i: int) -> Dict[str, Any]:
    m = res.metrics
    rows = res.ledger.rows
    return {
        "i": i,
        "seed": seed_i,
        "t_end": float(res.config["t_end"]),
        "T_first_fail_w": m["T_first_fail_w"]["value"],
        "T_first_fail_w_censored": m["T_first_fail_w"]["censored"],
        "T_first_fail_b": m["T_first_fail_b"]["value"],
        "T_first_fail_b_censored": m["T_first_fail_b"]["censored"],
        "T_safe_cum_w": m["T_safe_cum_w"],
        "T_safe_cum_b": m["T_safe_cum_b"],
        "T_recovery_median": m["T_recovery"]["median"],
        "T_recovery_censored": m["T_recovery"]["censored"],
        "E_w": m["E_w"],
        "E_b": m["E_b"],
        "w_end_min": m["w_end_min"],
        "w_end_mean": m["w_end_mean"],
        "exhausted_frac": m["exhausted_frac"],
        "placed": rows[-1]["placed_cum"] if rows else 0.0,
        "cost": res.budget["cost_used"],
        "n_projects": res.budget["n_projects"],
        "n_events": res.n_events_applied,
        "residual_rel_max": res.ledger.max_abs_rel,
    }


def run_realisation(task: Dict[str, Any]) -> Dict[str, Any]:
    """One MC realisation (also used as the process-pool entry point)."""
    params = load_params(task["params_path"])
    if task.get("overrides"):
        params = params.clone_with(task["overrides"])
    scenario = Scenario(task["scenario"], params, task.get("overrides") or {})
    run = RunConfig(
        scenario=task["scenario"], strategy=task["strategy"], bc=task["bc"],
        seed=int(task["seed"]), t_end=float(task["t_end"]), dx=float(task["dx"]),
        dt=float(task["dt"]), Lb=float(task["Lb"]), phi_shape=task["phi_shape"],
        cost_model=task["cost_model"], supply=task["supply"],
        forced_events=list(scenario.forced_events), label=task.get("label", "mc"),
    )
    table = build_event_table(scenario, run.seed, run.t_end, run.Lb, run.phi_shape,
                              run.forced_events)
    nour = run_model(params, scenario, run, events=table, store_fields=False)
    row = _metrics_row(nour, int(task["i"]), int(task["seed"]))
    row.update({"scenario": task["scenario"], "strategy": task["strategy"],
                "bc": task["bc"], "supply": task["supply"],
                "cost_model": task["cost_model"]})
    if task.get("pair"):
        base_run = replace(run, strategy="none", placements=None)
        base = run_model(params, scenario, base_run, events=table, store_fields=False)
        H = float(params["H_dep"])
        times = [t for t in (1.0, 5.0, 15.0) if t <= run.t_end + 1e-9]
        ret = retention_curve(nour, base, times, H)
        row.update(ret)
    return row


# ---------------------------------------------------------------------------
# Summary statistics
# ---------------------------------------------------------------------------
def kaplan_meier(times: np.ndarray, observed: np.ndarray, qs=(0.1, 0.5, 0.9)):
    """Right-censored quantiles via Kaplan-Meier (censoring at ``t_end``)."""
    times = np.asarray(times, dtype=float)
    observed = np.asarray(observed, dtype=bool)
    if times.size == 0:
        return {}
    uniq = np.unique(times)
    S = 1.0
    surv_t, surv_s = [0.0], [1.0]
    for t in uniq:
        at_risk = np.sum(times >= t)
        d = np.sum((times == t) & observed)
        if at_risk > 0 and d > 0:
            S *= 1.0 - d / at_risk
        surv_t.append(float(t))
        surv_s.append(S)
    surv_t = np.asarray(surv_t)
    surv_s = np.asarray(surv_s)
    out = {"km_censored_fraction": float(1.0 - observed.mean())}
    for q in qs:
        hit = np.flatnonzero(surv_s <= 1.0 - q)
        out[f"km_P{int(q*100)}"] = float(surv_t[hit[0]]) if hit.size else None
    return out


def summarise(rows: List[Dict[str, Any]]) -> Dict[str, Any]:
    out: Dict[str, Any] = {"n": len(rows)}
    for key in ("E_w", "E_b", "T_safe_cum_w", "T_safe_cum_b", "w_end_min",
                "w_end_mean", "exhausted_frac", "R_ret_1yr", "R_ret_5yr",
                "R_ret_15yr", "placed", "cost", "n_projects"):
        vals = np.array([r[key] for r in rows if r.get(key) is not None], dtype=float)
        if vals.size == 0:
            out[key] = {}
            continue
        out[key] = {f"P{int(q*100)}": float(np.quantile(vals, q))
                    for q in (0.1, 0.5, 0.9)}
        out[key]["mean"] = float(vals.mean())
    for key in ("T_first_fail_w", "T_first_fail_b"):
        t_end = float(rows[0].get("t_end", 15.0))
        # right-censored at the end of the run: keep the censored observation at
        # t_end (dropping it would bias the quantiles upward)
        times = np.array([r[key] if r[key] is not None else t_end for r in rows],
                         dtype=float)
        observed = np.array([not r[key + "_censored"] for r in rows], dtype=bool)
        out[key] = kaplan_meier(times, observed)
        obs_vals = times[observed]
        out[key]["observed_median"] = float(np.median(obs_vals)) if obs_vals.size else None
    rec = np.array([r["T_recovery_median"] for r in rows if r["T_recovery_median"] is not None])
    out["T_recovery"] = {"observed_median": float(np.median(rec)) if rec.size else None,
                         "n_observed": int(rec.size)}
    out["residual_rel_max"] = float(max(r["residual_rel_max"] for r in rows))
    return out


def resummarise(outdir: str | Path, t_end: Optional[float] = None) -> Dict[str, Any]:
    """Recompute ``mc_summary.json`` from an existing ``mc_results.csv``.

    Useful after fixing a statistic: the expensive realisations are not re-run.
    """
    import csv
    outdir = Path(outdir)
    with (outdir / "mc_results.csv").open(encoding="utf-8") as fh:
        raw = list(csv.DictReader(fh))
    rows: List[Dict[str, Any]] = []
    for r in raw:
        row: Dict[str, Any] = {}
        for k, v in r.items():
            if v in ("True", "False"):
                row[k] = v == "True"
            elif v == "":
                row[k] = None
            else:
                try:
                    row[k] = float(v)
                except (TypeError, ValueError):
                    row[k] = v
        if t_end is not None:
            row["t_end"] = float(t_end)
        rows.append(row)
    summary_path = outdir / "mc_summary.json"
    payload = json.loads(summary_path.read_text(encoding="utf-8")) if summary_path.exists() else {}
    payload["summary"] = summarise(rows)
    payload.setdefault("meta", {})["resummarised"] = True
    dump_json(summary_path, payload)
    return payload


def build_tasks(params, run, n: int, pair: bool) -> List[Dict[str, Any]]:
    tasks = []
    for i in range(n):
        seed_i = realisation_seed(run.seed, i)
        tasks.append({
            "i": i, "seed": seed_i, "params_path": str(params.path),
            "overrides": run.overrides, "scenario": run.scenario,
            "strategy": run.strategy, "bc": run.bc, "t_end": run.t_end,
            "dx": run.dx, "dt": run.dt, "Lb": run.Lb, "phi_shape": run.phi_shape,
            "cost_model": run.cost_model, "supply": run.supply,
            "pair": bool(pair), "label": run.label,
        })
    return tasks


def run_mc(tasks: List[Dict[str, Any]], jobs: int = 1) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    if jobs <= 1:
        for task in tasks:
            rows.append(run_realisation(task))
    else:
        with ProcessPoolExecutor(max_workers=jobs) as pool:
            futs = [pool.submit(run_realisation, task) for task in tasks]
            for fut in as_completed(futs):
                rows.append(fut.result())
    rows.sort(key=lambda r: r["i"])
    return rows


def write_mc(outdir: Path, rows: List[Dict[str, Any]], meta: Dict[str, Any]) -> Dict[str, Any]:
    import csv
    outdir = Path(outdir)
    outdir.mkdir(parents=True, exist_ok=True)
    keys = sorted({k for r in rows for k in r})
    with (outdir / "mc_results.csv").open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=keys)
        writer.writeheader()
        writer.writerows(rows)
    payload = {"meta": meta, "summary": summarise(rows)}
    dump_json(outdir / "mc_summary.json", payload)
    return payload


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description="Monte-Carlo over storm realisations")
    p.add_argument("--config", default=str(REPO_ROOT / "configs" / "S2.yaml"))
    p.add_argument("--out", required=True)
    p.add_argument("--n", type=int, default=200)
    p.add_argument("--jobs", type=int, default=min(8, os.cpu_count() or 1))
    p.add_argument("--strategy", default=None)
    p.add_argument("--seed", type=int, default=None)
    p.add_argument("--t-end", type=float, default=None)
    p.add_argument("--pair", action="store_true", help="run paired baseline for retention")
    p.add_argument("--tag", default="")
    args = p.parse_args(argv)

    from sim.params import load_config
    params, scenario, run = load_config(args.config)
    if args.strategy:
        run = replace(run, strategy=args.strategy)
    over = {}
    if args.seed is not None:
        over["seed"] = args.seed
    if args.t_end is not None:
        over["t_end"] = args.t_end
    if over:
        run = replace(run, **over)

    t0 = time.time()
    tasks = build_tasks(params, run, args.n, args.pair)
    rows = run_mc(tasks, args.jobs)
    runtime = time.time() - t0
    outdir = Path(args.out)
    meta = {
        "config": str(params.path), "scenario": run.scenario,
        "strategy": run.strategy, "bc": run.bc, "n": args.n,
        "base_seed": run.seed, "pair": bool(args.pair),
        "seed_rule": "seed*1000003+i mod 2^32",
        "t_end": run.t_end, "dx": run.dx, "dt": run.dt,
        "runtime_s": runtime, "git_commit": git_commit(),
        "overrides": run.overrides, "n_workers": args.jobs, "tag": args.tag,
    }
    payload = write_mc(outdir, rows, meta)
    print(f"[mc] {run.scenario}/{run.strategy} n={args.n} in {runtime:.1f}s -> {outdir}")
    print(f"     E_b P10/P50/P90 = {payload['summary']['E_b']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
