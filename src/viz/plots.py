# -*- coding: utf-8 -*-
"""Figures F1-F8 (CODER_SPEC §7.2).

All figures are 300 dpi PNGs, readable in black and white (line styles + markers,
not colour alone), with axis units and an explicit data-type label
(OBS / MODEL / ASSUME / MODEL-SCENARIO) in the legend or a corner tag.

Usage::

    python -m viz.plots                 # all figures
    python -m viz.plots --which F1,F4   # subset
"""
from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Any, Dict, List, Optional

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

REPO_ROOT = Path(__file__).resolve().parents[2]
RESULTS = REPO_ROOT / "results"
FIGURES = REPO_ROOT / "figures"
DPI = 300
STYLE = {
    "figure.dpi": 120,
    "savefig.dpi": DPI,
    "font.size": 9,
    "axes.grid": True,
    "grid.alpha": 0.3,
    "axes.spines.top": False,
    "axes.spines.right": False,
}
plt.rcParams.update(STYLE)

SCN_MARK = {"S1": ("-", "o"), "S2": ("--", "s"), "S3": (":", "^")}
SHAPE_STYLE = {
    "uniform": ("-", "o", "0.20"),
    "hotspot": ("--", "s", "0.45"),
    "multi": ("-.", "^", "0.65"),
}


def _load_json(path: Path) -> Dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _load_csv(path: Path) -> List[Dict[str, Any]]:
    with path.open(encoding="utf-8") as fh:
        out = []
        for row in csv.DictReader(fh):
            parsed: Dict[str, Any] = {}
            for k, v in row.items():
                if v in ("", "None"):
                    parsed[k] = None
                else:
                    try:
                        parsed[k] = float(v)
                    except ValueError:
                        parsed[k] = v
            out.append(parsed)
    return out


def _tag(ax, text: str, loc: str = "upper left") -> None:
    xy = {"upper left": (0.02, 0.98), "upper right": (0.98, 0.98),
          "lower left": (0.02, 0.02), "lower right": (0.98, 0.02)}[loc]
    ax.text(*xy, text, transform=ax.transAxes, ha="left" if "left" in loc else "right",
            va="top" if "upper" in loc else "bottom", fontsize=7,
            bbox=dict(boxstyle="round,pad=0.2", fc="white", ec="0.6", lw=0.5))


# ---------------------------------------------------------------------------
def fig_f1(path: Path) -> None:
    d = np.load(RESULTS / "E1" / "uniform" / "fields.npz")
    x, t, w = d["x"], d["t"], d["w"]
    fig, ax = plt.subplots(figsize=(7.2, 4.2))
    im = ax.pcolormesh(x, t, w, shading="auto", cmap="viridis", vmin=0, vmax=45)
    cs = ax.contour(x, t, w, levels=[20.0], colors="w", linewidths=1.2)
    ax.clabel(cs, fmt="w=20 m", fontsize=7)
    ax.set_xlabel("along-shore distance x [m]")
    ax.set_ylabel("time [yr]")
    ax.set_title("F1  dry-beach width w(x,t), S1 + 1e6 m3 uniform at t=0 (MODEL-SCENARIO)")
    cb = fig.colorbar(im, ax=ax, pad=0.01)
    cb.set_label("w [m]")
    _tag(ax, "MODEL-SCENARIO\nidealised t=0 placement")
    fig.tight_layout()
    fig.savefig(path)
    plt.close(fig)


