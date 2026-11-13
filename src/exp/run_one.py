"""Run one deterministic or paired-event simulation and write its artifacts."""

import argparse
import sys
import time
from pathlib import Path

import numpy as np

from src.sim.io import (file_md5, git_sha, load_config, object_sha256, tree_sha256,
                        write_events, write_fields, write_json, write_ledger, write_recovery)
from src.sim.model import ShorelineModel
from src.sim.strategies import Placement, constrain_placements, strategy_schedule


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", required=True)
    parser.add_argument("--strategy", default=None)
    parser.add_argument("--scenario", default=None)
    parser.add_argument("--seed", type=int, default=None)
    parser.add_argument("--bc", choices=["zeroflux", "open", "dirichlet"], default=None)
    parser.add_argument("--y-boundary", nargs=2, type=float, metavar=("LEFT", "RIGHT"))
    parser.add_argument("--t-end", type=float, default=None)
    parser.add_argument("--paired-retention", action="store_true")
    parser.add_argument("--out", required=True)
    args = parser.parse_args(argv)
    config_path = Path(args.config).resolve()
    root = Path(__file__).resolve().parents[2]
    config = load_config(config_path)
    scenario = args.scenario or config.get("scenario", "S1")
    strategy = args.strategy or config.get("strategy", "none")
    seed = int(args.seed if args.seed is not None else config.get("seed", 42))
    boundary = args.bc or config.get("bc", "zeroflux")
    y_boundary = args.y_boundary or config.get("y_boundary")
    t_end = float(args.t_end if args.t_end is not None else config.get("t_end", 15.0))
    # Keep the persisted resolved snapshot consistent with CLI overrides.
    config.update({"scenario": scenario, "strategy": strategy, "seed": seed,
                   "bc": boundary, "t_end": t_end})
    if y_boundary is not None:
        config["y_boundary"] = y_boundary
    placements = []
    for item in config.get("placement", []) or []:
        dt = float(config.get("dt", 0.02))
        planned = float(item["t"])
        actual = np.ceil(planned / dt - 1e-12) * dt
        if actual <= t_end + 1e-10:
            placements.append(Placement(float(actual), float(item["volume"]),
                                        float(item["xc"]), float(item["len"]), "config"))
    skipped_placements = []
    if "placement" not in config:
        placements = strategy_schedule(strategy, config, t_end,
                                        float(config.get("domain", {}).get("x_h", {}).get("value", 0.0)))
    else:
        placements, skipped_placements = constrain_placements(config, placements)
    model = ShorelineModel(config, scenario=scenario, strategy=strategy,
                           boundary=boundary,
                           seed=seed,
                           t_end=t_end,
                           dx=float(config.get("dx", 25.0)),
                           dt=float(config.get("dt", 0.02)),
                           placements=placements,
                           y_boundary=y_boundary,
                           skipped_placements=skipped_placements,
                           storm_enabled=bool(config.get("storm_enabled", True)))
    started = time.perf_counter()
    result = model.run()
    if args.paired_retention and result.results["mass"]["placed"] > 0:
        baseline = ShorelineModel(
            config, scenario=scenario, strategy="none", boundary=boundary,
            seed=seed, t_end=t_end, dx=float(config.get("dx", 25.0)),
            dt=float(config.get("dt", 0.02)), placements=[], events=model.events,
            storm_enabled=bool(config.get("storm_enabled", True)),
            y_boundary=y_boundary).run()
        denominator = result.results["mass"]["placed"]
        central = model.grid.central_mask
        base_y = np.stack([np.interp(result.fields["t"], baseline.fields["t"],
                                      baseline.fields["y"][:, j])
                           for j in range(model.grid.x.size)], axis=1)
        base_o = np.stack([np.interp(result.fields["t"], baseline.fields["t"],
                                      baseline.fields["O"][:, j])
                           for j in range(model.grid.x.size)], axis=1)
        from src.sim.units import book_volume
        delta = (book_volume(result.fields["y"], model.w0, model.h, model.v_ref)
                 + result.fields["O"] -
                 book_volume(base_y, model.w0, model.h, model.v_ref) - base_o)
        retention = {}
        for year in (1, 5, 15):
            if year > t_end or denominator <= 0:
                continue
            # Annual reports use the post-jump state at the requested time.
            # Event-aligned timesteps need not contain an exact integer year.
            values = delta[:, central].sum(axis=1) * model.grid.dx / denominator
            retention[f"R_ret_{year}yr"] = float(
                np.interp(year, result.fields["t"], values))
        result.results["retention"] = retention
        footprint = np.zeros(model.grid.x.size, dtype=bool)
        for item in model.placements:
            if item.time <= t_end:
                footprint |= np.abs(model.grid.x-item.center) < item.length/2
        db = (book_volume(result.fields['y'][-1],model.w0,model.h,model.v_ref)-
              book_volume(baseline.fields['y'][-1],model.w0,model.h,model.v_ref))*model.grid.dx
        fates = {'beach_original_footprint': float(db[footprint].sum()),
                 'beach_other_central': float(db[central & ~footprint].sum()),
                 'beach_buffers': float(db[~central & ~footprint].sum()),
                 'nearshore_reservoir': float((result.fields['O'][-1]-baseline.fields['O'][-1]).sum()*model.grid.dx),
                 'boundary_net_outflow': result.results['mass']['flux_out']-baseline.results['mass']['flux_out'],
                 'permanent_offshore_loss': result.results['mass']['offshore']-baseline.results['mass']['offshore'],
                 'avoided_current_deficit': baseline.results['mass']['R_c']-result.results['mass']['R_c']}
        result.results['sand_attribution'] = {'method':'paired intervention minus baseline; counterfactual effects, not tagged grains',
            'at_horizon_year':t_end, 'volume_m3':fates,
            'fraction_of_total_placed':{k:v/denominator for k,v in fates.items()},
            'closure_m3':float(denominator-sum(fates.values()))}
    elapsed = time.perf_counter() - started
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    result.results["meta"].update({
        "commit": git_sha(root),
        "config_md5": file_md5(config_path),
        "resolved_config_sha256": object_sha256(config),
        "params_md5": file_md5(root / "modeling" / "params.yaml"),
        "code_sha256": tree_sha256(root / "src"),
    })
    result.results["parameters"] = config
    write_json(out / "results.json", result.results)
    write_fields(out / "fields.npz", result.fields)
    write_ledger(out / "ledger.csv", result.ledger)
    write_events(out / "events.csv", result.events, result.event_records)
    write_recovery(out / "recovery.csv", result.recovery_records)
    run_meta = dict(result.results["meta"])
    run_meta.pop("run_seconds", None)
    run_meta["run_seconds"] = elapsed
    write_json(out / "meta.json", run_meta)
    print(f"wrote {out} residual_rel_max={result.results['mass']['residual_rel_max']:.3e}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
