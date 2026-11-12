# -*- coding: utf-8 -*-
"""T7: boundary flux bookkeeping against a known outflow.

Design: a Gaussian bump in the middle of a 6 km domain, u>0 and D>0, advected
fully through the right boundary.  For an open boundary the whole initial mass
must leave through the right face (the left face has no inflow because the
upstream state is ~0).  This is an exact "known outflow" case and tests sign,
units (H*F*dt) and the limiter.
"""
import numpy as np

from sim.model import Simulator

from .helpers import P, cfg, simulate


def _run(bc):
    params = P(u_drift=300.0, D_diff=1.0e4)
    from sim.params import Scenario
    scen = Scenario("base", params)
    run = cfg(bc=bc, t_end=20.0, Lb=3000.0)
    g = Simulator(params, scen, run).grid
    y0 = 20.0 * np.exp(-g.x ** 2 / (2 * 300.0 ** 2))
    res = simulate(params, scen, run, y0=y0)
    mass0 = float(10.0 * y0.sum() * g.dx)
    return res, mass0


def test_t7_open_boundary_flux():
    res, mass0 = _run("open")
    last = res.ledger.rows[-1]
    right = last["flux_outer_right_cum"]
    left = last["flux_outer_left_cum"]
    rel = abs(right - mass0) / mass0
    print(f"T7: mass0={mass0:.3f} right_out={right:.3f} left={left:.3f} "
          f"remaining={last['V_domain']:.3f} rel={rel:.2%}")
    assert rel < 0.10, f"open-boundary outflow differs from known loss by {rel:.2%}"
    assert abs(left) < 0.01 * mass0, "u>0 with an empty upstream should not import sand"
    assert abs(last["residual_rel"]) < 1e-6


def test_t7_zeroflux_has_no_flux():
    res, mass0 = _run("zeroflux")
    last = res.ledger.rows[-1]
    print(f"T7 zeroflux: left={last['flux_outer_left_cum']} "
          f"right={last['flux_outer_right_cum']} inside={last['V_domain']:.3f}")
    assert last["flux_outer_left_cum"] == 0.0
    assert last["flux_outer_right_cum"] == 0.0
    # V_domain is the *increment* over the initial state: zero-flux conserves it
    assert abs(last["V_domain"]) / mass0 < 1e-6