def fig_f2(path: Path) -> None:
    base = np.load(RESULTS / "E0" / "S1_deterministic" / "fields.npz")
    nour = np.load(RESULTS / "E1" / "uniform" / "fields.npz")
    x, t = nour["x"], nour["t"]
    positions = {
        "hotspot centre (x~0)": int(np.argmin(np.abs(x))),
        "hotspot edge (|x|~0.75 km)": int(np.argmin(np.abs(np.abs(x) - 750.0))),
        "buffer zone (|x|~3.0 km)": int(np.argmin(np.abs(np.abs(x) - 3000.0))),
    }
    fig, axes = plt.subplots(1, 3, figsize=(9.6, 3.2), sharey=True)
    for ax, (name, idx) in zip(axes, positions.items()):
        ax.plot(t, base["w"][:, idx], "k--", lw=1.1, label="baseline (MODEL-S1)")
        ax.plot(t, nour["w"][:, idx], "-", color="0.25", lw=1.4,
                label="+ 1e6 m3 uniform (MODEL)")
        ax.axhline(20.0, color="0.5", lw=1.0, ls=":", label="w_mgmt = 20 m (ASSUME)")
        ax.set_title(name, fontsize=8)
        ax.set_xlabel("time [yr]")
    axes[0].set_ylabel("dry-beach width w [m]")
    axes[0].legend(fontsize=6.5, loc="lower left")
    fig.suptitle("F2  w(t) at three along-shore positions (MODEL; no observational series exists)", fontsize=9)
    fig.tight_layout()
    fig.savefig(path)
    plt.close(fig)


def fig_f3(path: Path) -> None:
    rows = _load_csv(RESULTS / "E1" / "uniform" / "destinations.csv")
    t = np.array([r["t"] for r in rows])
    placed = np.array([r["placed"] for r in rows])
    mask = placed > 0.0
    ret = np.array([r["retained_domain"] for r in rows])[mask] / placed[mask]
    flux = np.array([r["flux_out_domain"] for r in rows])[mask] / placed[mask]
    off = np.array([r["offshore_loss"] for r in rows])[mask] / placed[mask]
    tt = t[mask]
    # NOTE: ΔR_c is a bookkeeping deficit, not a sand flow; it cancels in the
    # paired split (V_book = V_abs + R_c), so the three sand blocks are exactly
    # retained + out-of-domain + offshore = placed.
    fig, ax = plt.subplots(figsize=(6.6, 3.9))
    ax.stackplot(tt, flux * 100, off * 100,
                 labels=["flux out of 9 km domain", "permanent offshore loss"],
                 colors=["0.45", "0.20"], edgecolor="k", linewidth=0.4)
    total = (flux + off) * 100
    ax.plot(tt, total, "k-", lw=1.6, label="total loss  (= 100 % − retained)")
    ax.annotate(f"retained at {tt[-1]:.0f} yr: {100 * ret[-1]:.1f} %",
                xy=(tt[-1], total[-1]), xytext=(tt[-1] * 0.45, total[-1] * 0.55),
                fontsize=7, arrowprops=dict(arrowstyle="->", lw=0.6))
    ax.set_xlim(tt[0], tt[-1])
    ax.set_xlabel("time [yr]")
    ax.set_ylabel("share of placed volume [%]")
    ax.set_title("F3  where the placed sand goes (S1, 1e6 m3 uniform; paired difference)")
    ax.legend(fontsize=6.5, loc="upper left")
    _tag(ax, "MODEL (paired difference)\nchronic-loss difference = 0 by construction", "lower right")
    fig.tight_layout()
    fig.savefig(path)
    plt.close(fig)


def fig_f4(path: Path) -> None:
    fig, axes = plt.subplots(1, 2, figsize=(9.0, 3.4), sharey=True)
    for scn in ("S1", "S2", "S3"):
        rows = _load_csv(RESULTS / "E2" / f"{scn}_mc" / "mc_results.csv")
        for ax, key in zip(axes, ("T_first_fail_w", "T_first_fail_b")):
            vals = np.array([r[key] for r in rows if r[key] is not None])
            n_cens = sum(1 for r in rows if r[key] is None)
            ls, marker = SCN_MARK[scn]
            ax.hist(vals, bins=np.linspace(0, 15, 31), histtype="step",
                    linestyle=ls, lw=1.3, label=f"{scn} (censored {n_cens/len(rows):.0%})")
    for ax, title in zip(axes, ("beach-width criterion", "building-setback criterion")):
        ax.set_xlabel("first-failure time [yr]")
        ax.set_title(f"T_first_fail — {title}", fontsize=8)
        ax.legend(fontsize=7)
    axes[0].set_ylabel("realisations")
    fig.suptitle("F4  1000-realisation MC, strategy `once` (right-censored at 15 yr)", fontsize=9)
    fig.tight_layout()
    fig.savefig(path)
    plt.close(fig)


