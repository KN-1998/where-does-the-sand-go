"""Paired unscaled L0 diagnostic using the byte-frozen R2 solver.

The extension stays outside src and modeling/params.yaml so historical R2
ensembles retain their original source and resolved-parameter identities.
"""
import os
os.environ.setdefault("OPENBLAS_NUM_THREADS", "1")
os.environ.setdefault("OMP_NUM_THREADS", "1")

import argparse
from concurrent.futures import ProcessPoolExecutor
from copy import deepcopy
from hashlib import sha256
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import numpy as np
import yaml
from src.sim.io import (git_sha, load_config, object_sha256, tree_sha256,
                        write_events, write_fields, write_json, write_ledger,
                        write_recovery)
from src.sim.model import ShorelineModel
from src.sim.storms import generate_events


class DiagnosticModel(ShorelineModel):
    """Change only the chronic-field selection and the stationary event label."""

    def __init__(self, config, seed):
        if config["scenario"] != "L0_diag" or config["strategy"] != "none":
            raise ValueError("DiagnosticModel requires L0_diag / none")
        # Replay the original stationary S1 generator with L0's rates. S1 has
        # no forced event; using S2 would add a forced shock at t=2.25.
        event_config = deepcopy(config)
        event_config["scenarios"]["S1_calm"] = deepcopy(config["scenarios"]["L0_diag"])
        events = (generate_events(event_config, "S1", config["t_end"], seed)[0]
                  if config["storm_enabled"] else [])
        super().__init__(config, scenario="L0_diag", strategy="none",
                         boundary=config["bc"], seed=seed, t_end=config["t_end"],
                         dx=config["dx"], dt=config["dt"], placements=[], events=events,
                         storm_enabled=config["storm_enabled"])

    def _rho(self, t):
        return self.rho_base.copy()


def resolved_pair(seed):
    configs = [load_config(ROOT / f"configs/caliber_{group}.yaml") for group in ("A", "B")]
    for config in configs:
        config.update(seed=int(seed), strategy="none")
    left, right = [deepcopy(config) for config in configs]
    if left.pop("storm_enabled") is not False or right.pop("storm_enabled") is not True or left != right:
        raise ValueError("A/B must differ only in storm_enabled")
    return configs


def scalar(model, simulation, index):
    result = simulation.results
    return {"index": int(index), "seed": model.seed,
            "retreat_mean": (result["initial"]["w_mean"] - result["state"]["w_end_mean"]) / model.t_end,
            "residual_rel_max": result["mass"]["residual_rel_max"],
            "residual_central_rel_max": result["mass"]["residual_central_rel_max"],
            "events": result["events"]["n_events_applied"],
            "forced_events": sum(event.forced for event in model.events),
            "event_table_sha256": object_sha256([vars(event) for event in model.events]),
            "rho_corridor_mean": float(model.rho_base[model.grid.central_mask].mean())}


def run_pair(job):
    index, seed = job
    output = []
    for config in resolved_pair(seed):
        model = DiagnosticModel(config, seed)
        simulation = model.run()
        output.append(scalar(model, simulation, index))
    return output


def mean_statistics(values):
    values = np.asarray(values, dtype=float)
    mean = float(values.mean())
    se = float(values.std(ddof=1) / np.sqrt(values.size)) if values.size > 1 else 0.0
    return {"n": int(values.size), "retreat_mean": mean, "MCSE": se,
            "CI95": [mean - 1.96 * se, mean + 1.96 * se]}


def identity():
    source = tree_sha256(ROOT / "src")
    frozen = json.loads((ROOT / "CODE_VERSION.json").read_text(encoding="utf-8"))
    if source != frozen["src_sha256"]:
        raise RuntimeError("Frozen R2 source has changed")
    return {"git_commit": git_sha(ROOT), "source_sha256": source,
            "diagnostic_sha256": sha256(Path(__file__).read_bytes()).hexdigest(),
            "diagnostic_file": "tools/caliber_r2.py"}


