# -*- coding: utf-8 -*-
"""T11: non-negativity is imposed on V (not on y); R_c is the *current* deficit.

Criterion set (CODER_SPEC §5):
  (a) min V_book >= V_min - 1e-9              (judge V, not y)
  (b) some cell has y < -w0 and y is NOT clipped
  (c) R_c == [V_min - V_abs]^+ (current deficit, recoverable)
  (d) ledger contains R_c_cum and still closes
  (e) risk_w == 1 where w <= 0; risk_b follows d_b + y < m_s
"""
import numpy as np

from sim.model import Simulator
from sim.params import Scenario
from sim.units import V_abs_of_y, deficit

from .helpers import P, cfg, simulate


def test_t11_floor_and_deficit_counter():
    params = P(rho_e=12.0)
    scen = Scenario("base", params)
    run = cfg(bc="zeroflux", t_end=8.0)
    res = simulate(params, scen, run)
    y = res.y_end
    sim = Simulator(params, scen, run)
    V_abs = V_abs_of_y(y, sim.V_ref, sim.H)
    V_min = sim.V_min
    V_book = np.maximum(V_abs, V_min)
    R_c = deficit(y, V_min, sim.V_ref, sim.H)
    rows = res.ledger.rows

    assert y.min() < -20.0, f"y must be allowed below -w0 (got {y.min():.2f})"
    assert (V_book - V_min).min() > -1e-9, "reported V fell below V_min"
    assert np.allclose(R_c, np.maximum(V_min - V_abs, 0.0))
    rc_sum = float(R_c.sum() * res.grid.dx)
    print(f"T11: y_min={y.min():.2f} V_book_min={V_book.min():.1f} "
          f"R_c={rc_sum:.4e} ledger R_c_cum={rows[-1]['R_c_cum']:.4e} "
          f"residual_rel={rows[-1]['residual_rel']:.2e}")
    assert abs(rows[-1]["R_c_cum"] - rc_sum) / rc_sum < 1e-12
    assert "R_c_cum" in rows[-1] and "D_max_cum" in rows[-1]
    assert rows[-1]["D_max_cum"] >= rows[-1]["R_c_cum"] - 1e-9
    assert abs(rows[-1]["residual_rel"]) < 1e-6

    # (e) risk indicators are computed from formulas, not forced
    m = res.metrics
    w_eff = np.maximum(sim.w0 + y, 0.0)
    risk_w = w_eff < float(params["w_mgmt"])
    risk_b = (float(params["d_bldg"]) + y) < float(params["m_safe"])
    assert np.array_equal(risk_w, sim.metrics.risk(y)[0])
    assert np.array_equal(risk_b, sim.metrics.risk(y)[1])
    assert risk_w[w_eff <= 0].all(), "risk_w must be 1 on exhausted cells"
    assert not risk_b[res.grid.central][y[res.grid.central] > -20.0].any(), \
        "risk_b must not be forced to 1 on exhausted cells (needs y < -20 m)"
