# -*- coding: utf-8 -*-
"""T6 (single-event recovery) and T10 (event lands on a step boundary / mid-step / T).

T6 reference: recovery fraction = k/(k+lambda) = 0.667/0.767 = 0.8696.
"""
import numpy as np

from sim.model import Simulator
from sim.placements import make_strategy
from sim.params import Scenario
from sim.storms import EventTable, StormEvent

from .helpers import P, cfg, simulate


def test_t6_single_event_recovery():
    params = P()
    scen = Scenario("base", params)
    run = cfg(bc="open", t_end=30.0)
    res = simulate(params, scen, run, events=[StormEvent(t=1.0, dy_pot=20.0)])
    rows = res.ledger.rows
    ratio = rows[-1]["recovery_cum"] / rows[-1]["storm_injected_cum"]
    expected = float(params["k_rec"]) / (float(params["k_rec"]) + float(params["lam_off"]))
    o_end = float(np.abs(res.O_end).max())
    print(f"T6: recovery/injected={ratio:.6f} expected={expected:.6f} "
          f"max|O_end|={o_end:.2e}")
    assert abs(ratio - expected) < 1e-3, (ratio, expected)
    assert o_end < 1e-6, f"O did not decay to zero: {o_end:.2e}"
    assert abs(rows[-1]["residual_rel"]) < 1e-6


def test_t10_event_on_boundary_midstep_and_end():
    """Event at a dt multiple, in the middle of a step, and exactly at T."""
    params = P()
    scen = Scenario("base", params)
    w0 = np.array(Simulator(params, scen, cfg()).w0)
    f = 1.0 - np.exp(-w0 / 20.0)
    dy = np.minimum(20.0 * f, w0)
    expected = float((10.0 * dy * 25.0).sum())
    for t_event in (1.00, 1.01, 5.0):
        run = cfg(bc="open", t_end=5.0)
        sim = Simulator(params, scen, run, store_fields=False)
        res = sim.run_loop(5.0, events=EventTable([StormEvent(t=t_event, dy_pot=20.0)]),
                           strategy=make_strategy(params, run, sim.budget), collect=True)
        rows = res.ledger.rows
        inj = float(rows[-1]["storm_injected_cum"])
        rel = abs(inj - expected) / expected
        print(f"T10: t_event={t_event:.2f} n={res.n_events_applied} "
              f"injected={inj:.3f} expected={expected:.3f} rel={rel:.2e} "
              f"closure={rows[-1]['residual_rel']:.2e}")
        assert res.n_events_applied == 1, f"event applied {res.n_events_applied} times"
        assert rel < 1e-12, rel
        assert abs(rows[-1]["residual_rel"]) < 1e-6
    # the event column must record exactly one row
    assert len(res.events) == 1 and res.events[0]["t"] == 5.0
    assert len(res.events[0]) >= 8
