# -*- coding: utf-8 -*-
"""T4 (grid/time-step consistency) and T5 (no-storm analytical protection period).

T5 reference table (CODER_SPEC §6, analytical benchmark: uniform w0=18 m,
uniform rho_e=2.3 m/yr, V=1e6 m3, H=10 m, D=3e5):

    A uniform 5 km : dy0=20 m, T_p = 6.15 yr
    B hotspot 1 km : dy0=100 m, T_p = 7.33 yr
    C 0.5 km       : dy0=200 m, T_p = 7.36 yr
"""
import numpy as np

from sim.model import Simulator
from sim.placements import make_strategy
from sim.params import Scenario

from .helpers import P, cfg, simulate


def test_t4_dx_consistency():
    from sim.storms import build_event_table
    from exp.common import retention_curve
    from .helpers import P0
    # real erosion field; storms are replaced by one shared table so the only
    # difference between the two runs is the grid
    params = P0.clone_with({"lambda_s": 0.0})
    scen = Scenario("S1", params)
    table = build_event_table(scen, 42, 15.0, 4500.0, "uniform", [])
    metrics, retention = {}, {}
    for dx in (50.0, 25.0):
        run = cfg(scenario="S1", strategy="once", bc="open", t_end=15.0, dx=dx)
        nour = simulate(params, scen, run, events=table.events)
        base = simulate(params, scen, cfg(scenario="S1", strategy="none", bc="open",
                                         t_end=15.0, dx=dx), events=table.events)
        metrics[dx] = nour.metrics
        retention[dx] = retention_curve(nour, base, [15.0], float(params["H_dep"]))
    for key in ("E_w", "T_safe_cum_w", "T_safe_cum_b"):
        a, b = metrics[50.0][key], metrics[25.0][key]
        rel = abs(a - b) / max(1e-12, abs(b))
        print(f"T4: {key} dx=50 -> {a:.6g}, dx=25 -> {b:.6g}, rel diff {rel:.2%}")
        assert rel < 0.02, f"T4 failed for {key}: {rel:.2%}"
    # T_first_fail_w and the 15-yr retention are the contract's key indicators
    ta = metrics[50.0]["T_first_fail_w"]["value"]
    tb = metrics[25.0]["T_first_fail_w"]["value"]
    if ta is not None and tb is not None:
        rel = abs(ta - tb) / max(1e-12, tb)
        print(f"T4: T_first_fail_w dx=50 -> {ta:.3f}, dx=25 -> {tb:.3f}, rel {rel:.2%}")
        assert rel < 0.02
    ra = retention[50.0]["R_ret_15yr"]
    rb = retention[25.0]["R_ret_15yr"]
    rel = abs(ra - rb) / max(1e-12, abs(rb))
    print(f"T4: R_ret_15yr dx=50 -> {ra:.4f}, dx=25 -> {rb:.4f}, rel {rel:.2%}")
    assert rel < 0.02


def test_t5_protection_period():
    """T5: model protection period against the analytical erf benchmark."""
    params = P(rho_e=2.3, rho_e_hotspot_amp=0.0, w0_far=18.0, w0_min=18.0,
               u_drift=0.0, lambda_s=0.0)
    scen = Scenario("base", params)
    run = cfg(bc="open", t_end=15.0)
    cases = {"A": (5000.0, 1.0e6, 6.15), "B": (1000.0, 1.0e6, 7.33),
             "C": (500.0, 1.0e6, 7.36)}
    for name, (ell, vol, reference) in cases.items():
        spec = [{"t": 0.0, "xc": 0.0, "len": ell, "volume": vol, "budgeted": False}]
        res = simulate(params, scen, run, placements=spec)
        w = res.w0[None, :] + res.y
        ic = int(np.argmin(np.abs(res.grid.x)))
        crossing = np.flatnonzero(w[:, ic] < 20.0)
        assert crossing.size > 0, f"T5 {name}: centre never failed"
        t_model = float(res.t[crossing[0]])
        rel = abs(t_model - reference) / reference
        print(f"T5 {name}: ell={ell:.0f} dy0={vol / (10 * ell):.0f} "
              f"T_p model={t_model:.2f} ref={reference:.2f} rel={rel:.2%}")
        assert rel < 0.10, f"T5 {name} relative error {rel:.2%} > 10%"