def fig_f5(path: Path) -> None:
    payload = _load_json(RESULTS / "E1" / "summary.json")
    rows = payload["generated_rows"]
    labels = [r["label"] for r in rows]
    xpos = np.arange(len(rows))
    tsafe = [r["T_safe_cum_w"] for r in rows]
    prot = [r["protected_shoreline_years"] for r in rows]
    fig, axes = plt.subplots(1, 2, figsize=(8.6, 3.4))
    axes[0].bar(xpos, tsafe, color=["0.75", "0.45", "0.60"], edgecolor="k", hatch=["", "//", ".."])
    axes[0].set_ylabel("T_safe_cum^w [yr]")
    axes[0].set_title("length-weighted safe years", fontsize=8)
    axes[1].bar(xpos, prot, color=["0.75", "0.45", "0.60"], edgecolor="k", hatch=["", "//", ".."])
    axes[1].set_ylabel("protected shoreline-years [m·yr]")
    axes[1].set_title("∫∫ 1{w≥w_mgmt} dx dt", fontsize=8)
    for ax in axes:
        ax.set_xticks(xpos)
        ells = {"uniform": 5000, "hotspot": 1000, "multi": 2500}
        ax.set_xticklabels([f"{l}\nell={ells.get(l, 0)} m" for l in labels])
    fig.suptitle("F5  placement comparison, same volume 1e6 m3 (S1, MODEL)", fontsize=9)
    fig.tight_layout()
    fig.savefig(path)
    plt.close(fig)


def fig_f6(path: Path) -> None:
    payload = _load_json(RESULTS / "E5" / "summary.json")
    rows = payload["generated_rows"]
    base = next(r for r in rows if r.get("param") == "base")
    groups: Dict[str, Dict[str, float]] = {}
    for r in rows:
        if r.get("param") == "base":
            continue
        groups.setdefault(r["param"], {})[r["label"].split("_")[-1]] = r["E_w"]
    items = []
    for param, d in groups.items():
        if "low" not in d or "high" not in d:
            continue
        items.append((param, d["low"], d["high"], abs(d["high"] - d["low"])))
    items.sort(key=lambda x: x[3])
    fig, ax = plt.subplots(figsize=(6.8, 4.6))
    ypos = np.arange(len(items))
    for i, (param, lo, hi, _) in enumerate(items):
        ax.barh(i, lo - base["E_w"], left=base["E_w"], color="0.70", edgecolor="k", height=0.6)
        ax.barh(i, hi - base["E_w"], left=base["E_w"], color="0.40", edgecolor="k", height=0.6,
                hatch="//")
        ax.text(min(lo, hi), i, f" {min(lo,hi):.0f}", va="center", fontsize=6)
        ax.text(max(lo, hi), i, f"{max(lo,hi):.0f} ", va="center", ha="right", fontsize=6)
    ax.axvline(base["E_w"], color="k", lw=1.0, ls="--")
    ax.set_yticks(ypos)
    ax.set_yticklabels([p for p, *_ in items])
    ax.set_xlabel("E_w  [m·yr]   (baseline dashed)")
    ax.set_title("F6  one-at-a-time sensitivity of cumulative beach-width exposure (S2, once)")
    _tag(ax, "MODEL-SCENARIO\nstorm group: rho_e_scale frozen at S2 value", "lower right")
    fig.tight_layout()
    fig.savefig(path)
    plt.close(fig)


