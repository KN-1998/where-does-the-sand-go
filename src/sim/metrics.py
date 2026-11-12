# -*- coding: utf-8 -*-
"""Risk mapping, spatial aggregation and duration metrics (MODEL_SPEC §6.3).

All duration / exposure / failure-fraction metrics are computed on the **central
5 km** only (CODER_SPEC §3.5); boundary fluxes and mass closure use the full 9 km
domain.  ``T_first_fail`` means "the first time the failed *length fraction*
reaches ``f_thr``", never ``min_x`` (the hotspot is initially below the design
threshold, which would make the metric degenerate to zero).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional

import numpy as np

from .units import w_eff_of_y


@dataclass
class Metrics:
    w0: np.ndarray
    w_mgmt: float
    d_b: float
    m_s: float
    f_thr: float
    L_central: float
    t_end: float
    central: np.ndarray

    # accumulators
    f_w0: float = 0.0
    f_b0: float = 0.0
    E_w: float = 0.0
    E_b: float = 0.0
    safe_w: float = 0.0
    safe_b: float = 0.0
    t_first_w: Optional[float] = None
    t_first_b: Optional[float] = None
    t_first_any_w: Optional[float] = None   # diagnostic only, never sorted on
    t_first_any_b: Optional[float] = None
    w_end_min: float = np.nan
    w_end_mean: float = np.nan
    w_min_ever: float = np.inf
    exhausted_frac: float = np.nan
    _last_t: float = 0.0
    _last_f_w: float = 0.0
    _last_f_b: float = 0.0
    _started: bool = False
    w0_min: float = 0.0
    w0_mean: float = 0.0
    _recovery_times: List[float] = field(default_factory=list)
    _recovery_censored: int = 0
    _pending: Dict[int, float] = field(default_factory=dict)
    _risk_b_prev: Optional[np.ndarray] = None
    _f_hist: List[tuple] = field(default_factory=list)

    def __post_init__(self) -> None:
        self.w0_min = float(self.w0[self.central].min())
        self.w0_mean = float(self.w0[self.central].mean())

    # -- risk fields -----------------------------------------------------
    def risk(self, y: np.ndarray):
        w_eff = w_eff_of_y(y, self.w0)
        risk_w = w_eff < self.w_mgmt
        risk_b = (self.d_b + y) < self.m_s
        return risk_w, risk_b

    def _measure_fraction(self, field: np.ndarray, threshold: float) -> float:
        """Length fraction ``{field < threshold}`` on the central corridor.

        The contract defines ``f_c(t) = (1/L) ∫ risk_c dx``.  Counting whole cells
        gives a first-order estimate whose granularity is one cell (1 % at
        dx=50 m), which makes a threshold-crossing time jump by a full cell.
        Here the indicator is integrated with a piecewise-linear reconstruction
        between neighbouring cell centres (boundary half-cells use the centre
        value), i.e. a second-order quadrature of the same integral.
        """
        wc = np.asarray(field[self.central], dtype=float)
        below = (wc < threshold).astype(float)
        d = np.diff(wc)
        with np.errstate(divide="ignore", invalid="ignore"):
            u = (threshold - wc[:-1]) / d
        frac = np.where(d > 0.0, np.clip(u, 0.0, 1.0),
                        1.0 - np.clip(u, 0.0, 1.0))
        frac = np.where(np.abs(d) > 0.0, frac, below[:-1])
        n = wc.size
        return float((0.5 * below[0] + frac.sum() + 0.5 * below[-1]) / n)

    def fractions(self, y: np.ndarray):
        w_eff = w_eff_of_y(y, self.w0)
        f_w = self._measure_fraction(w_eff, self.w_mgmt)
        f_b = self._measure_fraction(self.d_b + y, self.m_s)
        return f_w, f_b

    # -- integration -----------------------------------------------------
    def observe(self, t: float, y: np.ndarray) -> None:
        f_w, f_b = self.fractions(y)
        prev_t = self._last_t
        prev_fw, prev_fb = self._last_f_w, self._last_f_b
        if not self._started:
            self.f_w0, self.f_b0 = f_w, f_b
            self._started = True
            self._last_t = float(t)
            self._last_f_w, self._last_f_b = f_w, f_b
            _, rb0 = self.risk(y)
            self._risk_b_prev = rb0.copy()  # so the first event can register cells
            self._f_hist.append((float(t), f_w, f_b))
            self._update_first(t, f_w, f_b, y, prev_t, prev_fw, prev_fb)
            self._update_recovery(t, y)
            return
        dt = float(t) - self._last_t
        if dt > 0.0:
            self.E_w += f_w * self.L_central * dt
            self.E_b += f_b * self.L_central * dt
            self.safe_w += (1.0 - f_w) * dt
            self.safe_b += (1.0 - f_b) * dt
        self._last_t = float(t)
        self._last_f_w, self._last_f_b = f_w, f_b
        self._f_hist.append((float(t), f_w, f_b))
        self._update_first(t, f_w, f_b, y, prev_t, prev_fw, prev_fb)
        self._update_recovery(t, y)

    def _update_first(self, t: float, f_w: float, f_b: float, y: np.ndarray,
                      prev_t: float, prev_fw: float, prev_fb: float) -> None:
        # linear interpolation between the last safe and the first failing step
        # removes the dt-sized quantisation of a threshold-crossing time
        if self.t_first_w is None and f_w >= self.f_thr:
            self.t_first_w = self._crossing_time(t, f_w, prev_t, prev_fw)
        if self.t_first_b is None and f_b >= self.f_thr:
            self.t_first_b = self._crossing_time(t, f_b, prev_t, prev_fb)
        rw, rb = self.risk(y)
        c = self.central
        if self.t_first_any_w is None and rw[c].any():
            self.t_first_any_w = float(t)
        if self.t_first_any_b is None and rb[c].any():
            self.t_first_any_b = float(t)

    def _crossing_time(self, t: float, f: float, prev_t: float, f_prev: float) -> float:
        if f <= f_prev or f < self.f_thr or f_prev >= self.f_thr:
            return float(t)
        w = (self.f_thr - f_prev) / (f - f_prev)
        w = min(max(w, 0.0), 1.0)
        return float(prev_t + w * (t - prev_t))

    # -- recovery after events -------------------------------------------
    def on_event(self, t: float, y: np.ndarray) -> None:
        """Register cells that the event pushed into building risk."""
        rw, rb = self.risk(y)
        if self._risk_b_prev is None:
            self._risk_b_prev = rb
            return
        newly = np.flatnonzero(rb & ~self._risk_b_prev & self.central)
        # leftovers from the previous event are censored by the next event
        if self._pending:
            self._recovery_censored += len(self._pending)
            self._pending.clear()
        for i in newly:
            self._pending[int(i)] = float(t)
        self._risk_b_prev = rb.copy()

    def _update_recovery(self, t: float, y: np.ndarray) -> None:
        if not self._pending:
            return
        _, rb = self.risk(y)
        done = [i for i in self._pending if not rb[i]]
        for i in done:
            self._recovery_times.append(float(t) - self._pending.pop(i))

    def finalize(self, y: np.ndarray) -> Dict[str, object]:
        w = self.w0 + y
        c = self.central
        self.w_end_min = float(w[c].min())
        self.w_end_mean = float(w[c].mean())
        self.exhausted_frac = float((w_eff_of_y(y, self.w0)[c] <= 0.0).mean())
        self._recovery_censored += len(self._pending)
        self._pending.clear()
        rec = np.asarray(self._recovery_times, dtype=float)
        n_rec = int(rec.size + self._recovery_censored)
        t_rec = {
            "median": float(np.median(rec)) if rec.size else None,
            "n": n_rec,
            "censored": int(self._recovery_censored),
        }
        return {
            "f_w0": self.f_w0,
            "f_b0": self.f_b0,
            "w0_min": self.w0_min,
            "w0_mean": self.w0_mean,
            "E_w": self.E_w,
            "E_b": self.E_b,
            "T_safe_cum_w": self.safe_w,
            "T_safe_cum_b": self.safe_b,
            "T_first_fail_w": _duration(self.t_first_w, self.t_end),
            "T_first_fail_b": _duration(self.t_first_b, self.t_end),
            "T_recovery": t_rec,
            "T_first_any_w": _duration(self.t_first_any_w, self.t_end),
            "T_first_any_b": _duration(self.t_first_any_b, self.t_end),
            "w_end_min": self.w_end_min,
            "w_end_mean": self.w_end_mean,
            "w_min_ever": self.w_min_ever,
            "exhausted_frac": self.exhausted_frac,
            "f_w_hist": self._f_hist,
        }

    def track_w_min(self, y: np.ndarray) -> None:
        w = (self.w0 + y)[self.central]
        self.w_min_ever = min(self.w_min_ever, float(w.min()))


def _duration(value: Optional[float], t_end: float) -> Dict[str, object]:
    """Right-censored duration record (§4.2b): censored => value is null."""
    if value is None:
        return {"value": None, "censored": True}
    return {"value": float(value), "censored": False}


def quantiles(values, qs=(0.1, 0.5, 0.9)) -> Dict[str, Optional[float]]:
    arr = np.asarray([v for v in values if v is not None], dtype=float)
    if arr.size == 0:
        return {f"P{int(q*100)}": None for q in qs}
    return {f"P{int(q*100)}": float(np.quantile(arr, q)) for q in qs}
