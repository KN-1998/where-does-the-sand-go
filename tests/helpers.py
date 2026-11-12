# -*- coding: utf-8 -*-
"""Shared test helpers.

All tests exercise the production path (``Simulator.run_loop``), not a private
copy of the numerics.  Initial states different from the production one
(``y=0``) must be passed through the constructor (``y0``/``O0``) so that the
ledger's incremental baseline is correct.
"""
from __future__ import annotations

from dataclasses import replace
from typing import Any, Dict, Iterable, Optional, Sequence

import numpy as np

from sim.model import SimResult, Simulator, run_model
from sim.params import Params, RunConfig, Scenario, load_params
from sim.placements import make_strategy
from sim.storms import EventTable, StormEvent

P0 = load_params()

BASE_OVERRIDES = {
    "rho_e": 0.0,
    "rho_e_hotspot_amp": 0.0,
    "u_drift": 0.0,
    "lambda_s": 0.0,
    "D_diff": 3.0e5,
}


def P(**over) -> Params:
    o = dict(BASE_OVERRIDES)
    o.update(over)
    return P0.clone_with(o)


def cfg(**over) -> RunConfig:
    kw = dict(scenario="base", strategy="none", bc="open", seed=1,
              t_end=5.0, dx=25.0, dt=0.02)
    kw.update(over)
    return RunConfig(**kw)


def simulate(params: Params, scenario: Scenario, run: RunConfig,
             y0: Optional[np.ndarray] = None, O0: Optional[np.ndarray] = None,
             events: Optional[Iterable[StormEvent]] = None,
             placements: Optional[Sequence[Dict[str, Any]]] = None,
             collect: bool = True) -> SimResult:
    sim = Simulator(params, scenario, run, y0=y0, O0=O0,
                    store_fields=collect)
    strat = make_strategy(params, run, sim.budget, placements=placements)
    table = EventTable(events=list(events or []))
    return sim.run_loop(run.t_end, events=table, strategy=strat, collect=collect)


def mass(ledger_rows, key: str, i: int = -1) -> float:
    return float(ledger_rows[i][key])
