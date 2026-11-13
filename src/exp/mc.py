"""Deterministic Monte Carlo runner and censor-aware Kaplan-Meier summaries."""
import argparse
import csv
from pathlib import Path
import numpy as np

from src.sim.io import load_config, write_json, tree_sha256, object_sha256
from src.sim.metrics import km_quantile, recovery_statistics
from src.sim.model import ShorelineModel
from src.sim.strategies import strategy_schedule


def _seed(base, index):
    return (int(base) * 1000003 + int(index)) % 2**32


def run_mc(config_path, scenario, strategy, n, base_seed, out,
           boundary=None, y_boundary=None):
    config_path = Path(config_path).resolve()
    config = load_config(config_path)
    scenario = scenario or config.get("scenario", "S1")
    strategy = strategy or config.get("strategy", "none")
    t_end = float(config.get("t_end", 15.0))
    boundary = boundary or config.get("bc", "zeroflux")
    y_boundary = y_boundary if y_boundary is not None else config.get("y_boundary")
    config.update(scenario=scenario, strategy=strategy, bc=boundary, t_end=t_end,
                  base_seed=int(base_seed), seed_rule="(base_seed*1000003+i) mod 2**32")
    config.pop('seed', None)
    if y_boundary is not None:
        config['y_boundary'] = y_boundary
    x_hotspot = float(config["domain"]["x_h"]["value"])
    base_placements = strategy_schedule(strategy, config, t_end, x_hotspot)
    out = Path(out)
    out.mkdir(parents=True, exist_ok=True)
    rows = []
    event_tables = []
    pooled_recovery = {"w": [], "b": []}
    width_end = []
    width_history = []
    report_times = np.arange(0.,t_end+1e-9,.5)
    fates = []
    for index in range(n):
        seed = _seed(base_seed, index)
        model = ShorelineModel(config, scenario=scenario, strategy=strategy,
                               boundary=boundary, y_boundary=y_boundary, seed=seed,
                               t_end=t_end, dt=float(config.get("dt", 0.02)),
                               dx=float(config.get("dx", 25.0)),
                               placements=base_placements,
                               storm_enabled=bool(config.get("storm_enabled", True)))
        simulation = model.run()
        result = simulation.results
        # Copy the row: a NumPy view would retain every run's full time history
        # and multiply ensemble memory by hundreds of output timesteps.
        width_end.append(simulation.fields["w"][-1].copy())
        width_history.append(np.stack([np.interp(report_times,simulation.fields['t'],
            simulation.fields['w'][:,j]) for j in range(len(model.grid.x))],axis=1).astype('float32'))
        retention={}
        if result['mass']['placed']>0:
            from src.exp.pairing import at_times, fate_effects
            baseline_model=ShorelineModel(config,scenario=scenario,strategy='none',
                boundary=boundary,y_boundary=y_boundary,seed=seed,t_end=t_end,
                dt=model.dt,dx=model.grid.dx,placements=[],events=model.events)
            baseline=baseline_model.run()
            years=[v for v in (1.,5.,15.) if v<=t_end]
            changes=(at_times(simulation,model,years)-at_times(baseline,model,years))/result['mass']['placed']
            retention={f'R_ret_{int(year)}yr':float(v) for year,v in zip(years,changes)}
            fate=fate_effects(simulation,baseline,model)
            if abs(sum(fate.values())-result['mass']['placed'])>1e-6*result['mass']['placed']:
                raise ArithmeticError('paired sand-attribution closure failed')
            fates.append(fate)
        for record in simulation.recovery_records:
            pooled_recovery[record["metric"]].append(record)
        event_tables.append([(event.time, event.potential_retreat,
                              event.forced_actual_retreat, event.center)
                             for event in model.events])
        rows.append({"index": index, "seed": seed,
                     "residual_rel_max": result["mass"]["residual_rel_max"],
                     "residual_central_rel_max": result["mass"]["residual_central_rel_max"],
                     "E_w": result["exposure"]["E_w"],
                     "E_b": result["exposure"]["E_b"],
                     "T_first_fail_w": result["duration"]["T_first_fail_w"]["value"],
                     "T_first_fail_w_censored": result["duration"]["T_first_fail_w"]["censored"],
                     "T_first_fail_b": result["duration"]["T_first_fail_b"]["value"],
                     "T_first_fail_b_censored": result["duration"]["T_first_fail_b"]["censored"],
                     "T_safe_cum_w": result["duration"]["T_safe_cum_w"],
                     "T_safe_cum_b": result["duration"]["T_safe_cum_b"],
                     "T_recovery_w": result["duration"]["T_recovery_w"]["value"],
                     "T_recovery_w_censored": result["duration"]["T_recovery_w"]["censored"],
                     "T_recovery_b": result["duration"]["T_recovery_b"]["value"],
                     "T_recovery_b_censored": result["duration"]["T_recovery_b"]["censored"],
                     "w_end_min": result["state"]["w_end_min"],
                     "w_end_mean": result["state"]["w_end_mean"],
                     "exhausted_frac": result["state"]["exhausted_frac"],
                     "events": result["events"]["n_events_applied"],
                     "cost_used": result['cost']['cost_used'],
                     'construction_cost':result['cost']['construction_cost'],
                     'monitoring_cost':result['cost']['monitoring_cost'],
                     'n_projects':result['cost']['n_projects'],
                     **{key:retention.get(key) for key in ('R_ret_1yr','R_ret_5yr','R_ret_15yr')},
                     "placed_m3": result["mass"]["placed"]})
    with (out / "runs.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]) if rows else ["index", "seed"])
        writer.writeheader()
        writer.writerows(rows)
    from hashlib import sha256
    import json
    table_hashes = [sha256(json.dumps(table, separators=(",", ":")).encode()).hexdigest()
                    for table in event_tables]
    summary = {"scenario": scenario, "strategy": strategy, "n": n,
               "base_seed": base_seed, "seed_rule": "(base_seed*1000003+i) mod 2**32",
               "event_table_hashes": table_hashes,
               "runs": rows, "bc": boundary,
               "code_sha256": tree_sha256(Path(__file__).resolve().parents[2] / "src"),
               "resolved_config": config,
               "resolved_config_sha256": object_sha256(config),
               "uncertainty_scope": "storm realizations only; parameters held fixed",
               "width_end": {"x": model.grid.x.tolist(),
                             "p10": np.quantile(width_end, .1, axis=0).tolist(),
                             "p50": np.quantile(width_end, .5, axis=0).tolist(),
                             "p90": np.quantile(width_end, .9, axis=0).tolist()}}
    for metric in ("E_w", "E_b", "T_safe_cum_w", "T_safe_cum_b", "w_end_min", "w_end_mean"):
        values = np.array([row[metric] for row in rows], dtype=float)
        summary.setdefault("quantiles", {})[metric] = {
            "p10": float(np.quantile(values, .1)), "p50": float(np.quantile(values, .5)),
            "p90": float(np.quantile(values, .9))}
    for suffix in ("w", "b"):
        observations = [(row[f"T_first_fail_{suffix}"], row[f"T_first_fail_{suffix}_censored"])
                        for row in rows]
        summary.setdefault("kaplan_meier", {})[suffix] = {
            f"p{int(q*100)}": km_quantile([item[0] if item[0] is not None else t_end for item in observations],
                                                   [item[1] for item in observations], q)
            for q in (.1, .5, .9)}
        summary["kaplan_meier"][suffix]["censored_count"] = sum(bool(item[1]) for item in observations)
    summary["kaplan_meier_recovery"] = {
        suffix: recovery_statistics(pooled_recovery[suffix]) for suffix in ("w", "b")}
    summary["recovery_sampling_unit"] = "pooled event-cell pairs; dependent within runs"
    summary['width_trajectory']={'t':report_times.tolist(),'x':model.grid.x.tolist(),
        **{f'p{int(q*100)}':np.quantile(width_history,q,axis=0).tolist() for q in (.1,.5,.9)},
        'scope':'pointwise storm-only quantiles, half-yearly; no simultaneous-coverage claim'}
    summary['retention_quantiles']={key:{f'p{int(q*100)}':float(np.quantile(
        [r[key] for r in rows if r[key] is not None],q)) for q in (.1,.5,.9)}
        for key in ('R_ret_1yr','R_ret_5yr','R_ret_15yr') if any(r[key] is not None for r in rows)}
    summary['sand_attribution_quantiles']={key:{f'p{int(q*100)}':float(np.quantile(
        [r[key] for r in fates],q)) for q in (.1,.5,.9)} for key in (fates[0] if fates else [])}
    summary['sand_attribution_scope']='paired signed volume effects; conditional on placement; not tagged grains; quantiles do not sum'
    write_json(out / "summary.json", summary)
    return summary


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", required=True)
    parser.add_argument("--scenario", default=None)
    parser.add_argument("--strategy", default=None)
    parser.add_argument("--n", type=int, default=1000)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--out", required=True)
    parser.add_argument("--bc", choices=["zeroflux", "open", "dirichlet"], default=None)
    parser.add_argument("--y-boundary", nargs=2, type=float, default=None)
    args = parser.parse_args(argv)
    if args.n <= 0:
        parser.error("--n must be positive")
    result = run_mc(args.config, args.scenario, args.strategy, args.n, args.seed, args.out,
                    boundary=args.bc, y_boundary=args.y_boundary)
    print(f"wrote {args.out}: n={result['n']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
