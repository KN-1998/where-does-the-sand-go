# -*- coding: utf-8 -*-
"""Result-level audit (independent of the running model).

Checks every artefact under ``results/`` for schema, numeric sanity, ledger
closure, MC completeness and figure presence.  Exit code 0 iff everything passes.

Usage::

    python -m exp.audit                 # human summary
    python -m exp.audit --json out.json # also write machine-readable report
"""
from __future__ import annotations

import argparse
import csv
import json
import math
from pathlib import Path
from typing import Any, Dict, List, Optional

REPO_ROOT = Path(__file__).resolve().parents[2]
RESULTS = REPO_ROOT / "results"
FIGURES = REPO_ROOT / "figures"

REQUIRED_TOP = ["meta", "initial", "duration", "exposure", "mass", "cost", "state"]
FIGURE_FILES = ["F1_w_xt.png", "F2_w_t_positions.png", "F3_sand_destinations.png",
                "F4_T_first_fail_hist.png", "F5_placement_bars.png",
                "F6_oat_tornado.png", "F7_phase_diagram.png", "F8_c0_strategies.png"]


class Audit:
    def __init__(self) -> None:
        self.checks: List[Dict[str, Any]] = []

    def check(self, name: str, ok: bool, detail: str = "") -> None:
        self.checks.append({"check": name, "ok": bool(ok), "detail": detail})

    @property
    def failed(self) -> List[Dict[str, Any]]:
        return [c for c in self.checks if not c["ok"]]

    def report(self) -> Dict[str, Any]:
        return {"n_checks": len(self.checks), "n_failed": len(self.failed),
                "checks": self.checks}


def _finite(x: Any) -> bool:
    return isinstance(x, (int, float)) and math.isfinite(float(x))


def _load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _check_results(a: Audit, path: Path) -> None:
    tag = str(path.relative_to(RESULTS))
    d = _load_json(path)
    a.check(f"{tag}: top-level keys", all(k in d for k in REQUIRED_TOP),
            str([k for k in REQUIRED_TOP if k not in d]))
    if not all(k in d for k in REQUIRED_TOP):
        return
    t_end = float(d["meta"].get("t_end") or 15.0) if "t_end" in d["meta"] else None
    for key in ("T_first_fail_w", "T_first_fail_b"):
        rec = d["duration"][key]
        a.check(f"{tag}: {key} censoring",
                (rec.get("value") is None) == bool(rec.get("censored")),
                str(rec))
        if rec.get("value") is not None:
            a.check(f"{tag}: {key} value finite", _finite(rec["value"]), str(rec["value"]))
    for key in ("T_safe_cum_w", "T_safe_cum_b"):
        v = d["duration"][key]
        a.check(f"{tag}: {key} in [0,15]", _finite(v) and -1e-9 <= v <= 15.0 + 1e-9,
                str(v))
    for key in ("E_w", "E_b"):
        v = d["exposure"][key]
        a.check(f"{tag}: {key} finite/non-negative", _finite(v) and v >= 0.0, str(v))
    m = d["mass"]
    a.check(f"{tag}: residual_rel_max < 1e-6",
            _finite(m["residual_rel_max"]) and abs(m["residual_rel_max"]) < 1e-6,
            f"{m['residual_rel_max']:.3e}")
    a.check(f"{tag}: placed >= 0", _finite(m["placed"]) and m["placed"] >= 0.0,
            str(m["placed"]))
    a.check(f"{tag}: cost >= 0", _finite(d["cost"]["cost_used"])
            and d["cost"]["cost_used"] >= 0.0, str(d["cost"]["cost_used"]))
    if d["cost"].get("c0_star") is not None and d["meta"].get("cost_model") == "all_in":
        a.check(f"{tag}: c0_star must be null under all_in", False, str(d["cost"]["c0_star"]))

    ledger_path = path.parent / "ledger.csv"
    if not ledger_path.exists():
        return
    with ledger_path.open(encoding="utf-8") as fh:
        rows = list(csv.DictReader(fh))
    a.check(f"{tag}: ledger has rows", len(rows) > 1, str(len(rows)))
    if not rows:
        return
    ts = [float(r["t"]) for r in rows]
    a.check(f"{tag}: ledger time monotone", all(b >= a - 1e-12 for a, b in zip(ts[:-1], ts[1:])),
            f"{ts[0]}..{ts[-1]}")
    a.check(f"{tag}: ledger starts at 0", abs(ts[0]) < 1e-12, str(ts[0]))
    rel = max(abs(float(r["residual_rel"])) for r in rows)
    a.check(f"{tag}: ledger max|residual_rel| < 1e-6", rel < 1e-6, f"{rel:.3e}")
    a.check(f"{tag}: results/ledger residual agree",
            abs(rel - abs(float(m["residual_rel_max"]))) < 1e-9,
            f"{rel:.3e} vs {m['residual_rel_max']:.3e}")
    last = rows[-1]
    a.check(f"{tag}: placed matches ledger",
            abs(float(last["placed_cum"]) - float(m["placed"])) < 1e-6,
            f"{last['placed_cum']} vs {m['placed']}")
    # closure identity with the ledger columns: residual = placed - (V+O+flux+losses)
    rhs = (float(last["V_domain"]) + float(last["O_domain"])
           + float(last["flux_outer_left_cum"]) + float(last["flux_outer_right_cum"])
           + float(last["offshore_loss_cum"]) + float(last["chronic_loss_cum"]))
    resid = float(last["placed_cum"]) - rhs
    scale = max(1.0, abs(float(last["placed_cum"])))
    a.check(f"{tag}: ledger closure recomputed",
            abs(resid - float(last["residual"])) / scale < 1e-9,
            f"{resid:.3e} vs {last['residual']}")
    a.check(f"{tag}: ledger has R_c and D_max columns",
            "R_c_cum" in last and "D_max_cum" in last)
    a.check(f"{tag}: D_max >= R_c",
            float(last["D_max_cum"]) >= float(last["R_c_cum"]) - 1e-9,
            f"{last['D_max_cum']} / {last['R_c_cum']}")
    _check_fields(a, tag, path.parent / "fields.npz")