def fig_f7(path: Path) -> None:
    rows = _load_csv(RESULTS / "E7" / "phase.csv")
    vols = sorted({r["V"] for r in rows})
    wmins = sorted({r["w_min"] for r in rows})
    fig, axes = plt.subplots(1, 2, figsize=(9.4, 3.8), sharey=True)
    for ax, shape in zip(axes, ("uniform", "hotspot")):
        z = np.full((len(wmins), len(vols)), np.nan)
        for r in rows:
            if r["shape"] != shape:
                continue
            i = wmins.index(r["w_min"])
            j = vols.index(r["V"])
            z[i, j] = r["protected_fraction"]
        im = ax.pcolormesh(vols, wmins, z, shading="auto", cmap="viridis",
                           vmin=0, vmax=1)
        vthr = 10.0 * 5000.0 * (20.0 - np.array(wmins))
        ax.plot(vthr, wmins, "w--", lw=1.2, label="V_thr = H L (w_mgmt - w_min)")
        ax.set_xscale("log")
        ax.set_xlabel("placed volume V [m3]")
        ax.set_title(f"placement = {shape}", fontsize=8)
        ax.legend(fontsize=6.5, loc="lower right")
    axes[0].set_ylabel("initial minimum beach width w_min [m]")
    cb = fig.colorbar(im, ax=axes, pad=0.01)
    cb.set_label("protected fraction of time [-]  (T_safe_cum/15 yr)")
    fig.suptitle("F7  V–w_min phase diagram (S1, idealised t=0 placement, MODEL)", fontsize=9)
    fig.savefig(path, bbox_inches="tight")
    plt.close(fig)


def fig_f8(path: Path) -> None:
    payload = _load_json(RESULTS / "E4" / "c0_scan_S2" / "c0_scan.json")
    rows = payload["rows"]
    strategies = ["once", "repeat", "targeted", "adaptive"]
    styles = {"once": ("-", "o"), "repeat": ("--", "s"),
              "targeted": ("-.", "^"), "adaptive": (":", "D")}
    fig, axes = plt.subplots(1, 2, figsize=(9.0, 3.4))
    for s in strategies:
        sel = [r for r in rows if r["strategy"] == s]
        c0 = [r["c0_M"] for r in sel]
        ls, mk = styles[s]
        axes[0].plot(c0, [r["E_w"] for r in sel], ls=ls, marker=mk, ms=4, lw=1.2, label=s)
        axes[1].plot(c0, [r["cost"] / 1e6 for r in sel], ls=ls, marker=mk, ms=4, lw=1.2, label=s)
    axes[0].set_ylabel("E_w [m·yr]")
    axes[1].set_ylabel("cost [M USD]")
    for ax in axes:
        ax.set_xlabel("fixed cost per project c0 [M USD]")
        ax.legend(fontsize=7)
    axes[0].set_title("beach-width exposure (E_b = 0; sand source binds before budget)",
                      fontsize=8)
    axes[1].set_title("total cost", fontsize=8)
    fig.suptitle("F8  strategy response to c0 (marginal cost structure only, S2)", fontsize=9)
    fig.tight_layout()
    fig.savefig(path)
    plt.close(fig)


FIGURES_MAP = {"F1": ("F1_w_xt.png", fig_f1), "F2": ("F2_w_t_positions.png", fig_f2),
               "F3": ("F3_sand_destinations.png", fig_f3),
               "F4": ("F4_T_first_fail_hist.png", fig_f4),
               "F5": ("F5_placement_bars.png", fig_f5),
               "F6": ("F6_oat_tornado.png", fig_f6),
               "F7": ("F7_phase_diagram.png", fig_f7),
               "F8": ("F8_c0_strategies.png", fig_f8)}


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description="Render figures F1-F8")
    p.add_argument("--which", default="F1,F2,F3,F4,F5,F6,F7,F8")
    args = p.parse_args(argv)
    FIGURES.mkdir(parents=True, exist_ok=True)
    which = [w.strip().upper() for w in args.which.split(",") if w.strip()]
    for key in which:
        name, fn = FIGURES_MAP[key]
        try:
            fn(FIGURES / name)
            print(f"[fig] {key} -> figures/{name}")
        except Exception as exc:  # keep going, report which figure failed
            print(f"[fig] {key} FAILED: {exc}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
