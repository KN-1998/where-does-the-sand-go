"""Generate compact, reproducible figures from saved simulation artifacts."""

import argparse
import csv
import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np


def _json(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def _fields(path):
    data = np.load(path)
    return {key: data[key] for key in data.files}


def plot_heatmap(root, run, out):
    data = _fields(Path(root) / run / "fields.npz")
    x, t, w = data["x"] / 1000.0, data["t"], data["w"]
    fig, ax = plt.subplots(figsize=(8.0, 4.0), constrained_layout=True)
    im = ax.pcolormesh(x, t, w, shading="auto", cmap="viridis")
    fig.colorbar(im, ax=ax, label="Beach width (m)")
    ax.axvspan(-2.5, 2.5, color="white", alpha=0.08, lw=0)
    ax.set(xlabel="Alongshore coordinate (km)", ylabel="Time (yr)",
           title=f"{run}: simulated beach width")
    fig.savefig(Path(out) / f"{run}_width_heatmap.png", dpi=180)
    plt.close(fig)


def plot_profiles(root, runs, out):
    fig, ax = plt.subplots(figsize=(8.0, 4.0), constrained_layout=True)
    for run in runs:
        data = _fields(Path(root) / run / "fields.npz")
        central = np.abs(data["x"]) <= 2500.0
        ax.plot(data["x"][central] / 1000.0, data["w"][-1, central], label=run)
    ax.axhline(20.0, color="black", ls="--", lw=0.9, label="width threshold")
    ax.set(xlabel="Alongshore coordinate (km)", ylabel="Final beach width (m)",
           title="Final profiles: placement layouts")
    ax.legend(frameon=False, ncol=2)
    fig.savefig(Path(out) / "placement_profiles.png", dpi=180)
    plt.close(fig)


def plot_strategy_bars(root, summary_name, out):
    path = Path(root) / summary_name
    if not path.exists():
        return
    rows = list(csv.DictReader(path.open(encoding="utf-8", newline="")))
    rows = [row for row in rows if row.get("scenario") in {"S2", "S3"}
            and row.get("strategy") in {"none", "once", "repeat", "targeted", "adaptive"}]
    if not rows:
        return
    labels = []
    eb, ew = [], []
    for row in rows:
        labels.append(f"{row['scenario']}\n{row['strategy']}")
        eb.append(float(row["E_b_myr"]))
        ew.append(float(row["E_w_myr"]))
    positions = np.arange(len(labels))
    width = 0.38
    fig, ax = plt.subplots(figsize=(10.0, 4.5), constrained_layout=True)
    ax.bar(positions - width / 2, eb, width, label="$E_b$ (building clearance)")
    ax.bar(positions + width / 2, ew, width, label="$E_w$ (beach width)")
    ax.set_xticks(positions, labels)
    ax.set_ylabel("Risk exposure (m·yr)")
    ax.set_title("Deterministic strategy comparison")
    ax.legend(frameon=False)
    fig.savefig(Path(out) / "strategy_exposure.png", dpi=180)
    plt.close(fig)


def plot_mc(root, run, out):
    run_dir = Path(root) / run
    path = run_dir / "runs.csv"
    if not path.exists():
        return
    rows = list(csv.DictReader(path.open(encoding="utf-8", newline="")))
    if not rows:
        return
    metrics = [("E_b", "Building exposure (m·yr)"),
               ("T_safe_cum_b", "Cumulative building-safe time (yr)"),
               ("w_end_min", "Minimum final width (m)")]
    fig, axes = plt.subplots(1, len(metrics), figsize=(10.0, 3.2), constrained_layout=True)
    for ax, (key, label) in zip(axes, metrics):
        values = np.asarray([float(row[key]) for row in rows], dtype=float)
        ax.boxplot(values, vert=True, labels=["MC"])
        ax.set_ylabel(label)
        ax.grid(axis="y", alpha=0.25)
    fig.suptitle(f"{run}: Monte Carlo uncertainty")
    fig.savefig(Path(out) / f"{run}_uncertainty.png", dpi=180)
    plt.close(fig)


def plot_oat(root, run, out):
    path = Path(root) / run / "oat.csv"
    if not path.exists():
        return
    rows = list(csv.DictReader(path.open(encoding="utf-8", newline="")))
    values = {}
    for row in rows:
        values.setdefault(row["parameter"], []).append(float(row["E_b"]))
    if not values:
        return
    names = list(values)
    spread = [max(values[name]) - min(values[name]) for name in names]
    order = np.argsort(spread)
    fig, ax = plt.subplots(figsize=(7.5, 4.5), constrained_layout=True)
    ax.barh(np.arange(len(names)), np.asarray(spread)[order], color="#4472c4")
    ax.set_yticks(np.arange(len(names)), np.asarray(names)[order])
    ax.set_xlabel("Range of $E_b$ across OAT points (m·yr)")
    ax.set_title("OAT sensitivity of building exposure")
    fig.savefig(Path(out) / f"{run}_tornado.png", dpi=180)
    plt.close(fig)


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", default="results/final_20261112")
    parser.add_argument("--out", default=None)
    parser.add_argument("--heatmap", default="S2_once")
    parser.add_argument("--mc", default="MC_S2_once")
    parser.add_argument("--oat", default="OAT_S2_once")
    args = parser.parse_args(argv)
    out = Path(args.out or (Path(args.root) / "figures"))
    out.mkdir(parents=True, exist_ok=True)
    plot_heatmap(args.root, args.heatmap, out)
    available = [name for name in ("S1_uniform", "S1_hotspot", "S1_multi")
                 if (Path(args.root) / name / "fields.npz").exists()]
    if available:
        plot_profiles(args.root, available, out)
    plot_strategy_bars(args.root, "summary.csv", out)
    plot_mc(args.root, args.mc, out)
    plot_oat(args.root, args.oat, out)
    print(f"wrote figures to {out}")


if __name__ == "__main__":
    raise SystemExit(main())
