# -*- coding: utf-8 -*-
"""Storm event sampling (CODER_SPEC §2.4b, §3.5).

The event table is generated **once per (scenario, seed)** and replayed by the
baseline, the placement variants and every strategy, so that paired differences
isolate the nourishment effect instead of a different storm sequence.

RNG discipline (§3.5): arrival times, magnitudes and footprint centres use three
independent streams; sharing one stream would make "one extra event" change every
later magnitude.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Sequence

import numpy as np

from .params import Scenario


@dataclass
class StormEvent:
    """One erosive event.

    ``dy_pot`` is the wide-beach potential retreat (m).  For forced events that
    are defined by their *actual* retreat (S2, T10), ``forced_actual`` is set and
    the per-cell magnitude becomes ``min(forced_actual, w_eff)``.
    """

    t: float
    dy_pot: float
    forced_actual: Optional[float] = None
    xk: float = 0.0
    sigma_e: float = 2000.0
    tag: str = "poisson"

    def as_row(self) -> Dict[str, Any]:
        return {
            "t": self.t,
            "dy_pot": self.dy_pot,
            "dy_forced_actual": self.forced_actual,
            "xk": self.xk,
            "sigma_e": self.sigma_e,
            "tag": self.tag,
        }


@dataclass
class EventTable:
    events: List[StormEvent] = field(default_factory=list)
    meta: Dict[str, Any] = field(default_factory=dict)

    def times(self) -> np.ndarray:
        return np.array([e.t for e in self.events], dtype=float)

    def __len__(self) -> int:
        return len(self.events)

    def __iter__(self):
        return iter(self.events)


def _streams(seed: int):
    ss = np.random.SeedSequence([int(seed), 20271111])
    children = ss.spawn(4)
    return (np.random.default_rng(children[0]),  # arrivals
            np.random.default_rng(children[1]),  # magnitudes
            np.random.default_rng(children[2]),  # footprint centres
            np.random.default_rng(children[3]))  # monitoring noise


def sample_arrivals(scenario: Scenario, rng: np.random.Generator,
                    t_start: float, t_end: float,
                    lam_max: Optional[float] = None) -> List[float]:
    """Thinning sampler for a (possibly non-homogeneous) Poisson process."""
    if t_end <= t_start:
        return []
    if lam_max is None:
        lam_max = max(scenario.lam_s(t_start), scenario.lam_s(t_end), 0.0)
    if lam_max <= 0.0:
        return []
    out: List[float] = []
    t = t_start
    while True:
        t += rng.exponential(1.0 / lam_max)
        if t >= t_end:
            break
        if rng.random() < scenario.lam_s(t) / lam_max:
            out.append(float(t))
    return out


def build_event_table(scenario: Scenario, seed: int, t_end: float, Lb: float,
                      phi_shape: str = "uniform",
                      forced_events: Optional[Sequence[Dict[str, Any]]] = None,
                      t_start: float = 0.0) -> EventTable:
    rng_arr, rng_mag, rng_pos, _ = _streams(seed)
    # advance the arrival stream to t_start for forecast windows
    lam_max = max(scenario.lam0, scenario.lam1)
    times = sample_arrivals(scenario, rng_arr, t_start, t_end, lam_max)

    events: List[StormEvent] = []
    for t in times:
        z = rng_mag.standard_normal()
        dy_pot = scenario.dy_ref(t) * float(np.exp(scenario.sigma_ln * z))
        xk = float(rng_pos.uniform(-Lb, Lb)) if phi_shape == "gaussian" else 0.0
        events.append(StormEvent(t=float(t), dy_pot=float(dy_pot), xk=xk,
                                 sigma_e=2000.0, tag="poisson"))

    for spec in (forced_events or []):
        t = float(spec["t"])
        if t < t_start or t > t_end + 1e-12:
            continue
        dy = spec.get("dy_actual", spec.get("dy"))
        if dy is None:
            raise KeyError("forced event needs dy_actual (or dy)")
        mode = spec.get("mode", "actual")
        # drop Poisson events that would coincide with the forced one
        events = [e for e in events if abs(e.t - t) > 0.05]
        events.append(StormEvent(
            t=t,
            dy_pot=float(spec.get("dy_pot", dy)),
            forced_actual=float(dy) if mode == "actual" else None,
            xk=float(spec.get("xk", 0.0)),
            sigma_e=float(spec.get("sigma_e", 2000.0)),
            tag="forced",
        ))

    events.sort(key=lambda e: e.t)
    meta = {
        "seed": int(seed),
        "scenario": scenario.name,
        "t_start": float(t_start),
        "t_end": float(t_end),
        "phi_shape": phi_shape,
        "n_events": len(events),
        "sigma_ln": scenario.sigma_ln,
        "lambda_s_0": scenario.lam0,
        "lambda_s_end": scenario.lam1,
        "dy_ref_0": scenario.dy0,
        "dy_ref_end": scenario.dy1,
        "streams": {"arrival": "seed:20271111:0", "magnitude": "seed:20271111:1",
                    "position": "seed:20271111:2"},
    }
    return EventTable(events=events, meta=meta)


def build_timing_table(scenario: Scenario, seed: int, times: Sequence[float],
                       dy_pot: Optional[Sequence[float]] = None,
                       xk: float = 0.0) -> EventTable:
    """Fixed-timing table used by E3 (storm *timing* contrast, same magnitudes)."""
    rng_arr, rng_mag, _, _ = _streams(seed)
    mags = list(dy_pot) if dy_pot is not None else [
        float(scenario.dy_ref(t) * np.exp(scenario.sigma_ln * rng_mag.standard_normal()))
        for t in times
    ]
    events = [StormEvent(t=float(t), dy_pot=float(d), xk=xk)
              for t, d in zip(times, mags)]
    events.sort(key=lambda e: e.t)
    return EventTable(events=events, meta={
        "seed": int(seed), "scenario": scenario.name, "mode": "timing",
        "n_events": len(events), "times": list(times),
    })


def monitoring_rng(seed: int) -> np.random.Generator:
    """Fourth stream: quarterly monitoring noise (never mixed with storm draws)."""
    return _streams(seed)[3]