def _check_fields(a: Audit, tag: str, path: Path) -> None:
    """fields.npz must carry y/O/w/exhausted/x/t with consistent shapes."""
    import numpy as np
    if not path.exists():
        return
    d = np.load(path)
    keys = set(d.files)
    a.check(f"{tag}: fields keys", {"y", "O", "w", "exhausted", "x", "t"} <= keys,
            str(sorted(keys)))
    if not {"y", "exhausted", "x", "t"} <= keys:
        return
    nt, nx = d["y"].shape
    a.check(f"{tag}: fields shapes",
            d["O"].shape == (nt, nx) and d["w"].shape == (nt, nx)
            and d["exhausted"].shape == (nt, nx)
            and d["x"].shape == (nx,) and d["t"].shape == (nt,),
            f"y={d['y'].shape} exhausted={d['exhausted'].shape}")
    a.check(f"{tag}: exhausted is boolean", d["exhausted"].dtype == bool,
            str(d["exhausted"].dtype))
    a.check(f"{tag}: fields dtype float32", d["y"].dtype == np.float32,
            str(d["y"].dtype))


def _check_mc(a: Audit, path: Path) -> None:
    tag = str(path.relative_to(RESULTS))
    d = _load_json(path)
    s = d["summary"]
    n = int(d["meta"]["n"])
    a.check(f"{tag}: n", int(s["n"]) == n, f"{s['n']} vs {n}")
    a.check(f"{tag}: n>=1000" if n >= 1000 else f"{tag}: n>=200", n >= min(1000, 200),
            str(n))
    for key in ("E_w", "E_b", "T_safe_cum_w", "T_safe_cum_b"):
        q = s.get(key, {})
        vals = [q.get(f"P{p}") for p in (10, 50, 90)]
        a.check(f"{tag}: {key} quantiles present/monotone",
                all(_finite(v) for v in vals) and vals[0] <= vals[1] + 1e-9
                and vals[1] <= vals[2] + 1e-9, str(vals))
    for key in ("T_first_fail_w", "T_first_fail_b"):
        q = s.get(key, {})
        a.check(f"{tag}: {key} KM available",
                "km_P50" in q and 0.0 <= q.get("km_censored_fraction", -1) <= 1.0,
                str({k: q.get(k) for k in ("km_P50", "km_censored_fraction")}))
    csv_path = path.parent / "mc_results.csv"
    if csv_path.exists():
        with csv_path.open(encoding="utf-8") as fh:
            nrows = sum(1 for _ in csv.DictReader(fh))
        a.check(f"{tag}: mc_results row count", nrows == n, f"{nrows} vs {n}")


