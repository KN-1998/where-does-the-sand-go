# -*- coding: utf-8 -*-
"""Event-driven simulation core.

One continuous step (CODER_SPEC §2.3-§2.4)::

    O^{n+1} = O^n exp(-a h),                     a = k + lambda
    R_n     = k/a (O^n - O^{n+1} + S),           S = 0 inside a continuous step
    rhs     = y^n + R_n/H - rho_e h              (sources explicit)
    A y^{n+1} = rhs + const_bc                   (transport implicit, BE)

A storm is applied as a jump at a step boundary *after* the continuous step; a
nourishment at the same time is applied *after* the storm jump.  No storm sand is
ever put into the continuous-step source term (§2.4b ordering rule).
"""
from __future__ import annotations

from dataclasses import dataclass, field, replace
from typing import Any, Dict, List, Optional

import numpy as np

from .accounting import Ledger, closure
from .grid import Grid, Transport, rho_field, solve_tridiag, w0_field
from .metrics import Metrics
from .params import Params, RunConfig, Scenario
from .placements import (MIN_MEANINGFUL, AdaptiveStrategy, Budget, PlannedPlacement,
                         Strategy, make_strategy)
from .storms import EventTable, StormEvent, build_event_table, monitoring_rng
from .sums import Kahan
from .units import V_abs_of_y, V_min_field, deficit, w_eff_of_y


@dataclass
class SimResult:
    grid: Grid
    t: np.ndarray
    y: np.ndarray
    O: np.ndarray
    w0: np.ndarray
    y_end: np.ndarray
    O_end: np.ndarray
    ledger: Ledger
    events: List[Dict[str, Any]]
    metrics: Dict[str, Any]
    budget: Dict[str, Any]
    strategy_log: List[Dict[str, Any]]
    n_events_applied: int
    config: Dict[str, Any]
    params_md5: str
    scenario: Dict[str, Any]
    placements_applied: List[Dict[str, Any]]

    def summary(self) -> Dict[str, Any]:
        m = self.metrics
        return {
            "meta": {
                **self.config,
                "params_md5": self.params_md5,
                "scenario": self.scenario,
                "n_events_applied": self.n_events_applied,
            },
            "initial": {
                "f_w0": m["f_w0"],
                "f_b0": m["f_b0"],
                "w_min": m.get("w0_min"),
                "w_mean": m.get("w0_mean"),
            },
            "duration": {
                "T_first_fail_w": m["T_first_fail_w"],
                "T_first_fail_b": m["T_first_fail_b"],
                "T_safe_cum_w": m["T_safe_cum_w"],
                "T_safe_cum_b": m["T_safe_cum_b"],
                "T_recovery": m["T_recovery"],
            },
            "exposure": {"E_w": m["E_w"], "E_b": m["E_b"]},
            "mass": {
                "placed": self.ledger.rows[-1]["placed_cum"] if self.ledger.rows else 0.0,
                "flux_out": (self.ledger.rows[-1]["flux_outer_left_cum"]
                             + self.ledger.rows[-1]["flux_outer_right_cum"]) if self.ledger.rows else 0.0,
                "offshore": self.ledger.rows[-1]["offshore_loss_cum"] if self.ledger.rows else 0.0,
                "chronic": self.ledger.rows[-1]["chronic_loss_cum"] if self.ledger.rows else 0.0,
                "R_c": self.ledger.rows[-1]["R_c_cum"] if self.ledger.rows else 0.0,
                "residual_rel_max": self.ledger.max_abs_rel,
            },
            "cost": {
                "cost_used": self.budget["cost_used"],
                "n_projects": self.budget["n_projects"],
                "c0_star": None,
            },
            "state": {
                "w_end_min": m["w_end_min"],
                "w_end_mean": m["w_end_mean"],
                "exhausted_frac": m["exhausted_frac"],
            },
        }


