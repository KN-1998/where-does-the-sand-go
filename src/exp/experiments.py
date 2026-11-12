# -*- coding: utf-8 -*-
"""Experiment drivers E0-E7 (CODER_SPEC §7, SCENARIOS_STRATEGIES §7).

Each experiment writes ``results/E<n>_<tag>/…`` with the per-run artefacts and a
``summary.json`` + ``summary.md`` table.  Runs are resumable: an existing run
directory is reused unless ``--force`` is given.

Usage::

    python -m exp.experiments --only E0,E1 --jobs 8
    python -m exp.experiments --only E2 --n-mc 1000 --jobs 8
"""
from __future__ import annotations

import argparse
import csv
import time
from dataclasses import replace
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence

import numpy as np

from sim.io import git_commit, write_results
from sim.model import run_model
from sim.params import RunConfig, Scenario, load_params
from sim.storms import EventTable, StormEvent, build_event_table, build_timing_table

from .common import REPO_ROOT, RESULTS, central_sand, dump_json, retention_curve
from .mc import build_tasks, run_mc, write_mc

PARAMS_PATH = REPO_ROOT / "modeling" / "params.yaml"
DEFAULT_JOBS = 8


# ---------------------------------------------------------------------------
# small helpers
# ---------------------------------------------------------------------------
def _mk_run(scenario: str, strategy: str = "none", bc: str = "open", seed: int = 42,
            t_end: float = 15.0, dx: float = 25.0, dt: float = 0.02,
            Lb: float = 4500.0, cost_model: str = "all_in", supply: str = "local",
            overrides: Optional[Dict[str, Any]] = None,
            forced_events: Optional[Sequence[Dict[str, Any]]] = None,
            label: str = "") -> RunConfig:
    return RunConfig(scenario=scenario, strategy=strategy, bc=bc, seed=seed,
                     t_end=t_end, dx=dx, dt=dt, Lb=Lb, cost_model=cost_model,
                     supply=supply, overrides=dict(overrides or {}),
                     forced_events=list(forced_events or []), label=label)


def _params(overrides: Optional[Dict[str, Any]] = None):
    p = load_params(PARAMS_PATH)
    if overrides:
        p = p.clone_with(overrides)
    return p


def _scenario(name: str, params, overrides: Optional[Dict[str, Any]] = None) -> Scenario:
    sc = Scenario(name, params, overrides)
    return sc


def _table(sc: Scenario, run: RunConfig) -> EventTable:
    return build_event_table(sc, run.seed, run.t_end, run.Lb, run.phi_shape,
                             run.forced_events)


def _row(res, **extra) -> Dict[str, Any]:
    m = res.metrics
    r = res.ledger.rows[-1]
    row = {
        "scenario": res.config["scenario"],
        "strategy": res.config["strategy"],
        "bc": res.config["bc"],
        "supply": res.config["supply"],
        "cost_model": res.config["cost_model"],
        "label": res.config["label"],
        "E_w": m["E_w"],
        "E_b": m["E_b"],
        "T_safe_cum_w": m["T_safe_cum_w"],
        "T_safe_cum_b": m["T_safe_cum_b"],
        "T_first_fail_w": m["T_first_fail_w"]["value"],
        "T_first_fail_b": m["T_first_fail_b"]["value"],
        "w_end_min": m["w_end_min"],
        "w_end_mean": m["w_end_mean"],
        "exhausted_frac": m["exhausted_frac"],
        "placed": r["placed_cum"],
        "cost": res.budget["cost_used"],
        "n_projects": res.budget["n_projects"],
        "n_events": res.n_events_applied,
        "residual_rel_max": res.ledger.max_abs_rel,
        "protected_shoreline_years": m["T_safe_cum_w"] * res.grid.n_central * res.grid.dx,
    }
    row.update(extra)
    return row


def _destinations(nour, base) -> Dict[str, float]:
    n, b = nour.ledger.rows[-1], base.ledger.rows[-1]
    retained = ((n["V_domain"] + n["O_domain"]) - (b["V_domain"] + b["O_domain"]))
    flux = ((n["flux_outer_left_cum"] + n["flux_outer_right_cum"])
            - (b["flux_outer_left_cum"] + b["flux_outer_right_cum"]))
    offshore = n["offshore_loss_cum"] - b["offshore_loss_cum"]
    chronic = n["chronic_loss_cum"] - b["chronic_loss_cum"]
    placed = n["placed_cum"]
    return {
        "placed": placed,
        "retained_domain": retained,
        "flux_out_domain": flux,
        "offshore_loss": offshore,
        "chronic_diff": chronic,
        "split_residual": placed - (retained + flux + offshore),
    }