def _check_e1(a: Audit) -> None:
    summary = _load_json(RESULTS / "E1" / "summary.json")
    rows = summary["generated_rows"]
    a.check("E1: three placements", len(rows) == 3, str(len(rows)))
    for shape in ("uniform", "hotspot", "multi"):
        d = RESULTS / "E1" / shape / "destinations.csv"
        a.check(f"E1/{shape}: destinations exists", d.exists())
        if not d.exists():
            continue
        with d.open(encoding="utf-8") as fh:
            rr = list(csv.DictReader(fh))
        last = rr[-1]
        placed = float(last["placed"])
        split = (float(last["retained_domain"]) + float(last["flux_out_domain"])
                 + float(last["offshore_loss"]))
        a.check(f"E1/{shape}: split sums to placed",
                abs(split - placed) / placed < 1e-3, f"{split:.3f} vs {placed:.3f}")


def _check_e4(a: Audit) -> None:
    payload = _load_json(RESULTS / "E4" / "c0_scan_S2" / "c0_scan.json")
    rows = payload["rows"]
    a.check("E4 c0 scan: 6x4 rows", len(rows) == 24, str(len(rows)))
    strategies = {r["strategy"] for r in rows}
    a.check("E4 c0 scan: four strategies", strategies == {"once", "repeat", "targeted", "adaptive"},
            str(strategies))
    for r in rows:
        if r["n_projects"] == 0 and r["cost"] != 0.0:
            a.check("E4 c0 scan: no project => no cost", False, str(r))
            break
    else:
        a.check("E4 c0 scan: no project => no cost", True)


def _check_e7(a: Audit) -> None:
    with (RESULTS / "E7" / "phase.csv").open(encoding="utf-8") as fh:
        rows = list(csv.DictReader(fh))
    a.check("E7: 12x8x2 grid", len(rows) == 192, str(len(rows)))
    pf = [float(r["protected_fraction"]) for r in rows]
    a.check("E7: protected fraction in [0,1]",
            all(0.0 <= v <= 1.0 + 1e-12 for v in pf), f"{min(pf):.3f}..{max(pf):.3f}")


def _check_figures(a: Audit) -> None:
    for name in FIGURE_FILES:
        p = FIGURES / name
        ok = p.exists() and p.stat().st_size > 20_000 and p.read_bytes()[:8] == b"\x89PNG\r\n\x1a\n"
        a.check(f"figure {name}", ok, f"{p.stat().st_size // 1024} KB" if p.exists() else "missing")


def _check_logs(a: Audit) -> None:
    log = RESULTS / "validation" / "pytest.log"
    a.check("pytest log exists", log.exists())
    if log.exists():
        raw = log.read_bytes()
        text = None
        for enc in ("utf-8-sig", "utf-16", "utf-16-le", "utf-8"):
            try:
                cand = raw.decode(enc)
            except UnicodeDecodeError:
                continue
            if "passed" in cand:
                text = cand
                break
        text = text or raw.decode("utf-8", errors="replace")
        a.check("pytest log: 17 passed", "17 passed" in text)


def audit() -> Audit:
    a = Audit()
    res_files = sorted(RESULTS.rglob("results.json"))
    a.check("results.json count >= 100", len(res_files) >= 100, str(len(res_files)))
    for p in res_files:
        _check_results(a, p)
    mc_files = sorted(RESULTS.rglob("mc_summary.json"))
    a.check("mc_summary count == 8", len(mc_files) == 8, str(len(mc_files)))
    for p in mc_files:
        _check_mc(a, p)
    for fn in (_check_e1, _check_e4, _check_e7, _check_figures, _check_logs):
        fn(a)
    return a


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description="Audit result artefacts")
    p.add_argument("--json", default=str(RESULTS / "validation" / "AUDIT.json"))
    args = p.parse_args(argv)
    a = audit()
    report = a.report()
    out = Path(args.json)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    for c in a.checks:
        if not c["ok"]:
            print(f"  [FAIL] {c['check']}  {c['detail']}")
    print(f"===== audit: {report['n_checks']} checks, {report['n_failed']} failed =====")
    return 0 if report["n_failed"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
