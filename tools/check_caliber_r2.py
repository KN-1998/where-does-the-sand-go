"""Read-only acceptance checks for the paired R2 caliber supplement."""
import argparse
from copy import deepcopy
import csv
from hashlib import sha256
import json
import math
from pathlib import Path
import statistics
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import yaml
from src.sim.io import object_sha256, tree_sha256
from src.sim.storms import generate_events
from tools.caliber_r2 import DiagnosticModel, resolved_pair


def require(condition, message):
    if not condition:
        raise RuntimeError(message)


def near(actual, expected, label):
    actual, expected = float(actual), float(expected)
    require(math.isfinite(actual) and math.isfinite(expected), label + ": nonfinite")
    require(math.isclose(actual, expected, rel_tol=1e-12, abs_tol=1e-13),
            f"{label}: {actual!r} != {expected!r}")


def read_json(path):
    return json.loads(path.read_text(encoding="utf-8"))


def read_csv(path):
    with path.open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def stats(values):
    mean = statistics.mean(values)
    error = statistics.stdev(values) / math.sqrt(len(values))
    return {"n": len(values), "retreat_mean": mean, "MCSE": error,
            "CI95": [mean - 1.96 * error, mean + 1.96 * error]}


def check_statistics(actual, values, label):
    expected = stats(values)
    require(actual["n"] == expected["n"], label + ": sample count")
    for key in ("retreat_mean", "MCSE"):
        near(actual[key], expected[key], f"{label}.{key}")
    require(len(actual["CI95"]) == 2, label + ": CI95 must have two endpoints")
    for index, value in enumerate(expected["CI95"]):
        near(actual["CI95"][index], value, f"{label}.CI95[{index}]")


def check_provenance(record, provenance, label):
    for key, value in provenance.items():
        require(record.get(key) == value, f"{label}: mismatched {key}")


def check_residual(record, label):
    for key in ("residual_rel_max", "residual_central_rel_max"):
        value = float(record[key])
        require(math.isfinite(value) and 0 <= value < 1e-6, f"{label}: invalid {key}")


def expected_events(config, seed):
    if not config["storm_enabled"]:
        return []
    event_config = deepcopy(config)
    event_config["scenarios"]["S1_calm"] = deepcopy(config["scenarios"]["L0_diag"])
    return generate_events(event_config, "S1", config["t_end"], seed)[0]


def check_event_identity(row, config, label):
    events = expected_events(config, int(row["seed"]))
    require(int(row["events"]) == len(events), label + ": event count")
    require(int(row["forced_events"]) == 0, label + ": forced event")
    require(row["event_table_sha256"] == object_sha256([vars(event) for event in events]),
            label + ": event table differs from stationary R2 generator")
    return events


def check_git_provenance(commit, diagnostic_hash):
    git = lambda *args: subprocess.check_output(["git", *args], cwd=ROOT, stderr=subprocess.PIPE)
    require(len(commit) == 40 and all(c in "0123456789abcdef" for c in commit), "invalid git_commit")
    git("merge-base", "--is-ancestor", commit, "HEAD")
    recorded = git("show", f"{commit}:tools/caliber_r2.py")
    require(sha256(recorded).hexdigest() == diagnostic_hash,
            "git_commit does not contain the recorded diagnostic implementation")