def save_deterministic(out, seed, provenance):
    records = []
    for group, config in zip(("A", "B"), resolved_pair(seed)):
        path = out / f"{group}_det"
        path.mkdir(parents=True, exist_ok=True)
        model = DiagnosticModel(config, seed)
        simulation = model.run()
        row = scalar(model, simulation, 0)
        simulation.results["meta"].update(provenance)
        simulation.results["parameters"] = config
        simulation.results["caliber"] = row
        write_json(path / "results.json", simulation.results)
        write_json(path / "meta.json", {**provenance, **row})
        write_fields(path / "fields.npz", simulation.fields)
        write_ledger(path / "ledger.csv", simulation.ledger)
        write_events(path / "events.csv", simulation.events, simulation.event_records)
        write_recovery(path / "recovery.csv", simulation.recovery_records)
        (path / "resolved_config.yaml").write_text(
            yaml.safe_dump(config, allow_unicode=True, sort_keys=False), encoding="utf-8", newline="\n")
        records.append(row)
    return records


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--n", type=int, default=1000)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--workers", type=int, default=8)
    parser.add_argument("--out", type=Path, default=ROOT / "results/caliber_R2")
    args = parser.parse_args()
    if args.n < 2 or args.workers < 1:
        parser.error("n >= 2 and workers >= 1 required")
    out = args.out.resolve()
    out.mkdir(parents=True, exist_ok=True)
    provenance = identity()
    deterministic = save_deterministic(out, args.seed, provenance)
    jobs = [(i, (args.seed * 1000003 + i) % 2**32) for i in range(args.n)]
    rows = [[], []]
    with ProcessPoolExecutor(max_workers=args.workers) as pool:
        for count, pair in enumerate(pool.map(run_pair, jobs, chunksize=5), 1):
            for side, row in zip(rows, pair):
                side.append(row)
            if count % 100 == 0 or count == args.n:
                print(f"paired runs {count}/{args.n}", flush=True)
    for group, config, side in zip(("A", "B"), resolved_pair(args.seed), rows):
        path = out / f"{group}_mc"
        path.mkdir(exist_ok=True)
        write_ledger(path / "runs.csv", side)
        stats = mean_statistics([row["retreat_mean"] for row in side])
        write_json(path / "summary.json", {**provenance, **stats, "runs": side,
                   "resolved_config": config, "base_seed": args.seed,
                   "seed_rule": "(base_seed*1000003+i) mod 2**32",
                   "residual_rel_max": max(r["residual_rel_max"] for r in side),
                   "residual_central_rel_max": max(r["residual_central_rel_max"] for r in side)})
    paired = []
    for a, b in zip(*rows):
        if (a["index"], a["seed"]) != (b["index"], b["seed"]):
            raise RuntimeError("Unpaired realization")
        paired.append({"index": a["index"], "seed": a["seed"],
                       "A_retreat": a["retreat_mean"], "B_retreat": b["retreat_mean"],
                       "difference": b["retreat_mean"] - a["retreat_mean"],
                       "storm_contribution_relative": (b["retreat_mean"] - a["retreat_mean"]) / 2.3136,
                       "bias_vs_field": (a["retreat_mean"] + (b["retreat_mean"] - a["retreat_mean"]) - 2.3136) / 2.3136})
    write_ledger(out / "paired_differences.csv", paired)
    delta = mean_statistics([row["difference"] for row in paired])
    maximum = max(r[key] for side in rows for r in side
                  for key in ("residual_rel_max", "residual_central_rel_max"))
    maximum = max(maximum, *(r[key] for r in deterministic
                  for key in ("residual_rel_max", "residual_central_rel_max")))
    if not np.isfinite(maximum) or maximum >= 1e-6 or delta["retreat_mean"] <= 0:
        raise RuntimeError("Conservation or positive paired contribution acceptance failed")
    summary = {**provenance, "field_mean_rho": 2.3136,
               "field_mean_rho_grid": rows[0][0]["rho_corridor_mean"],
               "A_nostorm": mean_statistics([r["retreat_mean"] for r in rows[0]]),
               "B_storm": mean_statistics([r["retreat_mean"] for r in rows[1]]),
               "realised_storm_contribution": delta["retreat_mean"],
               "bias_vs_field": float(np.mean([r["bias_vs_field"] for r in paired])),
               "storm_contribution_relative": float(np.mean([r["storm_contribution_relative"] for r in paired])),
               "paired_difference": delta, "residual_rel_max": maximum,
               "deterministic": {"A_nostorm": deterministic[0], "B_storm": deterministic[1]},
               "n_pairs": args.n, "base_seed": args.seed,
               "metric": "(initial raw corridor mean w - final raw corridor mean w) / 15 yr; no zero clipping",
               "CI_method": "mean +/- 1.96*MCSE; storm sampling only, fixed parameters",
               "bias_definition": "mean_i[(A_i + (B_i-A_i) - 2.3136)/2.3136]; total with-storm bias vs field",
               "storm_contribution_relative_definition": "mean_i[(B_i-A_i)/2.3136]"}
    write_json(out / "summary.json", summary)
    (out / "README.md").write_text(
        "# R2 caliber diagnostic\n\n"
        "A/B 的唯一配置差别为 storm_enabled；不用 no_storm.yaml，因为它继承 S1 的目标速率扣风暴缩放，无法提供要求的未缩放慢性场。\n\n"
        "复现：在仓库根目录执行 `python tools/caliber_r2.py --n 1000 --seed 42 --workers 8`。"
        "L0_diag 定义放在 caliber_A/B.yaml 中，工具子类只覆盖 _rho 返回原始 rho_base；事件用冻结 S1 平稳泊松生成器传入 L0 频率/强度，无强制事件。"
        "src/ 与 modeling/params.yaml 保持 R2 字节不变；source_sha256 对应 CODE_VERSION.json，diagnostic_sha256 单独标识新增工具。\n\n"
        "9 km 域、360 格、dx=25 m、dt=0.02 yr、open、15 yr、无补沙。lambda=0.4/yr，中位8 m，"
        "sigma_ln=ln(25/8)/1.645（约0.6927，沿用 R2 的95分位近似）。rho 场为1.7[1+1.2 exp(-x²/(2*600²))]；"
        "分母按要求使用2.3136 m/yr，另报 field_mean_rho_grid 实际网格均值。侵蚀热点 sigma_h=600 m 与初始滩宽 sigma_w=700 m 为原R2不同参数。\n\n"
        "MC 每个配对种子分别实际运行 A/B，不复用无风暴输出；原始样本在 A_mc/B_mc/runs.csv。"
        "贡献与偏差从 paired_differences.csv 的逐对差计算。后退率采用原始 y（耗尽后允许负滩宽），不将滩宽裁零；"
        "CI95 仅反映固定参数下风暴采样误差。bias_vs_field=mean[(A_i+(B_i-A_i)-2.3136)/2.3136] 为有风暴总后退相对场均值的偏差，"
        "与R3所举R1约1.6%的口径一致；storm_contribution_relative=mean[(B_i-A_i)/2.3136] 单独报告增量贡献占比。二者不可混用。\n",
        encoding="utf-8", newline="\n")
    print(json.dumps(summary, indent=2), flush=True)


if __name__ == "__main__":
    main()
