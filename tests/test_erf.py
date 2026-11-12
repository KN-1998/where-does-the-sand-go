# -*- coding: utf-8 -*-
"""T2 (erf convergence of the production scheme) and T3(b') (open boundary vs erf).

T2 protocol (CODER_SPEC §5): smooth Gaussian sigma=200 m, backward Euler with
dt proportional to dx -> expected L2 error ratio 1.8-2.2.  The step initial
condition is used only for the L_inf diagnostic (its error does not converge and
is not used to judge the order).
"""
import numpy as np
from math import erf

from sim.model import Simulator

from .helpers import P, cfg, simulate


def test_t2_be_convergence():
    params = P()
    from sim.params import Scenario
    scen = Scenario("base", params)
    errors = []
    for dx in (100.0, 50.0, 25.0):
        dt = 0.08 * dx / 100.0  # dt ∝ dx (BE first-order in time)
        run = cfg(bc="open", t_end=0.4, dx=dx, dt=dt, Lb=4500.0)
        g = Simulator(params, scen, run).grid
        y0 = np.exp(-g.x ** 2 / (2 * 200.0 ** 2))
        res = simulate(params, scen, run, y0=y0)
        t = float(res.t[-1])
        s2 = 200.0 ** 2 + 2 * 3.0e5 * t
        exact = np.sqrt(200.0 ** 2 / s2) * np.exp(-g.x ** 2 / (2 * s2))
        errors.append(float(np.sqrt(np.mean((res.y_end - exact) ** 2))))
        assert np.all(np.isfinite(res.y_end))
        assert res.y_end.min() > -1e-12, "smooth diffusion must stay non-negative"
    r1 = errors[0] / errors[1]
    r2 = errors[1] / errors[2]
    print(f"T2: L2 errors={['%.3e' % e for e in errors]} ratios={r1:.2f}, {r2:.2f}")
    assert 1.8 <= r1 <= 2.2, f"BE+dt~dx ratio {r1:.2f} outside [1.8, 2.2]"
    assert 1.8 <= r2 <= 2.2, f"BE+dt~dx ratio {r2:.2f} outside [1.8, 2.2]"


def test_t3bp_open_boundary_vs_erf():
    """T3(b'): large domain, open boundary, compare with the erf solution."""
    params = P()
    from sim.params import Scenario
    scen = Scenario("base", params)
    run = cfg(bc="open", t_end=1.0, Lb=10000.0)
    g = Simulator(params, scen, run).grid
    y0 = np.clip((500.0 - np.abs(g.x)) / g.dx + 0.5, 0.0, 1.0) * 100.0
    res = simulate(params, scen, run, y0=y0)
    s = 2.0 * np.sqrt(3.0e5 * 1.0)
    _erf = np.vectorize(erf)
    exact = 0.5 * 100.0 * (_erf((g.x + 500.0) / s) - _erf((g.x - 500.0) / s))
    l2 = float(np.sqrt(np.mean((res.y_end - exact) ** 2)) / 100.0)
    print(f"T3(b'): L2 relative error = {l2:.3e}")
    assert l2 < 2e-3, l2
