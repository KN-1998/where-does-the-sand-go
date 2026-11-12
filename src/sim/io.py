# -*- coding: utf-8 -*-
"""Result serialisation: ``results.json``, ``fields.npz``, ``ledger.csv``,
``events.csv``, ``meta.json`` (CODER_SPEC §4.2).

``fields.npz`` carries ``y/O/w/exhausted/x/t``; ``exhausted`` is the boolean
diagnostic mask required by CODER_SPEC §2.4c (``V <= V_min``).  All arrays except
the mask are float32 for display only -- never recompute the ledger from them.

Determinism
-----------
``results.json`` and ``fields.npz`` must be byte-identical for the same seed
(T8).  ``np.savez`` stamps the current time into the zip members, so the npz is
written here with a fixed timestamp instead.
"""
from __future__ import annotations

import csv
import hashlib
import io
import json
import platform
import subprocess
import time
import zipfile
from pathlib import Path
from typing import Any, Dict, Iterable, Optional

import numpy as np

from .model import SimResult

REPO_ROOT = Path(__file__).resolve().parents[2]


def code_md5() -> str:
    h = hashlib.md5()
    for path in sorted((REPO_ROOT / "src").rglob("*.py")):
        h.update(str(path.relative_to(REPO_ROOT)).replace("\\", "/").encode())
        h.update(path.read_bytes())
    return h.hexdigest()


def git_commit() -> str:
    try:
        out = subprocess.run(["git", "rev-parse", "HEAD"], cwd=REPO_ROOT,
                             capture_output=True, text=True, timeout=10)
        return out.stdout.strip() if out.returncode == 0 else "unknown"
    except Exception:  # pragma: no cover - git absent
        return "unknown"


def save_npz(path: str | Path, **arrays: np.ndarray) -> None:
    """Deterministic ``.npz`` writer (fixed zip timestamps)."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for key, value in arrays.items():
            buf = io.BytesIO()
            np.lib.format.write_array(buf, np.asanyarray(value), allow_pickle=False)
            info = zipfile.ZipInfo(f"{key}.npy", date_time=(1980, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            zf.writestr(info, buf.getvalue())


def _jsonify(obj: Any) -> Any:
    if isinstance(obj, dict):
        return {str(k): _jsonify(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_jsonify(v) for v in obj]
    if isinstance(obj, (np.floating, np.integer, np.bool_)):
        return obj.item()
    if isinstance(obj, np.ndarray):
        return obj.tolist()
    if isinstance(obj, float) and (obj != obj):  # NaN
        return None
    return obj


def build_results(res: SimResult, retention: Optional[Dict[str, Any]] = None,
                  extra: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Assemble the fixed schema of CODER_SPEC §4.2b."""
    m = res.metrics
    cfg = res.config
    out: Dict[str, Any] = {
        "meta": {
            "scenario": cfg.get("scenario"),
            "strategy": cfg.get("strategy"),
            "bc": cfg.get("bc"),
            "cost_model": cfg.get("cost_model"),
            "supply": cfg.get("supply"),
            "seed": cfg.get("seed"),
            "commit": git_commit(),
            "params_md5": res.params_md5,
            "n_events_applied": res.n_events_applied,
            "phi_shape": cfg.get("phi_shape"),
            "label": cfg.get("label"),
            "scenario_law": res.scenario,
        },
        "initial": {
            "f_w0": m["f_w0"],
            "f_b0": m["f_b0"],
            "w_min": m["w0_min"],
            "w_mean": m["w0_mean"],
        },
        "duration": {
            "T_first_fail_w": m["T_first_fail_w"],
            "T_first_fail_b": m["T_first_fail_b"],
            "T_safe_cum_w": m["T_safe_cum_w"],
            "T_safe_cum_b": m["T_safe_cum_b"],
            "T_recovery": m["T_recovery"],
        },
        "exposure": {"E_w": m["E_w"], "E_b": m["E_b"]},
        "mass": {
            "placed": _last(res.ledger, "placed_cum", 0.0),
            "flux_out": (_last(res.ledger, "flux_outer_left_cum", 0.0)
                         + _last(res.ledger, "flux_outer_right_cum", 0.0)),
            "offshore": _last(res.ledger, "offshore_loss_cum", 0.0),
            "chronic": _last(res.ledger, "chronic_loss_cum", 0.0),
            "R_c": _last(res.ledger, "R_c_cum", 0.0),
            "R_c_max": _last(res.ledger, "D_max_cum", 0.0),
            "Q_limited": _last(res.ledger, "Q_limited_cum", 0.0),
            "storm_injected": _last(res.ledger, "storm_injected_cum", 0.0),
            "recovery": _last(res.ledger, "recovery_cum", 0.0),
            "residual_rel_max": res.ledger.max_abs_rel,
        },
        "cost": {
            "cost_used": res.budget["cost_used"],
            "n_projects": res.budget["n_projects"],
            "c0_star": None,
            "c1_eff": res.budget["c1_eff"],
            "V_used": res.budget["V_used"],
            "S_used": res.budget["S_used"],
        },
        "state": {
            "w_end_min": m["w_end_min"],
            "w_end_mean": m["w_end_mean"],
            "w_min_ever": m["w_min_ever"],
            "exhausted_frac": m["exhausted_frac"],
        },
        "diagnostics": {
            "T_first_any_w": m["T_first_any_w"],
            "T_first_any_b": m["T_first_any_b"],
        },
        "placements": res.placements_applied,
        "strategy_log": res.strategy_log,
    }
    if retention is not None:
        out["retention"] = retention
    if extra:
        out.update(extra)
    return _jsonify(out)


