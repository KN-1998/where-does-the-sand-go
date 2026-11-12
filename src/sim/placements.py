# -*- coding: utf-8 -*-
"""Nourishment placements, budget/sand-source constraints and strategies.

Two families, deliberately kept apart (CODER_SPEC §2.5c):

* ``placement`` (Q2 / E1): uniform | hotspot | multi -- same total volume.
* ``strategy``  (Q5 / E4): once | repeat | targeted | adaptive.

Feasible volume per project is the ordered ``min`` of CODER_SPEC §2.5b::

    min(V_desired, V_event_max, V15_total - V_used, S_cap - S_used,
        (C_max - cost_used - c0) / c1_eff)

with ``c1_eff = (c1 | c1_marginal) + (c_transport if external else 0)``.
A project that would place less than ``MIN_MEANINGFUL`` is not silently executed:
it is recorded with a ``skipped_reason``.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

import numpy as np

MIN_MEANINGFUL = 1.0e5  # m^3

PLACEMENT_GEOMETRY = {
    "uniform": {"xc": 0.0, "ell": 5000.0},
    "hotspot": {"xc": 0.0, "ell": 1000.0},
    "multi": {"xc": None, "ell": 500.0},  # centres filled in below
}
MULTI_CENTRES = (-1800.0, -900.0, 0.0, 900.0, 1800.0)


@dataclass
class Budget:
    V15_total: float
    V_event_max: float
    S_borrow_total: float
    C_max: float
    c0: float
    c1: float
    c1_marginal: float
    c_transport: float
    cost_model: str = "all_in"
    supply: str = "local"
    a_borrow: float = 1.0
    V_used: float = 0.0
    S_used: float = 0.0
    cost_used: float = 0.0
    n_projects: int = 0

    @property
    def c_unit(self) -> float:
        return self.c1 if self.cost_model == "all_in" else self.c1_marginal

    @property
    def c1_eff(self) -> float:
        return self.c_unit + (self.c_transport if self.supply == "external" else 0.0)

    @property
    def S_cap(self) -> float:
        return self.V15_total if self.supply == "external" else self.S_borrow_total * self.a_borrow

    def planned_total(self, n: int) -> float:
        """V_tot(N) from SCENARIOS_STRATEGIES §3."""
        budget_cap = (self.C_max - n * self.c0) / self.c1_eff
        return max(0.0, min(self.V15_total, n * self.V_event_max, self.S_cap, budget_cap))

    def feasible(self, desired: float) -> float:
        remaining_cost = self.C_max - self.cost_used - self.c0
        caps = [desired, self.V_event_max, self.V15_total - self.V_used,
                self.S_cap - self.S_used, remaining_cost / self.c1_eff]
        return max(0.0, float(min(caps)))

    def commit(self, volume: float) -> float:
        cost = self.c0 + self.c1_eff * volume
        self.V_used += volume
        self.S_used += volume
        self.cost_used += cost
        self.n_projects += 1
        return cost

    def as_dict(self) -> Dict[str, Any]:
        return {
            "c1_eff": self.c1_eff,
            "S_cap": self.S_cap,
            "V_used": self.V_used,
            "S_used": self.S_used,
            "cost_used": self.cost_used,
            "n_projects": self.n_projects,
        }


@dataclass
class PlannedPlacement:
    t_plan: float
    volume: float
    xc: Optional[float]
    ell: float
    tag: str = "placement"
    budgeted: bool = True
    applied: bool = False
    t_actual: Optional[float] = None
    v_actual: Optional[float] = None
    skipped_reason: Optional[str] = None


def split_volume(volume: float, shape: str) -> List[tuple[float, float]]:
    """Return ``[(xc, share_of_volume), ...]`` for a placement family."""
    if shape == "uniform":
        return [(0.0, volume)]
    if shape == "hotspot":
        return [(0.0, volume)]
    if shape == "multi":
        share = volume / len(MULTI_CENTRES)
        return [(c, share) for c in MULTI_CENTRES]
    raise KeyError(f"unknown placement shape {shape!r}")


def make_plan(t_plan: float, volume: float, shape: str, tag: str,
              budgeted: bool = True) -> List[PlannedPlacement]:
    out = []
    for xc, share in split_volume(volume, shape):
        ell = PLACEMENT_GEOMETRY[shape]["ell"]
        out.append(PlannedPlacement(t_plan=t_plan, volume=share, xc=xc, ell=ell,
                                    tag=tag, budgeted=budgeted))
    return out


# ---------------------------------------------------------------------------
# Strategies
# ---------------------------------------------------------------------------
class Strategy:
    """Base class.  ``initial`` runs before t=0; ``on_time`` runs after each step."""

    name = "none"

    def __init__(self, params, run, budget: Budget):
        self.p = params
        self.run = run
        self.budget = budget
        self.delay = float(params["permit_delay"]) + float(params["tau_build"])
        self.last_place_t = 0.0
        self.f_at_last_place: Optional[float] = None
        self.trigger_log: List[Dict[str, Any]] = []

    def initial(self, model) -> None:  # pragma: no cover - default no-op
        return None

    def on_time(self, t: float, model) -> None:  # pragma: no cover - default no-op
        return None


class NoStrategy(Strategy):
    name = "none"


class ScriptedStrategy(Strategy):
    """Config-specified idealised placements (E1 / T5 / T10)."""

    name = "scripted"

    def __init__(self, params, run, budget, placements: List[Dict[str, Any]]):
        super().__init__(params, run, budget)
        self.specs = placements

    def initial(self, model) -> None:
        for spec in self.specs:
            t = float(spec.get("t", 0.0))
            vol = float(spec["volume"])
            xc = float(spec.get("xc", 0.0))
            ell = float(spec.get("len", spec.get("ell", 5000.0)))
            tag = str(spec.get("tag", "scripted"))
            model.add_placement(PlannedPlacement(t_plan=t, volume=vol, xc=xc,
                                                 ell=ell, tag=tag,
                                                 budgeted=bool(spec.get("budgeted", False))))


class OnceStrategy(Strategy):
    name = "once"

    def initial(self, model) -> None:
        for pl in make_plan(self.delay, float(self.p["V_event_max"]), "uniform",
                            "once", budgeted=True):
            model.add_placement(pl)


class RepeatStrategy(Strategy):
    name = "repeat"

    def initial(self, model) -> None:
        total = self.budget.planned_total(3)
        share = total / 3.0
        for k in range(3):
            t = self.delay + 5.0 * k
            for pl in make_plan(t, share, "uniform", f"repeat_{k+1}", budgeted=True):
                model.add_placement(pl)


class _TriggeredStrategy(Strategy):
    """Shared trigger/cooldown machinery for ``targeted`` and ``adaptive``."""

    max_projects = 4

    def __init__(self, params, run, budget):
        super().__init__(params, run, budget)
        self.delta_f = float(params["delta_f_trig"])
        self.sigma_m = float(params["sigma_m"])
        self.m_s = float(params["m_s"])
        self.d_b = float(params["d_b"])
        self.cooldown = self.delay + float(params["cooldown_extra"])

    def _measure(self, model, t: float):
        rng = model.monitor_rng
        eps = rng.normal(0.0, self.sigma_m, size=model.grid.nx)
        w_hat = model.w0 + model.y + eps
        f_w_hat = float((w_hat[model.grid.central] < float(self.p["w_mgmt"])).mean())
        if self.f_at_last_place is not None and f_w_hat - self.f_at_last_place >= self.delta_f:
            return f_w_hat, True, "delta_f"
        r_hat = self.d_b + model.y + eps
        if float((r_hat[model.grid.central] < self.m_s + 2.0).any()):
            return f_w_hat, True, "building_hard"
        return f_w_hat, False, ""

    def _should_check(self, t: float, model) -> bool:
        quarter = model.n_quarters_done
        desired = int(np.floor(t / 0.25 + 1e-9))
        if desired <= quarter:
            return False
        model.n_quarters_done = desired
        return True


class TargetedStrategy(_TriggeredStrategy):
    """Hotspot (1 km) placement at the largest risk-weighted deficit.

    First project is approved after ``tau_permit + tau_build`` (as for every
    strategy); further projects are added when the state trigger fires, up to
    ``max_projects``.  It never looks at the *real* future storm table.
    """

    name = "targeted"

    def initial(self, model) -> None:
        f_w0, _ = model.metrics.fractions(model.y)
        self.f_at_last_place = f_w0
        # first project is planned immediately (permit delay applies)
        for pl in make_plan(self.delay, float(self.p["V_event_max"]), "hotspot",
                            "targeted_1", budgeted=True):
            model.add_placement(pl)

    def on_time(self, t: float, model) -> None:
        if not self._should_check(t, model):
            return
        f_hat, fire, why = self._measure(model, t)
        if not fire:
            return
        if t - self.last_place_t < self.cooldown:
            self.trigger_log.append({"t": t, "why": why, "action": "cooldown"})
            return
        if model.budget.n_projects >= self.max_projects:
            return
        xc = model.target_xc_hotspot()
        for pl in make_plan(t + self.delay, float(self.p["V_event_max"]), "hotspot",
                            f"targeted_{model.budget.n_projects + 1}", budgeted=True):
            pl.xc = xc
            pl.ell = 1000.0
            model.add_placement(pl)
        self.last_place_t = t
        self.f_at_last_place = f_hat
        self.trigger_log.append({"t": t, "why": why, "action": "schedule",
                                 "xc": xc, "at": t + self.delay})


class AdaptiveStrategy(_TriggeredStrategy):
    """D8 state trigger + 5-year rolling forecast, no knowledge of future storms."""

    name = "adaptive"

    def initial(self, model) -> None:
        # t=0: initial assessment only -- no placement (A5)
        f_w0, f_b0 = model.metrics.fractions(model.y)
        self.f_at_last_place = f_w0
        self.trigger_log.append({"t": 0.0, "why": "initial_assessment",
                                 "f_w0": f_w0, "f_b0": f_b0, "action": "none"})

    def on_time(self, t: float, model) -> None:
        if not self._should_check(t, model):
            return
        f_hat, fire, why = self._measure(model, t)
        if not fire:
            return
        if t - self.last_place_t < self.cooldown:
            self.trigger_log.append({"t": t, "why": why, "action": "cooldown"})
            return
        if model.budget.n_projects >= self.max_projects:
            return
        plan = model.forecast_choose(t, horizon=5.0)
        self.trigger_log.append({"t": t, "why": why, **plan["log"]})
        if plan["retreat"]:
            return
        pl = PlannedPlacement(t_plan=t + self.delay, volume=plan["volume"],
                              xc=plan["xc"], ell=1000.0,
                              tag=f"adaptive_{model.budget.n_projects + 1}",
                              budgeted=True)
        model.add_placement(pl)
        self.last_place_t = t
        self.f_at_last_place = f_hat


def make_strategy(params, run, budget: Budget, placements=None) -> Strategy:
    if placements:
        return ScriptedStrategy(params, run, budget, placements)
    name = run.strategy
    if name in ("none", None):
        return NoStrategy(params, run, budget)
    if name == "once":
        return OnceStrategy(params, run, budget)
    if name == "repeat":
        return RepeatStrategy(params, run, budget)
    if name == "targeted":
        return TargetedStrategy(params, run, budget)
    if name == "adaptive":
        return AdaptiveStrategy(params, run, budget)
    raise KeyError(f"unknown strategy {name!r}")
