# -*- coding: utf-8 -*-
"""T1 (mass closure), T3(a,b,c) (zero source / zero flux / O decay),
T13 (erosion then refill) -- see tests/README.md and CODER_SPEC §5.

Initial reference (modeling/sanity/discrete_contract.py):
    T3a max|dy|  7.5e-13
    T3c rel err  2.8e-15
    T1  rel      1.1e-13
    T13 rel      1.4e-13
"""
import csv

import numpy as np

from sim.io import write_results
from sim.model import Simulator
from sim.placements import make_strategy
from sim.params import Scenario
from sim.storms import EventTable

from .helpers import P, cfg, simulate


def test_t1_closure(tmp_path):
    """T1: every ledger row closes to < 1e-6 (relative)."""
    from sim.params import load_params
    params = load_params()
    scen = Scenario("S2", params)
    run = cfg(scenario="S2", strategy="once", t_end=5.0,
              forced_events=list(scen.forced_events))
    sim = Simulator(params, scen, run, store_fields=False)
    res = sim.run_loop(5.0, events=None,
                       strategy=make_strategy(params, run, sim.budget), collect=True)
    assert res.ledger.rows, "ledger is empty"
    assert res.budget["n_projects"] == 1, "once strategy should place exactly one project"
    max_rel = max(abs(r["residual_rel"]) for r in res.ledger.rows)
    print(f"T1: rows={len(res.ledger.rows)} placed={res.budget['V_used']:.3e} "
          f"max|residual_rel|={max_rel:.3e}")
    assert max_rel < 1e-6, f"T1 failed: max|residual_rel|={max_rel:.3e}"

    # also via the written ledger.csv (the artefact the modeler will inspect)
    out = tmp_path / "T1"
    write_results(out, res, write_fields=False)
    with (out / "ledger.csv").open(encoding="utf-8") as fh:
        rows = list(csv.DictReader(fh))
    assert rows, "ledger.csv empty"
    rel = max(abs(float(r["residual_rel"])) for r in rows)
    assert rel < 1e-6, f"ledger.csv residual_rel={rel:.3e}"
    assert abs(float(rows[-1]["placed_cum"]) - res.budget["V_used"]) < 1e-6


def test_t3a_zero_source_uniform():
    """T3(a): uniform y, zero flux, no source -> field unchanged."""
    params = P()
    scen = Scenario("base", params)
    run = cfg(bc="zeroflux", t_end=5.0)
    y0 = np.full(360, 3.0)
    res = simulate(params, scen, run, y0=y0)
    err = float(np.abs(res.y_end - 3.0).max())
    print(f"T3a: max|dy|={err:.2e}")
    assert err < 1e-12, err


def test_t3b_zeroflux_mass():
    """T3(b): non-uniform field, zero total flux -> total mass conserved."""
    params = P(u_drift=50.0)
    scen = Scenario("base", params)
    run = cfg(bc="zeroflux", t_end=2.0)
    rng = np.random.default_rng(3)
    y0 = 5.0 + rng.normal(0.0, 0.5, 360)
    res = simulate(params, scen, run, y0=y0)
    H, dx = 10.0, res.grid.dx
    m0 = float(y0.sum() * dx * H)
    m1 = float(res.y_end.sum() * dx * H)
    rel = abs(m1 - m0) / abs(m0)
    print(f"T3b: mass0={m0:.6e} mass1={m1:.6e} rel={rel:.2e}")
    assert rel < 1e-10, rel


def test_t3c_o_decay():
    """T3(c): O alone decays as exp(-(k+lambda)t)."""
    params = P()
    scen = Scenario("base", params)
    run = cfg(bc="zeroflux", t_end=3.0)
    res = simulate(params, scen, run, O0=np.full(360, 100.0))
    a = float(params["k_rec"]) + float(params["lam_off"])
    pred = 100.0 * np.exp(-a * 3.0)
    rel = abs(res.O_end[0] - pred) / pred
    print(f"T3c: O_end={res.O_end[0]:.6e} pred={pred:.6e} rel={rel:.2e}")
    assert rel < 1e-12, rel


def test_t13_erode_refill():
    """T13: 5 yr erosion -> 1.5e7 m3 refill -> 5 yr; closure, R_c drops."""
    params = P(rho_e=12.0)
    scen = Scenario("base", params)
    run = cfg(strategy="scripted", bc="zeroflux", t_end=10.0)
    spec = [{"t": 5.0, "xc": 0.0, "len": 5000.0, "volume": 1.5e7, "budgeted": False}]
    sim = Simulator(params, scen, run, store_fields=False)
    res = sim.run_loop(10.0, events=EventTable([]),
                       strategy=make_strategy(params, run, sim.budget, placements=spec),
                       collect=True)
    rows = res.ledger.rows
    final = rows[-1]
    rel = abs(final["residual"]) / max(1.0, abs(final["placed_cum"]))
    i5 = int(np.argmin(np.abs(res.t - 5.0)))
    rc_before = rows[i5]["R_c_cum"]
    rc_after = rows[min(i5 + 1, len(rows) - 1)]["R_c_cum"]
    dmax = [r["D_max_cum"] for r in rows]
    monotone = all(b >= a - 1e-9 for a, b in zip(dmax[:-1], dmax[1:]))
    print(f"T13: final rel={rel:.2e} R_c(t=5)={rc_before:.3e} "
          f"R_c(after)={rc_after:.3e} D_max monotone={monotone}")
    assert rel < 1e-10, rel
    assert rc_after < rc_before, "R_c must fall after refill (current deficit, not peak)"
    assert monotone, "D_max must be non-decreasing"