def _last(ledger, key: str, default: float) -> float:
    if not ledger.rows:
        return default
    return float(ledger.rows[-1][key])


def write_results(outdir: str | Path, res: SimResult,
                  retention: Optional[Dict[str, Any]] = None,
                  runtime_s: Optional[float] = None,
                  extra_meta: Optional[Dict[str, Any]] = None,
                  extra: Optional[Dict[str, Any]] = None,
                  write_fields: bool = True) -> Dict[str, Any]:
    outdir = Path(outdir)
    outdir.mkdir(parents=True, exist_ok=True)
    results = build_results(res, retention=retention, extra=extra)
    with (outdir / "results.json").open("w", encoding="utf-8") as fh:
        json.dump(results, fh, ensure_ascii=False, indent=2)
    if write_fields:
        w = res.w0[None, :] + res.y
        save_npz(outdir / "fields.npz", y=res.y, O=res.O, w=w,
                 exhausted=res.exhausted, x=res.grid.x, t=res.t)
    res.ledger.write(outdir / "ledger.csv")
    _write_events(outdir / "events.csv", res.events)
    meta = {
        "code_md5": code_md5(),
        "params_md5": res.params_md5,
        "git_commit": git_commit(),
        "seed": res.config.get("seed"),
        "runtime_s": runtime_s,
        "config": res.config,
        "scenario": res.scenario,
        "grid": res.grid.summary(),
        "python": platform.python_version(),
        "numpy": np.__version__,
        "created_unix": time.time(),
        "n_events_applied": res.n_events_applied,
        "solver": {"scheme": "conservative FV + backward Euler",
                   "limiter": True, "bc": res.config.get("bc")},
    }
    if extra_meta:
        meta.update(extra_meta)
    with (outdir / "meta.json").open("w", encoding="utf-8") as fh:
        json.dump(_jsonify(meta), fh, ensure_ascii=False, indent=2)
    return results


EVENT_COLUMNS = ["t", "dy_pot", "dy_forced_actual", "xk", "sigma_e", "tag",
                 "dy_peak", "injected_central", "injected_domain", "n_exhausted"]


def _write_events(path: Path, rows: Iterable[Dict[str, Any]]) -> None:
    with path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=EVENT_COLUMNS)
        writer.writeheader()
        for row in rows:
            writer.writerow({k: ("" if row.get(k) is None else row.get(k))
                             for k in EVENT_COLUMNS})