class Simulator:
    """One realisation of the model on a fixed grid.

    ``y0``/``O0``/``t0`` allow the adaptive strategy to forecast from the current
    state without touching the live run.
    """

    def __init__(self, params: Params, scenario: Scenario, run: RunConfig,
                 grid: Optional[Grid] = None, y0: Optional[np.ndarray] = None,
                 O0: Optional[np.ndarray] = None, t0: float = 0.0,
                 store_fields: bool = True, ledger_on: bool = True,
                 label: str = ""):
        self.params = params
        self.scenario = scenario
        self.run = run
        self.grid = grid or Grid(run.Lb, run.dx)
        g = self.grid
        self.H = float(params["H_dep"])
        self.V_ref = float(params["V_ref"])
        self.w0 = w0_field(g.x, float(params["w0_far"]), float(params["w0_min"]),
                           float(params["sigma_w"]))
        self.rho_base = rho_field(g.x, float(params["rho_e"]),
                                  float(params["rho_e_hotspot_amp"]),
                                  float(params["sigma_h"]), float(params["x_h"]))
        self.V_min = V_min_field(self.w0, self.V_ref, self.H)
        self.y = np.zeros(g.nx) if y0 is None else np.array(y0, dtype=float)
        self.O = np.zeros(g.nx) if O0 is None else np.array(O0, dtype=float)
        self.t_start = float(t0)
        self.t = float(t0)
        self.store_fields = store_fields
        self.ledger_on = ledger_on
        self.label = label

        self.transport = Transport(g, float(params["u_drift"]), run.bc)
        self.k = float(params["k_rec"])
        self.lam = float(params["lam_off"])
        self.a = self.k + self.lam
        self.w_s = float(params["w_sat"])
        self.w_mgmt = float(params["w_mgmt"])
        self.d_b = float(params["d_bldg"])
        self.m_s = float(params["m_safe"])
        self.f_thr = float(params["f_thr"])
        self.dirichlet_yb = run.dirichlet_yb
        if self.dirichlet_yb is None:
            self.dirichlet_yb = -float(params["rho_e"]) * self.t

        self.metrics = Metrics(w0=self.w0, w_mgmt=self.w_mgmt, d_b=self.d_b,
                               m_s=self.m_s, f_thr=self.f_thr,
                               L_central=g.n_central * g.dx, t_end=run.t_end,
                               central=g.central)
        self.monitor_rng = monitoring_rng(run.seed)
        self.n_quarters_done = 0

        self.budget = Budget(
            V15_total=float(params["V15_total"]),
            V_event_max=float(params["V_event_max"]),
            S_borrow_total=float(params["S_borrow_total"]),
            C_max=float(params["C_max"]),
            c0=float(params["c0"]),
            c1=float(params["c1"]),
            c1_marginal=float(params["c1_marginal"]),
            c_transport=float(params["transport_cost_add"]),
            cost_model=run.cost_model,
            supply=run.supply,
            a_borrow=float(params["supply_availability"]),
        )

        self.pending: List[PlannedPlacement] = []
        self.events_rows: List[Dict[str, Any]] = []
        self.placements_applied: List[Dict[str, Any]] = []
        self.n_events_applied = 0
        self.ledger = Ledger()
        self._t_hist: List[float] = []
        self._y_hist: List[np.ndarray] = []
        self._O_hist: List[np.ndarray] = []

        # simple account accumulators (all m^3 / m^3); compensated sums keep the
        # 15-year closure at ~1e-13 instead of accumulating step rounding
        self.placed_cum = Kahan()
        self.flux_inner_left_cum = Kahan()
        self.flux_inner_right_cum = Kahan()
        self.flux_outer_left_cum = Kahan()
        self.flux_outer_right_cum = Kahan()
        self.offshore_cum = Kahan()
        self.chronic_cum = Kahan()
        self.offshore_central_cum = Kahan()
        self.chronic_central_cum = Kahan()
        self.storm_injected_cum = Kahan()
        self.recovery_cum = Kahan()
        self.q_limited_cum = Kahan()
        self.D_max = np.zeros(g.nx)
        self.D0 = float(deficit(self.y, self.V_min, self.V_ref, self.H).sum() * g.dx)
        # initial absolute stocks: ledger columns are increments w.r.t. these
        # (y0 = O0 = 0 in production, so this only matters for unit tests that
        # start from a non-zero bump -- T7)
        self.V0_domain = float((self.H * self.y).sum() * g.dx)
        self.O0_domain = float(self.O.sum() * g.dx)
        self.V0_central = float((self.H * self.y[g.central]).sum() * g.dx)
        self.O0_central = float(self.O[g.central].sum() * g.dx)

    # ------------------------------------------------------------------
    # placements
    # ------------------------------------------------------------------
    def add_placement(self, pl: PlannedPlacement) -> None:
        self.pending.append(pl)

    def _distribute(self, volume: float, xc: float, ell: float) -> np.ndarray:
        g = self.grid
        lo, hi = xc - ell / 2.0, xc + ell / 2.0
        overlap = np.clip(np.minimum(g.x + g.dx / 2.0, hi)
                          - np.maximum(g.x - g.dx / 2.0, lo), 0.0, None)
        if overlap.sum() <= 0.0:
            raise ValueError(f"placement at xc={xc} ell={ell} does not overlap the grid")
        weights = overlap / overlap.sum()
        dy = volume * weights / (self.H * g.dx)
        got = float((self.H * dy * g.dx).sum())
        if abs(got - volume) / volume > 1e-12:
            raise AssertionError(f"placement not conservative: {got} vs {volume}")
        return dy

    def _apply_placement(self, pl: PlannedPlacement, t: float) -> None:
        if pl.applied:
            return
        pl.applied = True
        pl.t_actual = float(t)
        if pl.budgeted:
            v = self.budget.feasible(pl.volume)
            if v < MIN_MEANINGFUL:
                pl.skipped_reason = "below_min_meaningful_or_exhausted"
                pl.v_actual = 0.0
                self.placements_applied.append({
                    "t": float(t), "tag": pl.tag, "xc": pl.xc, "ell": pl.ell,
                    "volume_design": float(pl.volume), "volume_actual": 0.0,
                    "skipped_reason": pl.skipped_reason,
                })
                return
            cost = self.budget.commit(v)
        else:
            v = float(pl.volume)
            cost = 0.0
        self.y += self._distribute(v, float(pl.xc), float(pl.ell))
        self.placed_cum.add(v)
        pl.v_actual = v
        self.placements_applied.append({
            "t": float(t), "tag": pl.tag, "xc": float(pl.xc), "ell": float(pl.ell),
            "volume_design": float(pl.volume), "volume_actual": float(v),
            "cost": float(cost), "skipped_reason": None,
        })

    def _apply_due_placements(self, t: float,
                              due: Optional[List[PlannedPlacement]] = None) -> None:
        items = self.pending if due is None else due
        for pl in list(items):
            if not pl.applied and pl.t_plan <= t + 1e-12:
                if pl.t_plan > self.run.t_end + 1e-12:
                    pl.applied = True
                    pl.skipped_reason = "skipped_due_to_window"
                    self.placements_applied.append({
                        "t": float(t), "tag": pl.tag, "xc": pl.xc, "ell": pl.ell,
                        "volume_design": float(pl.volume), "volume_actual": 0.0,
                        "skipped_reason": pl.skipped_reason,
                    })
                    continue
                self._apply_placement(pl, t)

    def planned_after_window(self) -> None:
        for pl in self.pending:
            if not pl.applied:
                pl.applied = True
                pl.skipped_reason = "skipped_due_to_window"
                self.placements_applied.append({
                    "t": None, "tag": pl.tag, "xc": pl.xc, "ell": pl.ell,
                    "volume_design": float(pl.volume), "volume_actual": 0.0,
                    "skipped_reason": pl.skipped_reason,
                })

    # ------------------------------------------------------------------
    # storms
    # ------------------------------------------------------------------
    def _apply_event(self, ev: StormEvent, t: float) -> None:
        g = self.grid
        w_raw = self.w0 + self.y
        w_eff = np.maximum(w_raw, 0.0)
        if ev.forced_actual is not None:
            dy = np.minimum(float(ev.forced_actual), w_eff)
        else:
            f = 1.0 - np.exp(-w_eff / self.w_s)
            dy = np.minimum(float(ev.dy_pot) * f, w_eff)
        if self.run.phi_shape == "gaussian":
            phi = np.exp(-(g.x - ev.xk) ** 2 / (2.0 * ev.sigma_e ** 2))
            phi = phi / phi.max()
        else:
            phi = np.ones(g.nx)
        dy = dy * phi
        self.y -= dy
        self.O += self.H * dy
        inj = float((self.H * dy * g.dx).sum())
        inj_central = float((self.H * dy[g.central] * g.dx).sum())
        self.storm_injected_cum.add(inj)
        self.n_events_applied += 1
        i_centre = int(np.argmin(np.abs(g.x - ev.xk)))
        self.events_rows.append({
            "t": float(t),
            "dy_pot": float(ev.dy_pot),
            "dy_forced_actual": (None if ev.forced_actual is None else float(ev.forced_actual)),
            "xk": float(ev.xk),
            "sigma_e": float(ev.sigma_e),
            "tag": ev.tag,
            "dy_peak": float(dy[i_centre]),
            "injected_central": inj_central,
            "injected_domain": inj,
            "n_exhausted": int((w_eff <= 0.0).sum()),
        })
        self.metrics.on_event(t, self.y)

    # ------------------------------------------------------------------
    # one continuous step
    # ------------------------------------------------------------------
    def _advance(self, h: float) -> None:
        g = self.grid
        t_mid = self.t + 0.5 * h
        D = float(self.params["D_diff"]) * self.scenario.D_factor(t_mid)
        rho = self.scenario.rho_scale(t_mid) * self.rho_base
        yb = float(self.dirichlet_yb) if self.dirichlet_yb is not None else 0.0
        if self.run.bc == "dirichlet":
            yb = -float(self.params["rho_e"]) * (self.t + h)
        y_prev = self.y
        O_prev = self.O

        O_new = O_prev * np.exp(-self.a * h)
        Rn = (self.k / self.a) * (O_prev - O_new)
        lamO = (self.lam / self.a) * (O_prev - O_new)
        rhs = y_prev + Rn / self.H - rho * h

        V_abs = V_abs_of_y(y_prev, self.V_ref, self.H)
        exhausted = V_abs <= self.V_min + 1e-12
        y_src = y_prev + Rn / self.H - rho * h  # source-only predictor
        sys_ = None
        y_new = y_prev
        for _ in range(4):
            sys_ = self.transport.assemble(h, y_prev, D, exhausted,
                                           yb_left=yb, yb_right=yb)
            y_new = solve_tridiag(sys_["lower"], sys_["main"], sys_["upper"],
                                  rhs + sys_["const"])
            newly = ((y_new < -self.w0 - 1e-12) & ~exhausted
                     & (y_src >= -self.w0 - 1e-12))
            if not newly.any():
                break
            exhausted = exhausted | newly

        F = self.transport.face_fluxes(y_new, D, sys_, yb_left=yb, yb_right=yb)
        self.q_limited_cum.add(self.transport.limited_volume(y_new, D, sys_, h, self.H))

        outflow_left = -float(F[0])
        outflow_right = float(F[-1])
        self.flux_outer_left_cum.add(self.H * outflow_left * h)
        self.flux_outer_right_cum.add(self.H * outflow_right * h)
        self.flux_inner_left_cum.add(self.H * (-float(F[g.j_central_left])) * h)
        self.flux_inner_right_cum.add(self.H * float(F[g.j_central_right]) * h)

        self.offshore_cum.add(float(lamO.sum() * g.dx))
        self.chronic_cum.add(float((rho * self.H).sum() * g.dx * h))
        self.offshore_central_cum.add(float(lamO[g.central].sum() * g.dx))
        self.chronic_central_cum.add(float((rho[g.central] * self.H).sum() * g.dx * h))
        self.recovery_cum.add(float(Rn.sum() * g.dx))

        self.y = y_new
        self.O = O_new
        R_c = deficit(self.y, self.V_min, self.V_ref, self.H)
        self.D_max = np.maximum(self.D_max, R_c)
        self.metrics.track_w_min(self.y)

    # ------------------------------------------------------------------
    # ledger
    # ------------------------------------------------------------------
    def _record(self, t: float) -> None:
        g = self.grid
        V_domain = float((self.H * self.y).sum() * g.dx) - self.V0_domain
        O_domain = float(self.O.sum() * g.dx) - self.O0_domain
        V_central = float((self.H * self.y[g.central]).sum() * g.dx) - self.V0_central
        O_central = float(self.O[g.central].sum() * g.dx) - self.O0_central
        R_c = deficit(self.y, self.V_min, self.V_ref, self.H)
        R_c_cum = float(R_c.sum() * g.dx)
        D_max_cum = float(self.D_max.sum() * g.dx)
        resid, resid_rel, _ = closure(
            placed_cum=self.placed_cum.value, V_domain=V_domain, O_domain=O_domain,
            R_c_cum=R_c_cum, R_c_start=self.D0,
            flux_left=self.flux_outer_left_cum.value,
            flux_right=self.flux_outer_right_cum.value,
            offshore=self.offshore_cum.value, chronic=self.chronic_cum.value)
        self.ledger.add(
            t=t, V_central=V_central, O_central=O_central,
            V_domain=V_domain, O_domain=O_domain, R_c_cum=R_c_cum,
            placed_cum=self.placed_cum.value,
            flux_inner_left_cum=self.flux_inner_left_cum.value,
            flux_inner_right_cum=self.flux_inner_right_cum.value,
            flux_outer_left_cum=self.flux_outer_left_cum.value,
            flux_outer_right_cum=self.flux_outer_right_cum.value,
            offshore_loss_cum=self.offshore_cum.value,
            chronic_loss_cum=self.chronic_cum.value,
            storm_injected_cum=self.storm_injected_cum.value,
            recovery_cum=self.recovery_cum.value,
            residual=resid, residual_rel=resid_rel,
            D_max_cum=D_max_cum, Q_limited_cum=self.q_limited_cum.value,
            n_events_applied=float(self.n_events_applied),
        )
        self._t_hist.append(float(t))
        if self.store_fields:
            self._y_hist.append(self.y.astype(np.float32))
            self._O_hist.append(self.O.astype(np.float32))

    # ------------------------------------------------------------------
    # forecasts (adaptive strategy only)
    # ------------------------------------------------------------------
    def target_xc_hotspot(self) -> float:
        """Location with the largest risk-weighted deficit (heuristic for ΔE_b)."""
        g = self.grid
        x_grid = g.x[g.central]
        y_c = self.y[g.central]
        b_def = np.maximum(self.m_s - (self.d_b + y_c), 0.0)
        w_def = np.maximum(self.w_mgmt - w_eff_of_y(y_c, self.w0[g.central]), 0.0)
        score = b_def + 0.5 * w_def
        best_x, best = 0.0, -1.0
        for xc in np.arange(-2000.0, 2000.0 + 1e-9, 100.0):
            m = np.abs(x_grid - xc) <= 500.0
            val = float(score[m].sum())
            if val > best:
                best, best_x = val, float(xc)
        return best_x

    def _forecast(self, t0: float, horizon: float, placements: List[Dict[str, Any]],
                  table: EventTable) -> Dict[str, float]:
        run = replace(self.run, t_end=t0 + horizon)
        sim = Simulator(self.params, self.scenario, run, grid=self.grid,
                        y0=self.y.copy(), O0=self.O.copy(), t0=t0,
                        store_fields=False, ledger_on=False, label="forecast")
        strategy = make_strategy(self.params, run, sim.budget, placements=placements)
        res = sim.run_loop(t_end=t0 + horizon, events=table, strategy=strategy,
                           collect=False)
        m = res.metrics
        tf = m["T_first_fail_b"]["value"]
        tf_rel = None if tf is None else max(0.0, tf - t0)
        return {"E_b": m["E_b"], "T_first_fail_b": tf_rel,
                "T_safe_cum_b": m["T_safe_cum_b"]}

    def forecast_choose(self, t0: float, horizon: float = 5.0) -> Dict[str, Any]:
        """5-year rolling forecast used by the adaptive strategy (D8)."""
        g = self.grid
        v = self.budget.feasible(self.budget.V_event_max)
        log: Dict[str, Any] = {"horizon": horizon, "volume": v}
        if v < MIN_MEANINGFUL:
            log["decision"] = "no_volume"
            return {"retreat": True, "xc": 0.0, "volume": 0.0, "log": log}
        candidates = [-1500.0, -750.0, 0.0, 750.0, 1500.0]
        n_members = 8
        base_e = np.zeros(n_members)
        cand_e = {xc: np.zeros(n_members) for xc in candidates}
        cand_tf = {xc: [] for xc in candidates}
        for m in range(n_members):
            # forecast storms: fresh draw, Poisson only (the forced S2 event is
            # NOT visible to the adaptive rule -- no knowledge of future storms)
            fseed = (int(self.run.seed) * 7919 + int(round(t0 * 100)) * 13 + m) % (2 ** 32)
            table = build_event_table(self.scenario, fseed, t0 + horizon, g.Lb,
                                      phi_shape=self.run.phi_shape, forced_events=[])
            base = self._forecast(t0, horizon, [], table)
            base_e[m] = base["E_b"]
            for xc in candidates:
                spec = [{"t": t0 + self.delay_for_adaptive(), "xc": xc, "len": 1000.0,
                         "volume": v, "tag": "forecast", "budgeted": False}]
                r = self._forecast(t0, horizon, spec, table)
                cand_e[xc][m] = r["E_b"]
                if r["T_first_fail_b"] is not None:
                    cand_tf[xc].append(r["T_first_fail_b"])
        scores = {}
        for xc in candidates:
            benefit = float(base_e.mean() - cand_e[xc].mean())
            scores[xc] = benefit / max(v, 1.0)
        best_cand = max(scores, key=scores.get)
        # In calm scenarios the 5-year forecast window can contain no building
        # risk at all (T_first_fail_b is ~14 yr), so every candidate ties at zero
        # benefit.  Then fall back to the risk-weighted deficit location instead
        # of an arbitrary argmax.  [自决, reported in PROGRESS]
        fallback = max(scores.values()) <= 1e-12
        best_xc = self.target_xc_hotspot() if fallback else best_cand
        if fallback:
            tf_best = float("inf")  # no building risk in the forecast window
        else:
            tf_best = min(cand_tf[best_cand]) if cand_tf[best_cand] else float("inf")
        log.update({
            "E_b_base": float(base_e.mean()),
            "E_b_best": float(cand_e[best_cand].mean()),
            "delta_E_b": float(base_e.mean() - cand_e[best_cand].mean()),
            "best_xc": best_xc,
            "benefit_fallback": fallback,
            "T_first_fail_b_forecast": (None if tf_best == float("inf") else float(tf_best)),
            "scores": {str(k): float(val) for k, val in scores.items()},
        })
        retreat = tf_best < float(self.params["T_min"])
        log["decision"] = "retreat" if retreat else "place"
        return {"retreat": bool(retreat), "xc": float(best_xc), "volume": float(v),
                "log": log}

    def delay_for_adaptive(self) -> float:
        return float(self.params["permit_delay"]) + float(self.params["tau_build"])

    # ------------------------------------------------------------------
    # main loop
    # ------------------------------------------------------------------
    def run_loop(self, t_end: Optional[float] = None, events: Optional[EventTable] = None,
                 strategy: Optional[Strategy] = None, collect: bool = True) -> SimResult:
        g = self.grid
        T = float(t_end if t_end is not None else self.run.t_end)
        table = events if events is not None else getattr(self, "event_table", None)
        if table is None:
            table = build_event_table(self.scenario, self.run.seed, T, g.Lb,
                                      self.run.phi_shape, self.run.forced_events)
            self.event_table = table
        if isinstance(table, (list, tuple)):
            table = EventTable(events=list(table))
        strat = strategy if strategy is not None else getattr(self, "strategy", None)
        if strat is None:
            strat = make_strategy(self.params, self.run, self.budget,
                                  placements=self.run.placements)
            self.strategy = strat
        self.events_table = table

        strat.initial(self)
        self.t = self.t_start
        # P0-4 ordering: the t=0 placement happens *before* anything else
        self._apply_due_placements(self.t)
        if collect:
            self.metrics.observe(self.t, self.y)
            self.metrics.track_w_min(self.y)
            self._record(self.t)

        ev_list = list(table.events)
        ei = 0
        dt = float(self.run.dt)
        while self.t < T - 1e-12:
            next_t = ev_list[ei].t if ei < len(ev_list) else float("inf")
            t_stop = min(self.t + dt, T)
            if next_t > self.t + 1e-12:
                t_stop = min(t_stop, next_t)
            if T - t_stop < 1e-12:
                t_stop = T
            h = t_stop - self.t
            if h <= 0.0:  # pragma: no cover - defensive
                t_stop = min(self.t + dt, T)
                h = t_stop - self.t
            self._advance(h)
            self.t = t_stop
            while ei < len(ev_list) and ev_list[ei].t <= self.t + 1e-12:
                self._apply_event(ev_list[ei], self.t)
                ei += 1
            strat.on_time(self.t, self)
            self._apply_due_placements(self.t)
            if collect:
                self.metrics.observe(self.t, self.y)
                self._record(self.t)

        if collect:
            self.planned_after_window()
            m = self.metrics.finalize(self.y)
            self.metrics_out = m
            y_end = self.y.copy()
            O_end = self.O.copy()
            self._y_hist = np.asarray(self._y_hist, dtype=np.float32)
            self._O_hist = np.asarray(self._O_hist, dtype=np.float32)
            self._t_hist = np.asarray(self._t_hist, dtype=float)
        else:
            m = self.metrics.finalize(self.y)
            y_end = self.y.copy()
            O_end = self.O.copy()
        return SimResult(
            grid=g, t=np.asarray(self._t_hist, dtype=float),
            y=self._y_hist if collect else self.y,
            O=self._O_hist if collect else self.O,
            w0=self.w0, y_end=y_end, O_end=O_end,
            ledger=self.ledger, events=self.events_rows, metrics=m,
            budget=self.budget.as_dict(), strategy_log=getattr(strat, "trigger_log", []),
            n_events_applied=self.n_events_applied,
            config=self.run.as_dict(), params_md5=self.params.md5,
            scenario=self.scenario.as_dict(),
            placements_applied=self.placements_applied,
        )


def run_model(params: Params, scenario: Scenario, run: RunConfig,
              events: Optional[EventTable] = None,
              placements: Optional[List[Dict[str, Any]]] = None,
              store_fields: bool = True) -> SimResult:
    """Convenience wrapper: build a simulator and run it once."""
    sim = Simulator(params, scenario, run, store_fields=store_fields)
    strat = make_strategy(params, run, sim.budget,
                          placements=placements if placements is not None else run.placements)
    return sim.run_loop(run.t_end, events=events, strategy=strat, collect=True)