def _row_from_json(payload: Dict[str, Any]) -> Dict[str, Any]:
    d = payload.get("duration", {})
    m = payload.get("mass", {})
    c = payload.get("cost", {})
    st = payload.get("state", {})
    meta = payload.get("meta", {})
    return {
        "scenario": meta.get("scenario"), "strategy": meta.get("strategy"),
        "bc": meta.get("bc"), "label": meta.get("label"),
        "E_w": payload.get("exposure", {}).get("E_w"),
        "E_b": payload.get("exposure", {}).get("E_b"),
        "T_safe_cum_w": d.get("T_safe_cum_w"), "T_safe_cum_b": d.get("T_safe_cum_b"),
        "T_first_fail_w": (d.get("T_first_fail_w") or {}).get("value"),
        "T_first_fail_b": (d.get("T_first_fail_b") or {}).get("value"),
        "w_end_min": st.get("w_end_min"), "w_end_mean": st.get("w_end_mean"),
        "exhausted_frac": st.get("exhausted_frac"),
        "placed": m.get("placed"), "cost": c.get("cost_used"),
        "n_projects": c.get("n_projects"),
        "n_events": meta.get("n_events_applied"),
        "residual_rel_max": m.get("residual_rel_max"),
        "protected_shoreline_years": (d.get("T_safe_cum_w") or 0.0) * 5000.0,
    }


def _save_run(outdir: Path, res, retention=None, fields=False, extra_meta=None):
    write_results(outdir, res, retention=retention, runtime_s=None,
                  extra_meta=extra_meta, write_fields=fields)


def _paired(params, sc: Scenario, run: RunConfig, table: EventTable,
            fields: bool = False):
    t0 = time.time()
    nour = run_model(params, sc, run, events=table, store_fields=fields)
    base_run = replace(run, strategy="none", placements=None,
                       label=run.label + "_base")
    base = run_model(params, sc, base_run, events=table, store_fields=False)
    H = float(params["H_dep"])
    times = [t for t in (1.0, 5.0, 15.0) if t <= run.t_end + 1e-9]
    ret = retention_curve(nour, base, times, H)
    dest = _destinations(nour, base)
    return nour, base, ret, dest, time.time() - t0


