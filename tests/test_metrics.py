# -*- coding: utf-8 -*-
"""T12: spatial aggregation and initial conditions (MODEL_SPEC §6.3).

Initial failure fractions:
  analytic continuous: f_w(0) = 1518/5000 = 0.3036
  discrete (360 cells, dx=25, 60 central cells): 0.3000  (tolerance ±0.005)
  f_b(0) = 0
"""
import numpy as np

from sim.params import load_params, Scenario

from .helpers import cfg, simulate


def test_t12_initial_fractions_and_schema():
    params = load_params()
    scen = Scenario("S1", params)
    run = cfg(scenario="S1", t_end=15.0, bc="open")
    res = simulate(params, scen, run)
    m = res.metrics

    f_analytic = 1518.0 / 5000.0
    print(f"T12: f_w(0)={m['f_w0']:.4f} (discrete), analytic={f_analytic:.4f}; "
          f"f_b(0)={m['f_b0']:.4f}")
    assert abs(m["f_w0"] - 0.30) <= 0.005, m["f_w0"]
    assert abs(f_analytic - 0.3036) < 1e-9
    assert m["f_b0"] == 0.0, "no building is at risk initially"
    assert res.grid.n_central == 200

    # schema / censoring semantics
    from sim.io import build_results
    out = build_results(res)
    assert "T_first_any_w" not in out["duration"], "diagnostic must not enter duration"
    assert "T_first_any_w" in out["diagnostics"]
    for key in ("T_first_fail_w", "T_first_fail_b"):
        rec = out["duration"][key]
        assert (rec["value"] is None) == bool(rec["censored"]), \
            "censored flag and value must be mutually exclusive"
    for key in ("T_safe_cum_w", "T_safe_cum_b"):
        v = out["duration"][key]
        assert 0.0 <= v <= 15.0 + 1e-9, f"{key}={v}"
    assert out["exposure"]["E_w"] >= 0.0 and out["exposure"]["E_b"] >= 0.0
    assert out["mass"]["residual_rel_max"] < 1e-6