def check(root):
    summary = read_json(root / "summary.json")
    n = summary["n_pairs"]
    require(isinstance(n, int) and n >= 200, "At least 200 paired realizations required")
    near(summary["field_mean_rho"], 2.3136, "field_mean_rho")
    provenance = {key: summary[key] for key in
                  ("git_commit", "source_sha256", "diagnostic_sha256", "diagnostic_file")}
    require(provenance["diagnostic_file"] == "tools/caliber_r2.py", "unexpected diagnostic file")
    require(provenance["source_sha256"] == read_json(ROOT / "CODE_VERSION.json")["src_sha256"]
            == tree_sha256(ROOT / "src"), "R2 source identity mismatch")
    require(provenance["diagnostic_sha256"] == sha256((ROOT / "tools/caliber_r2.py").read_bytes()).hexdigest(),
            "diagnostic source identity mismatch")
    check_git_provenance(provenance["git_commit"], provenance["diagnostic_sha256"])

    config_paths = [root / f"{group}_det/resolved_config.yaml" for group in ("A", "B")]
    texts = [path.read_bytes() for path in config_paths]
    require(texts[0].count(b"storm_enabled: false") == 1, "A missing unique disabled switch")
    require(texts[1].count(b"storm_enabled: true") == 1, "B missing unique enabled switch")
    require(texts[0].replace(b"storm_enabled: false", b"storm_enabled: true") == texts[1],
            "deterministic resolved configs differ beyond storm_enabled")
    configs = [yaml.safe_load(text.decode("utf-8")) for text in texts]
    expected_configs = resolved_pair(summary["base_seed"])
    require(configs == expected_configs, "resolved configs differ from current caliber_A/B inputs")
    require(summary["base_seed"] == 42, "deterministic and MC base seed must be 42")
    for config in configs:
        require((config["scenario"], config["strategy"], config["bc"], config["t_end"], config["dx"], config["dt"])
                == ("L0_diag", "none", "open", 15., 25., .02), "incorrect experimental controls")
        require(config["scenarios"]["L0_diag"] == {"lambda_s": .4, "dy_ref": 8., "rho_e": 2.3136},
                "incorrect L0 event parameters")
    model = DiagnosticModel(configs[0], 42)
    require(model.grid.x.size == 360 and model.grid.central_mask.sum() == 200, "incorrect grid/domain")
    field_mean = float(model.rho_base[model.grid.central_mask].mean())
    near(summary["field_mean_rho_grid"], field_mean, "field_mean_rho_grid")

    residuals = []
    group_rows = []
    for group, config, name in zip(("A", "B"), configs, ("A_nostorm", "B_storm")):
        det = root / f"{group}_det"
        result = read_json(det / "results.json")
        meta = read_json(det / "meta.json")
        row = result["caliber"]
        check_provenance(result["meta"], provenance, group + " deterministic results")
        check_provenance(meta, provenance, group + " deterministic meta")
        require(result["parameters"] == config, group + ": deterministic parameters")
        require(all(meta.get(k) == v for k, v in row.items()), group + ": meta/scalar mismatch")
        require(row == summary["deterministic"][name], group + ": top-level deterministic mismatch")
        require(row["seed"] == 42 and row["index"] == 0, group + ": deterministic seed/index")
        near(row["retreat_mean"], (result["initial"]["w_mean"] - result["state"]["w_end_mean"]) / 15,
             group + ": deterministic retreat")
        check_residual(row, group + " deterministic")
        for key in ("residual_rel_max", "residual_central_rel_max"):
            near(row[key], result["mass"][key], group + ": deterministic " + key)
            residuals.append(float(row[key]))
        ledger = read_csv(det / "ledger.csv")
        for key, column in (("residual_rel_max", "residual_rel"),
                            ("residual_central_rel_max", "residual_central_rel")):
            values = [float(item[column]) for item in ledger]
            require(all(math.isfinite(value) and 0 <= value < 1e-6 for value in values), group + ": ledger residual")
            near(row[key], max(values), group + ": ledger " + key)
        events = check_event_identity(row, config, group + " deterministic")
        applied = read_csv(det / "events.csv")
        require(len(applied) == len(events) == result["events"]["n_events_applied"], group + ": applied events")
        for index, (record, event) in enumerate(zip(applied, events)):
            near(record["t"], event.time, f"{group} event {index} time")
            near(record["potential_retreat"], event.potential_retreat, f"{group} event {index} magnitude")
            require(record["forced"] == "False" and record["forced_actual_retreat"] == "", group + ": forced applied event")

        mc = read_json(root / f"{group}_mc/summary.json")
        check_provenance(mc, provenance, group + " MC")
        require(mc["n"] == n and mc["base_seed"] == summary["base_seed"], group + ": MC count/seed")
        require(mc["seed_rule"] == "(base_seed*1000003+i) mod 2**32", group + ": seed rule")
        require(mc["resolved_config"] == config, group + ": MC config")
        rows = read_csv(root / f"{group}_mc/runs.csv")
        require(len(rows) == len(mc["runs"]) == n, group + ": row count")
        for index, (record, saved) in enumerate(zip(rows, mc["runs"])):
            label = f"{group} MC index {index}"
            require(set(record) == set(saved), label + ": row columns")
            for key, value in saved.items():
                if isinstance(value, str):
                    require(record[key] == value, label + ": " + key)
                else:
                    near(record[key], value, label + ": " + key)
            require(int(record["index"]) == index, label + ": index order")
            require(int(record["seed"]) == (summary["base_seed"] * 1000003 + index) % 2**32, label + ": seed")
            check_residual(record, label)
            check_event_identity(record, config, label)
            near(record["rho_corridor_mean"], field_mean, label + ": chronic field")
            residuals.extend(float(record[key]) for key in ("residual_rel_max", "residual_central_rel_max"))
        values = [float(record["retreat_mean"]) for record in rows]
        check_statistics(mc, values, group + " MC statistics")
        check_statistics(summary[name], values, group + " top-level statistics")
        for key in ("residual_rel_max", "residual_central_rel_max"):
            near(mc[key], max(float(record[key]) for record in rows), group + " MC " + key)
        group_rows.append(rows)

    paired = read_csv(root / "paired_differences.csv")
    require(len(paired) == n, "paired CSV row count")
    differences, biases, shares = [], [], []
    for index, (a, b, row) in enumerate(zip(*group_rows, paired)):
        label = f"paired index {index}"
        require(int(a["index"]) == int(b["index"]) == int(row["index"]) == index, label + ": indices")
        require(int(a["seed"]) == int(b["seed"]) == int(row["seed"]), label + ": seeds")
        a_value, b_value = float(a["retreat_mean"]), float(b["retreat_mean"])
        difference = b_value - a_value
        bias = (a_value + difference - 2.3136) / 2.3136
        share = difference / 2.3136
        for key, value in (("A_retreat", a_value), ("B_retreat", b_value), ("difference", difference),
                           ("bias_vs_field", bias), ("storm_contribution_relative", share)):
            near(row[key], value, label + ": " + key)
        differences.append(difference)
        biases.append(bias)
        shares.append(share)
    check_statistics(summary["paired_difference"], differences, "paired difference statistics")
    near(summary["realised_storm_contribution"], statistics.mean(differences), "realised_storm_contribution")
    near(summary["bias_vs_field"], statistics.mean(biases), "bias_vs_field")
    near(summary["storm_contribution_relative"], statistics.mean(shares), "storm_contribution_relative")
    near(summary["residual_rel_max"], max(residuals), "residual_rel_max")
    require(summary["A_nostorm"]["retreat_mean"] < summary["B_storm"]["retreat_mean"], "storm contribution not positive")
    return n, max(residuals)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=ROOT / "results/caliber_R2")
    args = parser.parse_args()
    try:
        n, residual = check(args.root.resolve())
    except (OSError, ValueError, KeyError, TypeError, RuntimeError, subprocess.CalledProcessError) as error:
        print(f"FAIL caliber_R2: {error}", file=sys.stderr)
        return 1
    print(f"PASS caliber_R2: {n} paired seeds; configs, events, statistics and provenance verified; residual={residual:.3e}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
