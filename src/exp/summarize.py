"""Collect scalar diagnostics from completed result directories."""

import argparse
import csv
import json
from pathlib import Path


FIELDS = [
    "run", "scenario", "strategy", "bc", "seed", "t_end", "placed_m3",
    "residual_rel_max", "E_w_myr", "E_b_myr", "T_first_fail_w",
    "T_first_fail_w_censored", "T_first_fail_b", "T_first_fail_b_censored",
    "T_safe_cum_w", "T_safe_cum_b", "w_end_min", "w_end_mean",
    "T_recovery_w", "T_recovery_w_censored", "T_recovery_b",
    "T_recovery_b_censored", "exhausted_frac", "n_events", "cost_used_usd",
    "n_projects",
]


def _value(block, key):
    item = block.get(key, {})
    return item.get("value") if isinstance(item, dict) else item


def summarize(root):
    rows = []
    for path in sorted(Path(root).iterdir()):
        # Keep the deterministic strategy table separate from diagnostics,
        # Monte Carlo runs, OAT sweeps, and paired-retention reruns.
        if (path.name.startswith(("BC_", "MC_", "OAT_", "DIAG_")) or
                path.name.endswith("_paired")):
            continue
        result_path = path / "results.json"
        if not result_path.is_file():
            continue
        data = json.loads(result_path.read_text(encoding="utf-8"))
        meta = data.get("meta", {})
        duration = data.get("duration", {})
        mass = data.get("mass", {})
        state = data.get("state", {})
        cost = data.get("cost", {})
        rows.append({
            "run": path.name,
            "scenario": meta.get("scenario"),
            "strategy": meta.get("strategy"),
            "bc": meta.get("bc"),
            "seed": meta.get("seed"),
            "t_end": data.get("parameters", {}).get("t_end"),
            "placed_m3": mass.get("placed"),
            "residual_rel_max": mass.get("residual_rel_max"),
            "E_w_myr": data.get("exposure", {}).get("E_w"),
            "E_b_myr": data.get("exposure", {}).get("E_b"),
            "T_first_fail_w": _value(duration, "T_first_fail_w"),
            "T_first_fail_w_censored": duration.get("T_first_fail_w", {}).get("censored"),
            "T_first_fail_b": _value(duration, "T_first_fail_b"),
            "T_first_fail_b_censored": duration.get("T_first_fail_b", {}).get("censored"),
            "T_safe_cum_w": duration.get("T_safe_cum_w"),
            "T_safe_cum_b": duration.get("T_safe_cum_b"),
            "T_recovery_w": _value(duration, "T_recovery_w"),
            "T_recovery_w_censored": duration.get("T_recovery_w", {}).get("censored"),
            "T_recovery_b": _value(duration, "T_recovery_b"),
            "T_recovery_b_censored": duration.get("T_recovery_b", {}).get("censored"),
            "w_end_min": state.get("w_end_min"),
            "w_end_mean": state.get("w_end_mean"),
            "exhausted_frac": state.get("exhausted_frac"),
            "n_events": data.get("events", {}).get("n_events_applied"),
            "cost_used_usd": cost.get("cost_used"),
            "n_projects": cost.get("n_projects"),
        })
    return rows


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", default="results")
    parser.add_argument("--out", default="results/summary.csv")
    args = parser.parse_args(argv)
    rows = summarize(args.root)
    with Path(args.out).open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows(rows)
    print(f"wrote {args.out}: {len(rows)} runs")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
