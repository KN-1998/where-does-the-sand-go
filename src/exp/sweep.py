"""One-at-a-time parameter sensitivity runner for scalar shoreline outputs."""
import argparse
import csv
import copy
from pathlib import Path
import numpy as np

from src.sim.io import load_config, write_json, tree_sha256, object_sha256
from src.sim.model import ShorelineModel
from src.sim.strategies import strategy_schedule


PARAMS = {
    "D_diff": ("transport", "D_diff"),
    "H_dep": ("geometry", "H_dep"),
    "rho_e": ("transport", "rho_e"),
    "u_drift": ("transport", "u_drift"),
    "k_rec": ("storm", "k_rec"),
    "lam_off": ("storm", "lam_off"),
    "w_sat": ("storm", "w_sat"),
    "rho_e_hotspot_amp": ("transport", "rho_e_hotspot_amp"),
    "sigma_h": ("transport", "sigma_h"),
    "w0_far": ("beach_state", "w0_far"),
    "w_mgmt": ("beach_state", "w_mgmt"),
    "V15_total": ("management", "V15_total"),
    "V_event_max": ("management", "V_event_max"),
    "S_borrow_total": ("management", "S_borrow_total"),
    "c1": ("management", "c1"),
    "lambda_s": ("storm", "lambda_s"),
    "dy_ref": ("storm", "dy_ref"),
}


def value_entry(data):
    return data["value"] if isinstance(data, dict) else data


def set_value(data, val):
    if isinstance(data, dict) and "value" in data:
        data["value"] = float(val)
    else:
        raise ValueError("OAT parameter must be a scalar parameter with a value field")


def run_sweep(config_path, scenario="S2", strategy="once", n=200, seed=42,
              out="results/sweep", boundary=None, y_boundary=None):
    base = load_config(config_path)
    out = Path(out)
    out.mkdir(parents=True, exist_ok=True)
    boundary = boundary or base.get("bc", "zeroflux")
    rows = []
    for param, (section, key) in PARAMS.items():
        original = value_entry(base[section][key])
        if param == "D_diff":
            values = [1e5, 3e5, 8e5]
        elif param == "H_dep":
            values = [8., 10., 12.]
        elif param == "rho_e":
            values = [1.0, 1.7, 3.5, 4.6]
        elif param == "u_drift":
            values = [0., 50., 150.]
        elif param in {"k_rec", "lam_off"}:
            values = sorted(set([max(.001, original*.5), original, original*1.5]))
        elif param == "rho_e_hotspot_amp":
            values = [0.5, original, 2.0]
        elif param == "sigma_h":
            values = [500.0, original, 1000.0]
        elif param == "w0_far":
            values = [20.0, original, 30.0]
        elif param == "w_mgmt":
            values = [12.0, original, 32.0]
        elif param == "V15_total":
            values = [3.5e6, original, 6.8e6]
        elif param == "V_event_max":
            values = [1.5e6, original, 3.5e6]
        elif param == "S_borrow_total":
            values = [1.5e6, original, 3.2e6]
        elif param == "lambda_s":
            values = [.2, .4, .8]
        elif param == "dy_ref":
            values = [4., 8., 12.]
        elif param == "c1":
            values = [20.0, original, 35.0]
        else:
            values = [10., 20., 40.]
        for val in values:
            config = copy.deepcopy(base)
            set_value(config[section][key], val)
            if param in {'lambda_s', 'dy_ref'}:
                scenario_key = {'S1':'S1_calm','S2':'S2_storm_soon','S3':'S3_repeat'}[scenario]
                old = config['scenarios'][scenario_key][param]
                config['scenarios'][scenario_key][param] = (
                    [val, val * old[1]/old[0]] if isinstance(old, list) else val)
            for index in range(n):
                run_seed = (seed * 1000003 + index) % 2**32
                placements = strategy_schedule(strategy, config,
                    float(config.get("t_end", 15.0)), float(config["domain"]["x_h"]["value"]))
                result = ShorelineModel(config, scenario=scenario, strategy=strategy,
                    seed=run_seed, t_end=float(config.get("t_end", 15.0)),
                    dt=float(config.get("dt", .02)), dx=float(config.get("dx", 25.)),
                    boundary=boundary, y_boundary=y_boundary,
                    placements=placements).run().results
                rows.append({"parameter": param, "value": val, "index": index,
                    "seed": run_seed, "E_b": result["exposure"]["E_b"],
                    "E_w": result["exposure"]["E_w"],
                    "T_safe_cum_b": result["duration"]["T_safe_cum_b"],
                    "T_first_fail_b": result["duration"]["T_first_fail_b"]["value"],
                    "T_first_fail_b_censored": result["duration"]["T_first_fail_b"]["censored"],
                    "placed_m3": result["mass"]["placed"],
                    "cost_used": result["cost"]["cost_used"],
                    "residual_rel_max": result["mass"]["residual_rel_max"]})
    with (out / "oat.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]) if rows else [])
        writer.writeheader()
        writer.writerows(rows)
    write_json(out / 'design.json', {'n_values':len(rows)//n, 'seeds_per_value':n,
        'base_seed':seed, 'scenario':scenario, 'strategy':strategy, 'bc':boundary,
        'code_sha256':tree_sha256(Path(__file__).resolve().parents[2]/'src'),
        'resolved_config_sha256':object_sha256(base), 'resolved_config':base,
        'interpretation':'OAT matched seeds; scenario total erosion held fixed in storm-rate/strength scans; fixed forced S2 event excluded from strength scaling'})
    return rows


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", required=True)
    parser.add_argument("--scenario", default="S2")
    parser.add_argument("--strategy", default="once")
    parser.add_argument("--n", type=int, default=200)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--out", default="results/sweep")
    parser.add_argument("--bc", choices=["zeroflux", "open", "dirichlet"], default=None)
    parser.add_argument("--y-boundary", nargs=2, type=float, default=None)
    args = parser.parse_args(argv)
    if args.n <= 0:
        parser.error("--n must be positive")
    rows = run_sweep(args.config, args.scenario, args.strategy, args.n, args.seed, args.out,
                     boundary=args.bc, y_boundary=args.y_boundary)
    print(f"wrote {args.out}: {len(rows)} runs")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
