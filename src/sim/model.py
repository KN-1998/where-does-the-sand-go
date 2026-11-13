"""Event-driven one-dimensional shoreline model."""

from dataclasses import dataclass
from pathlib import Path

import numpy as np

from .accounting import control_totals, relative_residual, residual
from .grid import Grid, limited_transport
from .io import value
from .metrics import (historical_deficit, reconstructed_risk_metrics,
                      recovery_samples, recovery_statistics)
from .storms import apply_storm, generate_events
from .strategies import (Placement, apply_placement, cost_terms,
                         feasible_volume, snap_up, strategy_schedule)
from .units import book_volume, current_deficit, minimum_volume


@dataclass
class SimulationResult:
    results: dict
    fields: dict
    ledger: list
    events: list
    event_records: list
    skipped_placements: list
    recovery_records: list


class ShorelineModel:
    """Minimal production runner for E0/E1 and later event-driven experiments."""

    def __init__(self, params, scenario="S1", strategy="none", boundary="zeroflux",
                 seed=42, t_end=None, dx=None, dt=None, placements=None,
                 rho_override=None, events=None, storm_enabled=True,
                 y_boundary=None, skipped_placements=None, initial_y=None,
                 initial_o=None, t_start=0.0):
        self.params = params
        self.scenario = scenario
        self.strategy = strategy
        self.boundary = boundary
        if boundary == "dirichlet" and y_boundary is None:
            raise ValueError("dirichlet boundary requires explicit adjacent-shoreline values")
        self.y_boundary = y_boundary
        self.seed = int(seed)
        self.t_start = float(t_start)
        self.t_end = float(t_end if t_end is not None else value(params, "domain", "T_sim"))
        self.dt = float(dt if dt is not None else value(params, "numerics", "dt", 0.02))
        if self.dt <= 0 or self.t_end <= 0:
            raise ValueError("dt and t_end must be positive")
        dx = float(dx if dx is not None else value(params, "numerics", "dx", 25.0))
        corridor = float(value(params, "domain", "L_corridor"))
        buffer_length = float(value(params, "domain", "L_buffer"))
        self.grid = Grid.build(corridor / 2.0 + buffer_length, dx, corridor / 2.0)
        self.h = float(value(params, "geometry", "H_dep"))
        self.v_ref = float(value(params, "beach_state", "V_ref"))
        self.w_far = float(value(params, "beach_state", "w0_far"))
        self.w_min = float(value(params, "beach_state", "w0_min"))
        self.sigma_w = float(value(params, "beach_state", "sigma_w"))
        self.w0 = self.w_far - (self.w_far - self.w_min) * np.exp(
            -(self.grid.x ** 2) / (2.0 * self.sigma_w ** 2))
        self.diffusivity = float(value(params, "transport", "D_diff"))
        self.hs_trend = float(value(params, "climate_scenarios", "Hs_trend", 0.0)) / 100.0
        self.drift = float(value(params, "transport", "u_drift"))
        self.rho_base = float(value(params, "transport", "rho_e")) * (
            1.0 + float(value(params, "transport", "rho_e_hotspot_amp")) * np.exp(
                -((self.grid.x-float(value(params,'domain','x_h',0.))) ** 2) / (2.0 * float(value(params, "transport", "sigma_h")) ** 2)))
        self.k = float(value(params, "storm", "k_rec"))
        self.lam = float(value(params, "storm", "lam_off"))
        if self.k < 0 or self.lam < 0:
            raise ValueError("reservoir rates cannot be negative")
        self.w_sat = float(value(params, "storm", "w_sat"))
        self.sigma_e = float(value(params, "storm", "sigma_e"))
        self.rho_override = rho_override
        self.initial_y = np.zeros(self.grid.x.size, dtype=np.float64) if initial_y is None else np.asarray(initial_y, float).copy()
        self.initial_o = np.zeros(self.grid.x.size, dtype=np.float64) if initial_o is None else np.asarray(initial_o, float).copy()
        if (self.initial_y.shape != self.w0.shape or self.initial_o.shape != self.w0.shape or
                not np.all(np.isfinite(self.initial_y)) or not np.all(np.isfinite(self.initial_o)) or
                np.any(self.initial_o < 0) or not 0 <= self.t_start < self.t_end):
            raise ValueError("finite grid-shaped initial states, O>=0 and 0<=t_start<t_end required")
        self.initial_v = book_volume(self.initial_y, self.w0, self.h, self.v_ref)
        self.initial_total = float(((self.initial_v + self.initial_o) * self.grid.dx).sum())
        self.initial_deficit = float((current_deficit(
            self.initial_y, self.w0, self.h, self.v_ref) * self.grid.dx).sum())
        self.placements = list(placements) if placements is not None else []
        self.skipped_placements = list(skipped_placements or [])
        if placements is None:
            self.placements = strategy_schedule(
                strategy, params, self.t_end, value(params, "domain", "x_h"))
        self.events = list(events) if events is not None else (
            generate_events(params, scenario, self.t_end, self.seed)[0]
            if storm_enabled else [])
        self.events.sort(key=lambda item: item.time)
        self.placements.sort(key=lambda item: item.time)
        if any(not np.isfinite(e.time) or e.time < self.t_start-1e-9 or e.time > self.t_end+1e-9
               or not np.isfinite(e.potential_retreat) or e.potential_retreat < 0 for e in self.events):
            raise ValueError("events must be finite, nonnegative and inside the run window")
        if any(not np.isfinite(p.time) or p.time < self.t_start-1e-9 or p.time > self.t_end+1e-9
               or not np.isfinite(p.volume) or p.volume < 0 for p in self.placements):
            raise ValueError("placements must be finite, nonnegative and inside the run window")

    def _rho(self, t):
        if self.rho_override is not None:
            return np.full(self.grid.x.size, float(self.rho_override))
        scenarios = self.params["scenarios"]
        if self.scenario == "S1":
            scenario = scenarios["S1_calm"]
            lam_s, median, target = scenario["lambda_s"], scenario["dy_ref"], scenario["rho_e"]
        elif self.scenario == "S2":
            scenario = scenarios["S2_storm_soon"]
            lam_s, median, target = scenario["lambda_s"], scenario["dy_ref"], scenario["rho_e"]
        elif self.scenario == "S3":
            scenario = scenarios["S3_repeat"]
            scenario_horizon = float(value(self.params, "domain", "T_sim", self.t_end))
            f = np.clip(t / scenario_horizon, 0.0, 1.0)
            lam_s = scenario["lambda_s"][0] + f * (scenario["lambda_s"][1] - scenario["lambda_s"][0])
            median = scenario["dy_ref"][0] + f * (scenario["dy_ref"][1] - scenario["dy_ref"][0])
            target = scenario["rho_e"][0] + f * (scenario["rho_e"][1] - scenario["rho_e"][0])
        else:
            raise ValueError(f"unknown scenario {self.scenario!r}")
        sigma_ln = np.log(25.0 / 8.0) / 1.645
        lam_ratio = self.lam / (self.k + self.lam) if self.k + self.lam else 0.0
        rho_storm = float(lam_s) * float(median) * np.exp(sigma_ln**2 / 2.0) * lam_ratio
        if self.params.get("chronic_mode", "scenario_net") == "observed_direct":
            return self.rho_base.copy()
        if self.params.get("chronic_mode", "scenario_net") == "scenario_unadjusted":
            return self.rho_base * float(target) / float(value(self.params, "transport", "rho_e_corridor_mean"))
        scale = (float(target) - rho_storm) / float(value(self.params, "transport", "rho_e_corridor_mean"))
        if scale < 0:
            raise ValueError("storm permanent-loss proxy exceeds scenario total erosion; specify a valid chronic model")
        return self.rho_base * scale

    def _scenario_rates(self, t):
        if self.scenario == "S1":
            scenario = self.params["scenarios"]["S1_calm"]
            return float(scenario["lambda_s"]), float(scenario["dy_ref"]), float(scenario["rho_e"])
        if self.scenario == "S2":
            scenario = self.params["scenarios"]["S2_storm_soon"]
            return float(scenario["lambda_s"]), float(scenario["dy_ref"]), float(scenario["rho_e"])
        if self.scenario == "S3":
            scenario = self.params["scenarios"]["S3_repeat"]
            horizon = float(value(self.params, "domain", "T_sim", self.t_end))
            fraction = float(np.clip(t / horizon, 0.0, 1.0))
            interpolate = lambda pair: float(pair[0]) + fraction * (float(pair[1]) - float(pair[0]))
            return (interpolate(scenario["lambda_s"]), interpolate(scenario["dy_ref"]),
                    interpolate(scenario["rho_e"]))
        raise ValueError(f"unknown scenario {self.scenario!r}")

    def _diffusivity(self, t):
        if self.scenario != "S3":
            return self.diffusivity
        return self.diffusivity * (1.0 + self.hs_trend * float(t) / 10.0) ** 2.5

    def _record(self, t, y, offshore, placed, flux_left, flux_right,
                flux_inner_left, flux_inner_right, offshore_loss, chronic_loss,
                recovery, storm_injected, rows, limiter_faces=0):
        domain = np.ones(self.grid.x.size, dtype=bool)
        central = self.grid.central_mask
        v_book = book_volume(y, self.w0, self.h, self.v_ref)
        deficit = current_deficit(y, self.w0, self.h, self.v_ref)
        current_total = float(((v_book + offshore) * self.grid.dx).sum())
        residual_value = residual(
            placed, flux_left + flux_right, offshore_loss, chronic_loss,
            current_total, self.initial_total,
            float((deficit * self.grid.dx).sum()), self.initial_deficit)
        central_v = float(((v_book[central] - self.v_ref) * self.grid.dx).sum())
        domain_v = float(((v_book[domain] - self.v_ref) * self.grid.dx).sum())
        central_deficit = float(deficit[central].sum() * self.grid.dx)
        central_residual = residual(self.central_cumulative['placed'],
            flux_inner_left + flux_inner_right, self.central_cumulative['offshore'],
            self.central_cumulative['chronic'],
            float((v_book[central]+offshore[central]).sum()*self.grid.dx),
            float((self.initial_v[central]+self.initial_o[central]).sum()*self.grid.dx),
            central_deficit, float(current_deficit(self.initial_y,self.w0,self.h,self.v_ref)[central].sum()*self.grid.dx))
        rows.append({
            "t": float(t),
            "V_central": central_v,
            "O_central": float((offshore[central] * self.grid.dx).sum()),
            "R_c_central": central_deficit,
            "placed_central_cum": float(self.central_cumulative['placed']),
            "offshore_loss_central_cum": float(self.central_cumulative['offshore']),
            "chronic_loss_central_cum": float(self.central_cumulative['chronic']),
            "residual_central": central_residual,
            "residual_central_rel": relative_residual(central_residual, self.central_cumulative['placed']),
            "V_domain": domain_v,
            "O_domain": float((offshore * self.grid.dx).sum()),
            "R_c_cum": float((deficit * self.grid.dx).sum()),
            "placed_cum": float(placed),
            "flux_inner_left_cum": float(flux_inner_left),
            "flux_inner_right_cum": float(flux_inner_right),
            "flux_outer_left_cum": float(flux_left),
            "flux_outer_right_cum": float(flux_right),
            "offshore_loss_cum": float(offshore_loss),
            "chronic_loss_cum": float(chronic_loss),
            "storm_injected_cum": float(storm_injected),
            "recovery_cum": float(recovery),
            "transport_limited_faces": int(limiter_faces),
            "residual": float(residual_value),
            "residual_rel": float(relative_residual(residual_value, placed)),
        })

    def run(self):
        y = self.initial_y.copy()
        offshore = self.initial_o.copy()
        t = self.t_start
        event_i = 0
        placement_i = 0
        projects_applied = 0
        applied_project_ids = set()
        placed = flux_left = flux_right = 0.0
        flux_inner_left = flux_inner_right = 0.0
        offshore_loss = chronic_loss = 0.0
        recovery = storm_injected = 0.0
        limiter_faces = 0
        event_records = []
        storm_transitions = []
        adaptive_decisions = []
        ledger = []
        self.central_cumulative = {'placed':0., 'offshore':0., 'chronic':0.}
        times = [t]
        ys = [y.copy()]
        os = [offshore.copy()]

        def due(time, target):
            return target is not None and abs(float(target) - time) <= 1e-9

        def save_state(time):
            times.append(time); ys.append(y.copy()); os.append(offshore.copy())

        def apply_due(time):
            nonlocal y, offshore, placement_i, event_i, placed, storm_injected, projects_applied, adaptive_baseline_fw
            # Contract order: initial placement precedes a t=0 storm; at later
            # coincidences the storm jump precedes the placement pulse.
            if abs(time) <= 1e-9:
                order = ("placement", "storm")
            else:
                order = ("storm", "placement")
            for kind in order:
                if kind == "storm":
                    while event_i < len(self.events) and due(time, self.events[event_i].time):
                        event = self.events[event_i]
                        y_before = y.copy()
                        y, offshore, potential, actual_center, injected, inj = apply_storm(
                            y, offshore, self.w0, self.grid, self.h, event, self.w_sat, self.sigma_e)
                        y_after = y.copy()
                        w_threshold = float(value(self.params, "beach_state", "w_mgmt"))
                        b_threshold = float(value(self.params, "beach_state", "m_safe"))
                        d_bldg = float(value(self.params, "beach_state", "d_bldg"))
                        storm_transitions.append({
                            "t": float(event.time),
                            "w_before": self.w0 + y_before < w_threshold,
                            "w_after": self.w0 + y_after < w_threshold,
                            "b_before": d_bldg + y_before < b_threshold,
                            "b_after": d_bldg + y_after < b_threshold,
                        })
                        storm_injected += injected
                        event_records.append({
                            "t": float(event.time),
                            "potential_retreat": float(potential),
                            "actual_center_retreat": float(actual_center),
                            "center": float(event.center),
                            "gaussian": bool(event.gaussian),
                            "sigma_e": float(self.sigma_e) if event.gaussian else None,
                            "forced": bool(event.forced),
                            "forced_actual_retreat": event.forced_actual_retreat,
                            "injected_full_m3": float(inj.sum()),
                            "injected_central_m3": float(inj[self.grid.central_mask].sum()),
                            "depleted_cells": int(np.count_nonzero((self.w0 + y) <= 0.0)),
                        })
                        event_i += 1
                        save_state(time)
                else:
                    while placement_i < len(self.placements) and due(time, self.placements[placement_i].time):
                        placement = self.placements[placement_i]
                        y, actual, added = apply_placement(
                            y, placement.volume, placement.center, placement.length, self.grid, self.h)
                        placed += actual
                        self.central_cumulative['placed'] += float(added[self.grid.central_mask].sum())
                        project_id = placement.project_id or f'pulse_{placement_i}'
                        projects_applied += int(actual > 0.0 and project_id not in applied_project_ids)
                        if actual > 0.0: applied_project_ids.add(project_id)
                        if self.strategy in {'adaptive','targeted'} and actual > 0:
                            controller.reset_reference = True
                        placement_i += 1
                        save_state(time)
                        if self.strategy == "adaptive":
                            smooth_n = max(1, int(round(500.0 / self.grid.dx)))
                            post_w = np.convolve(self.w0 + y, np.ones(smooth_n) / smooth_n, mode="same")
                            adaptive_baseline_fw = float((post_w[self.grid.central_mask] <
                                value(self.params, "beach_state", "w_mgmt")).mean())

        controller = None
        if self.strategy in {"adaptive","targeted"}:
            from .adaptive import AdaptiveController
            controller = AdaptiveController(self)

        def maybe_schedule_adaptive(time):
            if controller is None:
                return
            pending = any(item.time > time+1e-9 for item in self.placements[placement_i:])
            plan = controller.observe(time,y,offshore,placed,projects_applied,pending)
            if plan is not None:
                self.placements.append(plan)
                self.placements.sort(key=lambda item:item.time)

        adaptive_baseline_fw = None
        apply_due(t)
        # The initial reporting state follows all t=0 actions. Later jumps
        # retain every intermediate state to detect even brief failures.
        times[:] = [t]; ys[:] = [y.copy()]; os[:] = [offshore.copy()]
        maybe_schedule_adaptive(t)
        self._record(t, y, offshore, placed, flux_left, flux_right,
                     flux_inner_left, flux_inner_right, offshore_loss,
                     chronic_loss, recovery, storm_injected, ledger, limiter_faces)
        while t < self.t_end - 1e-10:
            candidates = [self.t_end, t + self.dt]
            # Use identical quarterly split points for every policy. Otherwise
            # a never-triggered adaptive run differs numerically from baseline.
            candidates.append(min(self.t_end, (np.floor(t / 0.25 + 1e-9) + 1.0) * 0.25))
            if event_i < len(self.events) and self.events[event_i].time > t + 1e-9:
                candidates.append(self.events[event_i].time)
            if placement_i < len(self.placements) and self.placements[placement_i].time > t + 1e-9:
                candidates.append(self.placements[placement_i].time)
            if controller is not None:
                candidates.extend(controller.next_monitor_times(t))
            t_next = min(candidates)
            h_step = t_next - t
            if h_step <= 1e-12:
                apply_due(t)
                continue
            rho = self._rho(t + h_step / 2.0)
            diffusivity = self._diffusivity(t + h_step / 2.0)
            total_rate = self.k + self.lam
            o_next = offshore * np.exp(-total_rate * h_step)
            recovery_step = (self.k / total_rate) * (offshore - o_next) if total_rate else np.zeros_like(offshore)
            loss_step = (self.lam / total_rate) * (offshore - o_next) if total_rate else np.zeros_like(offshore)
            source = recovery_step / (self.h * h_step) - rho
            y, flux, limited = limited_transport(
                y, source, self.w0, h_step, self.grid, diffusivity, self.drift,
                self.boundary, self.y_boundary)
            limiter_faces += limited
            flux_left += -self.h * float(flux[0]) * h_step
            flux_right += self.h * float(flux[-1]) * h_step
            left_inner_face = int(np.flatnonzero(self.grid.central_mask)[0])
            right_inner_face = int(np.flatnonzero(self.grid.central_mask)[-1] + 1)
            flux_inner_left += -self.h * float(flux[left_inner_face]) * h_step
            flux_inner_right += self.h * float(flux[right_inner_face]) * h_step
            offshore = o_next
            recovery += float((recovery_step * self.grid.dx).sum())
            offshore_loss += float((loss_step * self.grid.dx).sum())
            chronic_loss += float((rho * self.h * self.grid.dx * h_step).sum())
            self.central_cumulative['offshore'] += float(loss_step[self.grid.central_mask].sum()*self.grid.dx)
            self.central_cumulative['chronic'] += float(rho[self.grid.central_mask].sum()*self.h*self.grid.dx*h_step)
            t = t_next
            if ((event_i < len(self.events) and due(t, self.events[event_i].time)) or
                    (placement_i < len(self.placements) and due(t, self.placements[placement_i].time))):
                times.append(t)
                ys.append(y.copy())
                os.append(offshore.copy())
            apply_due(t)
            maybe_schedule_adaptive(t)
            times.append(t)
            ys.append(y.copy())
            os.append(offshore.copy())
            self._record(t, y, offshore, placed, flux_left, flux_right,
                         flux_inner_left, flux_inner_right, offshore_loss,
                         chronic_loss, recovery, storm_injected, ledger, limiter_faces)

        w = self.w0[None, :] + np.asarray(ys)
        risk_w = w.clip(min=0.0) < float(value(self.params, "beach_state", "w_mgmt"))
        risk_b = float(value(self.params, "beach_state", "d_bldg")) + np.asarray(ys) < float(value(self.params, "beach_state", "m_safe"))
        central = self.grid.central_mask
        f_w0 = float(risk_w[0, central].mean())
        f_b0 = float(risk_b[0, central].mean())
        f_thr = float(value(self.params, "management", "f_thr"))
        f_w = risk_w[:, central].mean(axis=1)
        f_b = risk_b[:, central].mean(axis=1)

        first_w, safe_w, exposure_w_unit = reconstructed_risk_metrics(
            times, w[:, central] - float(value(self.params, "beach_state", "w_mgmt")), f_thr)
        first_b, safe_b, exposure_b_unit = reconstructed_risk_metrics(
            times, float(value(self.params, "beach_state", "d_bldg")) +
            np.asarray(ys)[:, central] - float(value(self.params, "beach_state", "m_safe")), f_thr)
        t_values = np.asarray(times)
        recovery_records = []
        recovery_summaries = {}
        for suffix, risk in (("w", risk_w), ("b", risk_b)):
            samples = recovery_samples(
                t_values, risk,
                [(item["t"], item[suffix + "_before"], item[suffix + "_after"])
                 for item in storm_transitions],
                [event.time for event in self.events], self.t_end, central,
                [item.time for item in self.placements[:placement_i]])
            recovery_summaries[suffix] = recovery_statistics(samples)
            recovery_records.extend(dict(sample, metric=suffix) for sample in samples)
        recovery_w, recovery_b = recovery_summaries["w"], recovery_summaries["b"]
        central_length = float(central.sum() * self.grid.dx)
        exposure_w = exposure_w_unit * central_length
        exposure_b = exposure_b_unit * central_length
        # Historical maximum of the current V-floor deficit.  This uses raw
        # w=w0+y, because y is deliberately allowed below -w0 after exhaustion;
        # clipping w at zero would report the wrong deficit.
        d_max_cum = historical_deficit(w, self.h, self.grid.dx)
        cost_model = value(self.params, "management", "cost_model", "all_in")
        supply = value(self.params, "management", "supply_scenario", "local")
        c1 = float(value(self.params, "management",
                         "c1" if cost_model == "all_in" else "c1_marginal", 0.0))
        if supply == "external":
            c1 += float(value(self.params, "management", "transport_cost_add", 0.0))
        c0 = (float(value(self.params, "management", "c0", 0.0))
              if cost_model == "marginal_plus_fixed" else 0.0)
        results = {
            "meta": {"scenario": self.scenario, "strategy": self.strategy,
                     "bc": self.boundary, "seed": self.seed, "dt": self.dt,
                     "dx": self.grid.dx, "cost_model": cost_model,
                     "supply": supply,
                     "metric_integration": "linear spatial/time states; analytic piecewise exposure; bounded first crossing; all jumps saved",
                     "adaptive_method": "five-year independent-storm ensemble; observed state; cost-normalized building benefit; synthetic posterior updates"
                        if self.strategy in {"adaptive","targeted"} else None,
                     'S2_forced_event_scope':'state-conditioned fixed actual retreat stress; potential forcing may differ between interventions'
                        if self.scenario=='S2' else None},
            "initial": {"f_w0": f_w0, "f_b0": f_b0,
                        "w_min": float(w[0].min()), "w_mean": float(w[0, central].mean())},
            "mass": {"placed": placed, "flux_out": flux_left + flux_right,
                     "flux_inner": flux_inner_left + flux_inner_right,
                     "offshore": offshore_loss, "chronic": chronic_loss,
                     "recovery": recovery, "storm_injected": storm_injected,
                     "R_c": ledger[-1]["R_c_cum"],
                     "D_max_cum": d_max_cum,
                     "transport_limited_faces": limiter_faces,
                     "residual_rel_max": max(row["residual_rel"] for row in ledger)},
            "state": {"w_end_min": float(w[-1].min()),
                      "w_end_mean": float(w[-1, central].mean()),
                      "exhausted_frac": float((w[-1, central] <= 0.0).mean())},
            "duration": {"T_first_fail_w": first_w, "T_first_fail_b": first_b,
                         "T_safe_cum_w": safe_w, "T_safe_cum_b": safe_b,
                         "T_recovery_w": recovery_w, "T_recovery_b": recovery_b},
            "exposure": {"E_w": exposure_w, "E_b": exposure_b},
            "cost": {"construction_cost": placed * c1 + projects_applied * c0,
                     "monitoring_cost": controller.monitor_cost if controller else 0.,
                     "cost_used": placed * c1 + projects_applied * c0 + (controller.monitor_cost if controller else 0.),
                     "n_projects": projects_applied, "c0_star": None},
        }
        results["events"] = {"n_events_applied": len(event_records)}
        results['mass']['residual_central_rel_max'] = max(row['residual_central_rel'] for row in ledger)
        results["placements"] = {
            "n_applied": projects_applied,
            "skipped": self.skipped_placements,
            "adaptive_decisions": controller.logs if controller else adaptive_decisions,
        }
        return SimulationResult(results, {
            "y": np.asarray(ys), "O": np.asarray(os), "w": w,
            "x": self.grid.x, "t": np.asarray(times),
            "exhausted": w <= 0,
        }, ledger, self.events, event_records, self.skipped_placements, recovery_records)