def _write_summary(outdir: Path, name: str, rows: List[Dict[str, Any]],
                   extra: Optional[Dict[str, Any]] = None) -> None:
    outdir.mkdir(parents=True, exist_ok=True)
    payload = {"experiment": name, "git_commit": git_commit(),
               "generated_rows": rows, **(extra or {})}
    dump_json(outdir / "summary.json", payload)
    cols = ["label", "scenario", "strategy", "bc", "supply", "cost_model",
            "E_w", "E_b", "T_safe_cum_w", "T_safe_cum_b", "placed", "cost",
            "n_projects", "retention_R_ret_1yr", "retention_R_ret_5yr",
            "retention_R_ret_15yr", "residual_rel_max",
            "E_b_P50", "E_w_P50", "Tff_w_km_P10", "Tff_w_km_P50", "Tff_w_km_P90",
            "Tff_b_km_P50", "T_safe_w_P50", "T_safe_b_P50",
            "R_ret_1yr_P50", "R_ret_5yr_P50"]
    cols = [c for c in cols if any(c in r for r in rows)]
    lines = ["| " + " | ".join(cols) + " |", "|" + "---|" * len(cols)]
    for r in rows:
        cells = []
        for c in cols:
            v = r.get(c)
            if isinstance(v, float):
                cells.append(f"{v:.4g}")
            else:
                cells.append("—" if v is None else str(v))
        lines.append("| " + " | ".join(cells) + " |")
    (outdir / "summary.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def _mc_meta(sc: Scenario, run: RunConfig, n: int, pair: bool, runtime: float,
             overrides: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    return {"scenario": run.scenario, "strategy": run.strategy, "bc": run.bc,
            "n": n, "base_seed": run.seed, "pair": pair,
            "seed_rule": "seed*1000003+i mod 2^32", "t_end": run.t_end,
            "dx": run.dx, "dt": run.dt, "runtime_s": runtime,
            "git_commit": git_commit(), "overrides": overrides or {},
            "scenario_law": sc.as_dict()}


# ---------------------------------------------------------------------------
# L0 un-nourished baseline for the D11 double-counting check (VALIDATION §1.5)
# ---------------------------------------------------------------------------
def exp_L0(jobs: int, n_mc: int = 300, force: bool = False) -> Dict[str, Any]:
    """L0: total shoreline retreat of the un-nourished field, calibers (i)/(ii).

    Caliber (i) keeps the observed rho_e and adds storms -> the model is expected
    to retreat ~+22.5% faster than the field's own corridor mean (2.31 m/yr).
    Caliber (ii) removes the storm contribution from the field (rho_bg=1.178,
    a_h=1.73) and adds it back explicitly -> total returns to ~2.31 m/yr.
    """
    out = RESULTS / "L0"
    rows: Dict[str, Any] = {}
    for tag, over in (("i", {}), ("ii", {"rho_e": 1.178, "rho_e_hotspot_amp": 1.73})):
        params = _params(over) if over else _params()
        sc = _scenario("base", params)
        run = _mk_run("base", "none", t_end=15.0, overrides=over, label=f"L0_{tag}")
        mc_dir = out / f"caliber_{tag}_mc"
        if force or not (mc_dir / "mc_summary.json").exists():
            t0 = time.time()
            tasks = build_tasks(params, run, n_mc, pair=False)
            mc_rows = run_mc(tasks, jobs)
            payload = write_mc(mc_dir, mc_rows, _mc_meta(sc, run, n_mc, False,
                                                        time.time() - t0, over))
        else:
            import json
            payload = json.loads((mc_dir / "mc_summary.json").read_text(encoding="utf-8"))
        s = payload["summary"]
        # corridor mean of rho_e(x) computed from the field itself (params'
        # rho_e_corridor_mean is a derived constant and is NOT updated by overrides)
        field_mean = (float(params["rho_e"])
                      * (1.0 + float(params["rho_e_hotspot_amp"]) * np.sqrt(2.0 * np.pi)
                         * float(params["sigma_h"]) / 5000.0))
        storm = sc.rho_storm(0.0)
        # reference: the same field with storms switched off (one deterministic run)
        p0 = params.clone_with({"lambda_s": 0.0})
        sc0 = _scenario("base", p0)
        run0 = _mk_run("base", "none", t_end=15.0, overrides={"lambda_s": 0.0},
                       label=f"L0_{tag}_nostorm")
        res0 = run_model(p0, sc0, run0, events=EventTable([]), store_fields=False)
        g0 = res0.grid
        hot0 = np.abs(g0.x) <= 750.0
        rate_nostorm = -float(res0.y_end[g0.central].mean()) / 15.0
        rows[tag] = {
            "field_mean_rho": field_mean,
            "rho_storm_potential": storm,
            "expected_total": field_mean + storm,
            "expected_bias_vs_field": storm / field_mean,
            "retreat_corridor_P50": s.get("retreat_rate_corridor", {}).get("P50"),
            "retreat_corridor_mean": s.get("retreat_rate_corridor", {}).get("mean"),
            "retreat_hotspot_P50": s.get("retreat_rate_hotspot", {}).get("P50"),
            "retreat_corridor_nostorm": rate_nostorm,
            "realised_storm_contribution": (
                None if s.get("retreat_rate_corridor", {}).get("P50") is None
                else s["retreat_rate_corridor"]["P50"] - rate_nostorm),
            "bias_vs_field": (
                None if s.get("retreat_rate_corridor", {}).get("P50") is None
                else s["retreat_rate_corridor"]["P50"] / field_mean - 1.0),
            "E_b_P50": s.get("E_b", {}).get("P50"),
        }
        print(f"[L0] caliber ({tag}): corridor P50="
              f"{rows[tag]['retreat_corridor_P50']}, expected={field_mean + storm:.2f}")
    out.mkdir(parents=True, exist_ok=True)
    dump_json(out / "summary.json", {"git_commit": git_commit(), "rows": rows})
    return {"rows": rows}


# ---------------------------------------------------------------------------
# E0 baseline
# ---------------------------------------------------------------------------
def exp_E0(jobs: int, n_mc: int, force: bool = False) -> Dict[str, Any]:
    out = RESULTS / "E0"
    rows = []
    details = {}
    for scn in ("S1", "S2", "S3"):
        params = _params()
        sc = _scenario(scn, params)
        run = _mk_run(scn, "none", label=f"E0_{scn}")
        table = _table(sc, run)
        run_dir = out / f"{scn}_deterministic"
        if force or not (run_dir / "results.json").exists():
            t0 = time.time()
            res = run_model(params, sc, run, events=table, store_fields=True)
            _save_run(run_dir, res, fields=True, extra_meta={"experiment": "E0"})
            elapsed = time.time() - t0
            rows.append(_row(res))
        else:
            import json
            payload = json.loads((run_dir / "results.json").read_text(encoding="utf-8"))
            rows.append(_row_from_json(payload))
        mc_dir = out / f"{scn}_mc"
        if force or not (mc_dir / "mc_summary.json").exists():
            t0 = time.time()
            run_mc_cfg = replace(run, strategy="none")
            tasks = build_tasks(params, run_mc_cfg, n_mc, pair=False)
            mc_rows = run_mc(tasks, jobs)
            payload = write_mc(mc_dir, mc_rows, _mc_meta(sc, run_mc_cfg, n_mc, False,
                                                        time.time() - t0))
        else:
            import json
            payload = json.loads((mc_dir / "mc_summary.json").read_text(encoding="utf-8"))
        details[scn] = payload["summary"]
        print(f"[E0] {scn}: deterministic + MC n={n_mc} done")
    _write_summary(out, "E0", rows, {"mc": details})
    return {"rows": rows, "mc": details}


# ---------------------------------------------------------------------------
# E1 placement comparison (same volume, idealised t=0)
# ---------------------------------------------------------------------------
E1_VOLUME = 1.0e6


def _placement_specs(shape: str, volume: float, t: float = 0.0) -> List[Dict[str, Any]]:
    if shape == "uniform":
        return [{"t": t, "xc": 0.0, "len": 5000.0, "volume": volume, "tag": "uniform"}]
    if shape == "hotspot":
        return [{"t": t, "xc": 0.0, "len": 1000.0, "volume": volume, "tag": "hotspot"}]
    if shape == "multi":
        centres = (-1800.0, -900.0, 0.0, 900.0, 1800.0)
        return [{"t": t, "xc": c, "len": 500.0, "volume": volume / 5.0,
                 "tag": f"multi_{c:+.0f}"} for c in centres]
    raise KeyError(shape)


def exp_E1(jobs: int, force: bool = False) -> Dict[str, Any]:
    out = RESULTS / "E1"
    params = _params()
    sc = _scenario("S1", params)
    run = _mk_run("S1", "scripted", label="E1")
    table = _table(sc, run)
    rows = []
    for shape in ("uniform", "hotspot", "multi"):
        specs = _placement_specs(shape, E1_VOLUME)
        r = replace(run, strategy="scripted", placements=specs, label=f"E1_{shape}")
        run_dir = out / shape
        if force or not (run_dir / "results.json").exists():
            nour, base, ret, dest, elapsed = _paired(params, sc, r, table,
                                                     fields=(shape == "uniform"))
            _save_run(run_dir, nour, retention=ret, fields=(shape == "uniform"),
                      extra_meta={"experiment": "E1", "destinations": dest})
            _save_run(run_dir / "baseline", base, fields=False,
                      extra_meta={"experiment": "E1"})
            dest["runtime_s"] = elapsed
        else:
            import json
            payload = json.loads((run_dir / "results.json").read_text(encoding="utf-8"))
            ret = payload.get("retention", {})
            dest = json.loads((run_dir / "meta.json").read_text(encoding="utf-8")).get("destinations", {})
            nour = None
            base = None
        if nour is not None:
            row = _row(nour)
            _save_destination_timeline(run_dir / "destinations.csv", nour, base)
        else:
            row = _row_from_json(payload)
        row.update({"label": shape, "scenario": "S1", "strategy": "placement",
                    "shape": shape, "placed": E1_VOLUME,
                    "retention_R_ret_1yr": ret.get("R_ret_1yr"),
                    "retention_R_ret_5yr": ret.get("R_ret_5yr"),
                    **{k: v for k, v in dest.items() if k != "runtime_s"}})
        rows.append(row)
        print(f"[E1] {shape} done")
    _write_summary(out, "E1", rows, {"volume": E1_VOLUME})
    return {"rows": rows}


def _save_destination_timeline(path: Path, nour, base) -> None:
    with path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.writer(fh)
        writer.writerow(["t", "placed", "retained_domain", "flux_out_domain",
                         "offshore_loss", "chronic_diff", "R_c_diff"])
        for rn, rb in zip(nour.ledger.rows, base.ledger.rows):
            retained = (rn["V_domain"] + rn["O_domain"]) - (rb["V_domain"] + rb["O_domain"])
            flux = ((rn["flux_outer_left_cum"] + rn["flux_outer_right_cum"])
                    - (rb["flux_outer_left_cum"] + rb["flux_outer_right_cum"]))
            offshore = rn["offshore_loss_cum"] - rb["offshore_loss_cum"]
            chronic = rn["chronic_loss_cum"] - rb["chronic_loss_cum"]
            rc = rn["R_c_cum"] - rb["R_c_cum"]
            writer.writerow([rn["t"], rn["placed_cum"], retained, flux, offshore,
                             chronic, rc])


# ---------------------------------------------------------------------------
# E2 three scenarios MC (strategy once)
# ---------------------------------------------------------------------------
def exp_E2(jobs: int, n_mc: int, force: bool = False) -> Dict[str, Any]:
    out = RESULTS / "E2"
    details = {}
    rows = []
    for scn in ("S1", "S2", "S3"):
        params = _params()
        sc = _scenario(scn, params)
        run = _mk_run(scn, "once", label=f"E2_{scn}")
        mc_dir = out / f"{scn}_mc"
        if force or not (mc_dir / "mc_summary.json").exists():
            t0 = time.time()
            tasks = build_tasks(params, run, n_mc, pair=True)
            mc_rows = run_mc(tasks, jobs)
            payload = write_mc(mc_dir, mc_rows, _mc_meta(sc, run, n_mc, True,
                                                        time.time() - t0))
        else:
            import json
            payload = json.loads((mc_dir / "mc_summary.json").read_text(encoding="utf-8"))
        details[scn] = payload["summary"]
        s = payload["summary"]
        rows.append({"label": scn, "scenario": scn, "strategy": "once",
                     "E_b_P50": s["E_b"].get("P50"),
                     "E_w_P50": s["E_w"].get("P50"),
                     "Tff_w_km_P50": s["T_first_fail_w"].get("km_P50"),
                     "Tff_w_km_P10": s["T_first_fail_w"].get("km_P10"),
                     "Tff_w_km_P90": s["T_first_fail_w"].get("km_P90"),
                     "Tff_b_km_P50": s["T_first_fail_b"].get("km_P50"),
                     "T_safe_w_P50": s["T_safe_cum_w"].get("P50"),
                     "T_safe_b_P50": s["T_safe_cum_b"].get("P50"),
                     "R_ret_1yr_P50": s.get("R_ret_1yr", {}).get("P50"),
                     "R_ret_5yr_P50": s.get("R_ret_5yr", {}).get("P50")})
        print(f"[E2] {scn} MC n={n_mc} done")
    _write_summary(out, "E2", rows, {"mc": details})
    return {"rows": rows, "mc": details}


# ---------------------------------------------------------------------------
# E3 storm timing
# ---------------------------------------------------------------------------
def exp_E3(jobs: int, force: bool = False) -> Dict[str, Any]:
    out = RESULTS / "E3"
    params = _params()
    sc = _scenario("S2", params)
    run = _mk_run("S2", "once", label="E3")
    rows = []
    rng = np.random.default_rng(2027)
    mags = [8.0 * float(np.exp(sc.sigma_ln * rng.standard_normal())) for _ in range(6)]
    groups = {
        "early": [0.4, 1.2, 2.0, 2.8, 3.6, 4.4],
        "spread": [1.0, 3.5, 6.0, 8.5, 11.0, 13.5],
        "late": [10.2, 11.2, 12.2, 13.2, 14.2, 14.8],
    }
    for name, times in groups.items():
        table = build_timing_table(sc, run.seed, times, dy_pot=mags)
        r = replace(run, label=f"E3_{name}", forced_events=[])
        run_dir = out / name
        if force or not (run_dir / "results.json").exists():
            res = run_model(params, sc, r, events=table, store_fields=True)
            _save_run(run_dir, res, fields=True, extra_meta={"experiment": "E3"})
        else:
            res = None
        if res is not None:
            rows.append(_row(res, timing=name))
            w = res.w0[None, :] + res.y
            g = res.grid
            i_c = int(np.argmin(np.abs(g.x)))
            rows[-1]["w_end_centre"] = float(w[-1, i_c])
            rows[-1]["w_min_ever"] = float(res.metrics["w_min_ever"])
        print(f"[E3] {name}: {times}")
    _write_summary(out, "E3", rows, {"magnitudes": mags, "groups": groups})
    return {"rows": rows}


# ---------------------------------------------------------------------------
# E4 strategies
# ---------------------------------------------------------------------------
def exp_E4(jobs: int, force: bool = False) -> Dict[str, Any]:
    out = RESULTS / "E4"
    rows = []
    main_details = {}
    combos = [("local", "all_in"), ("external", "all_in"),
              ("local", "marginal_plus_fixed")]
    for supply, cost_model in combos:
        tag = f"{supply}_{cost_model}"
        for scn in ("S1", "S2", "S3"):
            params = _params()
            sc = _scenario(scn, params)
            table = _table(sc, _mk_run(scn, "once", supply=supply,
                                       cost_model=cost_model))
            for strategy in ("once", "repeat", "targeted", "adaptive"):
                run = _mk_run(scn, strategy, supply=supply, cost_model=cost_model,
                              label=f"E4_{tag}_{scn}_{strategy}")
                run_dir = out / tag / scn / strategy
                if force or not (run_dir / "results.json").exists():
                    nour, base, ret, dest, elapsed = _paired(params, sc, run, table)
                    _save_run(run_dir, nour, retention=ret,
                              extra_meta={"experiment": "E4", "destinations": dest})
                else:
                    import json
                    payload = json.loads((run_dir / "results.json").read_text(encoding="utf-8"))
                    ret = payload.get("retention", {})
                    nour = None
                if nour is not None:
                    row = _row(nour)
                    row["retreat_decisions"] = sum(
                        1 for e in nour.strategy_log if e.get("decision") == "retreat")
                else:
                    row = _row_from_json(payload)
                row.update({"label": f"{tag}/{scn}/{strategy}", "supply": supply,
                            "cost_model": cost_model,
                            "retention_R_ret_1yr": ret.get("R_ret_1yr"),
                            "retention_R_ret_5yr": ret.get("R_ret_5yr")})
                rows.append(row)
                print(f"[E4] {tag} {scn} {strategy}")

    # c0 scan: only marginal_plus_fixed (D18); S2
    c0_rows = []
    scan_dir = out / "c0_scan_S2"
    scan_dir.mkdir(parents=True, exist_ok=True)
    for c0e6 in (0.0, 2.0, 4.0, 6.0, 8.0, 10.0):
        for strategy in ("once", "repeat", "targeted", "adaptive"):
            params = _params({"c0": c0e6 * 1e6})
            sc = _scenario("S2", params)
            run = _mk_run("S2", strategy, cost_model="marginal_plus_fixed",
                          overrides={"c0": c0e6 * 1e6},
                          label=f"E4_c0_{c0e6:.0f}M_{strategy}")
            rdir = scan_dir / f"c0_{c0e6:.0f}M" / strategy
            if force or not (rdir / "results.json").exists():
                table = _table(sc, run)
                res = run_model(params, sc, run, events=table, store_fields=False)
                _save_run(rdir, res, extra_meta={"experiment": "E4_c0"})
            res = None
            import json
            payload = json.loads((rdir / "results.json").read_text(encoding="utf-8"))
            c0_rows.append({"c0_M": c0e6, "strategy": strategy,
                            "E_b": payload["exposure"]["E_b"],
                            "E_w": payload["exposure"]["E_w"],
                            "T_safe_cum_b": payload["duration"]["T_safe_cum_b"],
                            "cost": payload["cost"]["cost_used"],
                            "n_projects": payload["cost"]["n_projects"],
                            "placed": payload["mass"]["placed"]})
    _write_summary(out, "E4", rows, {"c0_scan_S2": c0_rows})
    import json
    dump_json(scan_dir / "c0_scan.json", {"rows": c0_rows})
    return {"rows": rows, "c0": c0_rows}


# ---------------------------------------------------------------------------
# E5 OAT sensitivity
# ---------------------------------------------------------------------------
OAT = [
    ("D_diff", "D", 1.0e5, 8.0e5),
    ("H_dep", "H", 8.0, 12.0),
    ("rho_e", "rho_e", 1.2, 2.1),
    ("rho_e_hotspot_amp", "a_h", 0.5, 2.0),
    ("u_drift", "u", 0.0, 150.0),
    ("lambda_s", "lambda_s", 0.2, 0.8),
    ("dy_ref", "dy_ref", 4.0, 12.0),
    ("k_rec", "k_rec", 0.33, 2.0),
    ("lam_off", "lam_off", 0.02, 0.3),
    ("w0_far", "w0_far", 20.0, 40.0),
    ("w_mgmt", "w_mgmt", 12.0, 32.0),
    ("V15_total", "V15_total", 3.5e6, 6.8e6),
    ("V_event_max", "V_event_max", 1.5e6, 3.5e6),
    ("S_borrow_total", "S_borrow_total", 1.5e6, 3.2e6),
]


def exp_E5(jobs: int, force: bool = False, sobol: bool = False) -> Dict[str, Any]:
    out = RESULTS / "E5"
    base_params = _params()
    base_sc = _scenario("S2", base_params)
    base_run = _mk_run("S2", "once", label="E5_base")
    base_table = _table(base_sc, base_run)
    base_res = run_model(base_params, base_sc, base_run, events=base_table,
                         store_fields=False)
    base_row = _row(base_res)
    rows = [{"param": "base", "value": None, **base_row, "label": "base"}]
    # Parameters that enter rho_storm: leaving the scenario scale free would make
    # the fixed corridor-mean target *compensate* the change (lower lambda_s ->
    # more chronic erosion), so the tornado would measure the split, not the storm
    # effect.  Freeze the S2 scale for this group.  [自决, reported in PROGRESS]
    storm_group = {"lambda_s", "dy_ref", "k_rec", "lam_off"}
    base_scale = base_sc.rho_scale(0.0)
    for key, name, low, high in OAT:
        for tag, val in (("low", low), ("high", high)):
            params = base_params.clone_with({key: val})
            sc_over = {"rho_e_scale": base_scale} if key in storm_group else None
            sc = _scenario("S2", params, sc_over)
            table = _table(sc, base_run)
            run_dir = out / f"{key}_{tag}"
            if force or not (run_dir / "results.json").exists():
                res = run_model(params, sc, replace(base_run, overrides={key: val},
                                                    label=f"E5_{key}_{tag}"),
                                events=table, store_fields=False)
                _save_run(run_dir, res, extra_meta={"experiment": "E5",
                                                    "rho_e_scale_note": sc_over})
            else:
                import json
                res = None
            if res is not None:
                r = _row(res)
            else:
                import json
                p = json.loads((run_dir / "results.json").read_text(encoding="utf-8"))
                r = {"E_w": p["exposure"]["E_w"], "E_b": p["exposure"]["E_b"],
                     "T_safe_cum_b": p["duration"]["T_safe_cum_b"],
                     "T_safe_cum_w": p["duration"]["T_safe_cum_w"],
                     "T_first_fail_w": p["duration"]["T_first_fail_w"]["value"],
                     "placed": p["mass"]["placed"], "cost": p["cost"]["cost_used"]}
            rows.append({"label": f"{key}_{tag}", "param": name, "value": val,
                         **r})
        print(f"[E5] OAT {key} done")
    extra = {}
    if sobol:
        extra = _sobol_light(jobs)
    _write_summary(out, "E5", rows, {"sobol": extra})
    return {"rows": rows, "sobol": extra}


SOBOL_GROUPS = [
    ["D_diff", "rho_e", "u_drift"],
    ["lambda_s", "dy_ref", "k_rec"],
    ["V15_total", "V_event_max", "S_borrow_total"],
]
SOBOL_BOUNDS = {
    "D_diff": (1.0e5, 8.0e5),
    "rho_e": (1.2, 2.1),
    "u_drift": (0.0, 150.0),
    "lambda_s": (0.2, 0.8),
    "dy_ref": (4.0, 12.0),
    "k_rec": (0.33, 2.0),
    "V15_total": (3.5e6, 6.8e6),
    "V_event_max": (1.5e6, 3.5e6),
    "S_borrow_total": (1.5e6, 3.2e6),
}


def _sobol_eval(task: Dict[str, Any]) -> tuple:
    """One Saltelli model evaluation (process-pool entry point)."""
    over = task["over"]
    params = _params(over)
    sc_over = {"rho_e_scale": task["scale"]} if task.get("scale") is not None else None
    sc = _scenario("S2", params, sc_over)
    run = _mk_run("S2", "once", overrides=over, label="E5_sobol")
    table = _table(sc, run)
    res = run_model(params, sc, run, events=table, store_fields=False)
    return float(res.metrics["E_b"]), float(res.metrics["E_w"])


def _sobol_light(jobs: int) -> Dict[str, Any]:
    """Saltelli first-order Sobol indices for the three required groups.

    Design: ``N*(k+2)`` evaluations per group (A, B, and one AB_j per parameter);
    ``S1_j = mean(yB * (yAB_j - yA)) / Var([yA, yB])``.
    """
    from concurrent.futures import ProcessPoolExecutor
    out = RESULTS / "E5" / "sobol"
    out.mkdir(parents=True, exist_ok=True)
    rng = np.random.default_rng(7)
    N = 96
    base_scale = _scenario("S2", _params()).rho_scale(0.0)
    results: Dict[str, Any] = {}
    for gi, group in enumerate(SOBOL_GROUPS):
        # the storm group is entangled with the scenario's rho_e scaling; freeze it
        freeze = base_scale if group == SOBOL_GROUPS[1] else None
        A = {k: rng.uniform(*SOBOL_BOUNDS[k], N) for k in group}
        B = {k: rng.uniform(*SOBOL_BOUNDS[k], N) for k in group}
        tasks = []
        for i in range(N):
            tasks.append({"over": {k: float(A[k][i]) for k in group},
                          "scale": freeze, "tag": "A"})
            tasks.append({"over": {k: float(B[k][i]) for k in group},
                          "scale": freeze, "tag": "B"})
            for j, key in enumerate(group):
                over = {k: float(A[k][i]) for k in group}
                over[key] = float(B[key][i])
                tasks.append({"over": over, "scale": freeze, "tag": f"AB{j}"})
        if jobs > 1:
            with ProcessPoolExecutor(max_workers=jobs) as pool:
                outs = list(pool.map(_sobol_eval, tasks))
        else:
            outs = [_sobol_eval(t) for t in tasks]
        pos = 0
        yA, yB = {"E_b": [], "E_w": []}, {"E_b": [], "E_w": []}
        yAB = {key: {"E_b": [], "E_w": []} for key in group}
        for i in range(N):
            for target in ("E_b", "E_w"):
                yA[target].append(outs[pos][0 if target == "E_b" else 1])
            pos += 1
            for target in ("E_b", "E_w"):
                yB[target].append(outs[pos][0 if target == "E_b" else 1])
            pos += 1
            for j, key in enumerate(group):
                for target in ("E_b", "E_w"):
                    yAB[key][target].append(outs[pos][0 if target == "E_b" else 1])
                pos += 1
        s1: Dict[str, Dict[str, float]] = {"E_b": {}, "E_w": {}}
        var = {}
        for target in ("E_b", "E_w"):
            ya = np.asarray(yA[target])
            yb = np.asarray(yB[target])
            var[target] = float(np.var(np.concatenate([ya, yb])))
            for key in group:
                yab = np.asarray(yAB[key][target])
                s1[target][key] = (float(np.mean(yb * (yab - ya)) / var[target])
                                   if var[target] > 0 else 0.0)
        results[f"group{gi+1}"] = {"params": group, "N": N, "n_runs": len(tasks),
                                   "S1": s1, "var": var,
                                   "bounds": {k: list(SOBOL_BOUNDS[k]) for k in group}}
        print(f"[E5] sobol group{gi+1} S1(E_w)="
              f"{ {k: round(v, 3) for k, v in s1['E_w'].items()} }")
    dump_json(out / "sobol_summary.json", results)
    return results


# ---------------------------------------------------------------------------
# E6 boundary conditions and domain size
# ---------------------------------------------------------------------------
def exp_E6(jobs: int, force: bool = False) -> Dict[str, Any]:
    out = RESULTS / "E6"
    rows = []
    params = _params()
    sc = _scenario("S1", params)
    table = _table(sc, _mk_run("S1", "once"))
    for bc in ("open", "zeroflux", "dirichlet"):
        run = _mk_run("S1", "once", bc=bc, label=f"E6_bc_{bc}")
        run_dir = out / f"bc_{bc}"
        if force or not (run_dir / "results.json").exists():
            nour, base, ret, dest, elapsed = _paired(params, sc, run, table)
            _save_run(run_dir, nour, retention=ret,
                      extra_meta={"experiment": "E6", "destinations": dest})
        else:
            import json
            payload = json.loads((run_dir / "results.json").read_text(encoding="utf-8"))
            ret = payload.get("retention", {})
            nour = None
        row = _row(nour) if nour is not None else _row_from_json(payload)
        row.update({"label": f"bc_{bc}", "bc": bc,
                    "retention_R_ret_1yr": ret.get("R_ret_1yr"),
                    "retention_R_ret_5yr": ret.get("R_ret_5yr"),
                    "retention_R_ret_15yr": ret.get("R_ret_15yr")})
        rows.append(row)
    # domain size sensitivity (open, 9 km vs 14 km)
    for Lb in (4500.0, 7000.0):
        run = _mk_run("S1", "once", bc="open", Lb=Lb, label=f"E6_Lb{Lb:.0f}")
        run_dir = out / f"domain_{int(Lb)}"
        if force or not (run_dir / "results.json").exists():
            nour, base, ret, dest, elapsed = _paired(params, sc, run, table)
            _save_run(run_dir, nour, retention=ret,
                      extra_meta={"experiment": "E6", "destinations": dest})
        else:
            import json
            payload = json.loads((run_dir / "results.json").read_text(encoding="utf-8"))
            ret = payload.get("retention", {})
            nour = None
        row = _row(nour) if nour is not None else _row_from_json(payload)
        row.update({"label": f"domain_{int(Lb)}", "bc": "open", "Lb": Lb,
                    "retention_R_ret_1yr": ret.get("R_ret_1yr"),
                    "retention_R_ret_5yr": ret.get("R_ret_5yr"),
                    "retention_R_ret_15yr": ret.get("R_ret_15yr")})
        rows.append(row)
    _write_summary(out, "E6", rows)
    return {"rows": rows}


# ---------------------------------------------------------------------------
# E7 phase diagram V x w_min
# ---------------------------------------------------------------------------
def exp_E7(jobs: int, force: bool = False) -> Dict[str, Any]:
    out = RESULTS / "E7"
    volumes = np.geomspace(1.0e5, 5.0e6, 12)
    w_mins = np.linspace(6.0, 22.0, 8)
    rows = []
    for shape in ("uniform", "hotspot"):
        for V in volumes:
            for wmin in w_mins:
                params = _params({"w0_min": float(wmin)})
                sc = _scenario("S1", params)
                run = _mk_run("S1", "scripted", label=f"E7_{shape}_V{V:.0e}_w{wmin:.0f}",
                              overrides={"w0_min": float(wmin)})
                specs = _placement_specs(shape, float(V))
                run = replace(run, placements=specs)
                table = EventTable([])
                res = run_model(params, sc, run, events=table, store_fields=False)
                m = res.metrics
                rows.append({
                    "shape": shape, "V": float(V), "w_min": float(wmin),
                    "V_thr": 10.0 * 5000.0 * (20.0 - float(wmin)),
                    "T_safe_cum_w": m["T_safe_cum_w"],
                    "T_safe_cum_b": m["T_safe_cum_b"],
                    "E_w": m["E_w"], "E_b": m["E_b"],
                    "w_end_min": m["w_end_min"],
                    "protected_fraction": m["T_safe_cum_w"] / 15.0,
                })
        print(f"[E7] {shape}: {len(w_mins)} x {len(volumes)} grid done")
    out.mkdir(parents=True, exist_ok=True)
    with (out / "phase.csv").open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)
    _write_summary(out, "E7", rows[:5], {"n_rows": len(rows),
                                         "volumes": list(map(float, volumes)),
                                         "w_mins": list(map(float, w_mins))})
    return {"rows": rows}


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
def main(argv=None) -> int:
    p = argparse.ArgumentParser(description="Run experiments E0-E7")
    p.add_argument("--only", default="L0,E0,E1,E2,E3,E4,E5,E6,E7")
    p.add_argument("--jobs", type=int, default=DEFAULT_JOBS)
    p.add_argument("--n-mc", type=int, default=1000)
    p.add_argument("--force", action="store_true")
    p.add_argument("--sobol", action="store_true")
    args = p.parse_args(argv)
    which = {w.strip().upper() for w in args.only.split(",") if w.strip()}
    t0 = time.time()
    out = {}
    if "L0" in which:
        out["L0"] = exp_L0(args.jobs, max(200, args.n_mc // 3), args.force)
    if "E0" in which:
        out["E0"] = exp_E0(args.jobs, args.n_mc, args.force)
    if "E1" in which:
        out["E1"] = exp_E1(args.jobs, args.force)
    if "E2" in which:
        out["E2"] = exp_E2(args.jobs, args.n_mc, args.force)
    if "E3" in which:
        out["E3"] = exp_E3(args.jobs, args.force)
    if "E4" in which:
        out["E4"] = exp_E4(args.jobs, args.force)
    if "E5" in which:
        out["E5"] = exp_E5(args.jobs, args.force, args.sobol)
    if "E6" in which:
        out["E6"] = exp_E6(args.jobs, args.force)
    if "E7" in which:
        out["E7"] = exp_E7(args.jobs, args.force)
    print(f"[experiments] {sorted(out)} in {time.time() - t0:.1f}s")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
