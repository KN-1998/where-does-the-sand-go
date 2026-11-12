# -*- coding: utf-8 -*-
"""Shared helpers for experiment drivers."""
from __future__ import annotations

import json
from dataclasses import replace
from pathlib import Path
from typing import Any, Dict, Optional, Sequence, Tuple

import numpy as np

from sim.io import write_results
from sim.model import SimResult, run_model
from sim.params import Params, RunConfig, Scenario
from sim.storms import EventTable, build_event_table

REPO_ROOT = Path(__file__).resolve().parents[2]
RESULTS = REPO_ROOT / "results"
FIGURES = REPO_ROOT / "figures"


def central_sand(res: SimResult, i: int, H: float = 10.0) -> float:
    """Central 5 km (V + O) increment, m^3, at time index ``i``."""
    g = res.grid
    return float((H * res.y[i, g.central]).sum() * g.dx
                 + res.O[i, g.central].sum() * g.dx)


def index_at(res: SimResult, t: float) -> int:
    return int(np.argmin(np.abs(res.t - t)))


def retention_curve(nour: SimResult, base: SimResult,
                    times: Sequence[float] = (1.0, 5.0, 15.0),
                    H: float = 10.0) -> Dict[str, Any]:
    out: Dict[str, Any] = {}
    rows = nour.ledger.rows
    for t in times:
        i = index_at(nour, t)
        if nour.t[i] > nour.t[-1] + 1e-9 and t > nour.t[-1]:
            continue
        placed = float(rows[i]["placed_cum"])
        dv = central_sand(nour, i, H) - central_sand(base, i, H)
        key = f"R_ret_{int(round(t))}yr" if abs(t - round(t)) < 1e-9 else f"R_ret_{t:g}yr"
        out[key] = (dv / placed) if placed > 1e-9 else None
        out[f"placed_{int(round(t))}yr" if abs(t - round(t)) < 1e-9 else f"placed_{t:g}yr"] = placed
    return out


def run_pair(params: Params, scenario: Scenario, run: RunConfig,
             table: Optional[EventTable] = None,
             retention_times: Sequence[float] = (1.0, 5.0, 15.0)) -> Tuple[SimResult, SimResult, Dict[str, Any]]:
    """Run a nourished realisation and its paired no-nourishment baseline.

    The same event table is replayed in both runs (CODER_SPEC §2.4b / MODEL_SPEC
    §6.2), so the difference is attributable to the intervention.
    """
    if table is None:
        table = build_event_table(scenario, run.seed, run.t_end, run.Lb,
                                  run.phi_shape, run.forced_events)
    H = float(params["H_dep"])
    nour = run_model(params, scenario, run, events=table, store_fields=True)
    base_run = replace(run, strategy="none", placements=None, label=run.label + "_base")
    base = run_model(params, scenario, base_run, events=table, store_fields=False)
    times = [t for t in retention_times if t <= run.t_end + 1e-9]
    ret = retention_curve(nour, base, times, H)
    return nour, base, ret


def save(outdir: Path, res: SimResult, retention=None, runtime_s=None,
         extra_meta=None, write_fields=True) -> Dict[str, Any]:
    return write_results(outdir, res, retention=retention, runtime_s=runtime_s,
                         extra_meta=extra_meta, write_fields=write_fields)


def load_json(path: str | Path) -> Dict[str, Any]:
    with Path(path).open("r", encoding="utf-8") as fh:
        return json.load(fh)


def dump_json(path: str | Path, obj: Any) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as fh:
        json.dump(obj, fh, ensure_ascii=False, indent=2, default=_default)


def _default(o):
    if isinstance(o, (np.floating, np.integer)):
        return o.item()
    if isinstance(o, np.ndarray):
        return o.tolist()
    return str(o)
