"""Paired storm-event generation and instantaneous beach/offshore exchange."""

from dataclasses import dataclass

import numpy as np


@dataclass(frozen=True)
class StormEvent:
    time: float
    potential_retreat: float
    center: float = 0.0
    gaussian: bool = False
    forced_actual_retreat: float | None = None
    forced: bool = False


def _scenario_params(params, scenario, t):
    scenarios = params["scenarios"]
    if scenario == "S1":
        s = scenarios["S1_calm"]
        return s["lambda_s"], s["dy_ref"], s["rho_e"]
    if scenario == "S2":
        s = scenarios["S2_storm_soon"]
        return s["lambda_s"], s["dy_ref"], s["rho_e"]
    if scenario == "S3":
        s = scenarios["S3_repeat"]
        f = np.clip(t / float(params["domain"]["T_sim"]["value"]), 0.0, 1.0)
        interp = lambda pair: float(pair[0]) + f * (float(pair[1]) - float(pair[0]))
        return interp(s["lambda_s"]), interp(s["dy_ref"]), interp(s["rho_e"])
    raise ValueError(f"unknown scenario {scenario!r}")


def generate_events(params, scenario, t_end, seed):
    """Generate one event table from scenario+seed, independent of strategy."""
    rng_arrival = np.random.default_rng((int(seed) * 1000003 + 11) % 2**32)
    rng_mag = np.random.default_rng((int(seed) * 1000003 + 29) % 2**32)
    rng_space = np.random.default_rng((int(seed) * 1000003 + 47) % 2**32)
    sigma_ln = np.log(25.0 / 8.0) / 1.645
    events = []
    t = 0.0
    if scenario in {"S1", "S2"}:
        lam, median, _ = _scenario_params(params, scenario, 0.0)
        while lam > 0:
            t += float(rng_arrival.exponential(1.0 / lam))
            if t >= t_end:
                break
            magnitude = float(rng_mag.lognormal(np.log(median), sigma_ln))
            events.append(StormEvent(t, magnitude))
    else:
        lam_max = float(_scenario_params(params, "S3", t_end)[0])
        while lam_max > 0:
            t += float(rng_arrival.exponential(1.0 / lam_max))
            if t >= t_end:
                break
            lam_t, median, _ = _scenario_params(params, "S3", t)
            if rng_arrival.random() <= lam_t / lam_max:
                events.append(StormEvent(t, float(rng_mag.lognormal(np.log(median), sigma_ln))))

    if scenario == "S2":
        forced_at = float(params["scenarios"]["S2_storm_soon"]["forced_event_at"])
        if forced_at <= t_end:
            magnitude = float(params["scenarios"]["S2_storm_soon"].get("forced_dy", 25.0))
            events.append(StormEvent(forced_at, 0.0, forced_actual_retreat=magnitude, forced=True))

    events.sort(key=lambda event: event.time)
    return events, rng_space


def apply_storm(y, offshore, w0, grid, h, event, w_sat, sigma_e):
    y = np.asarray(y, dtype=np.float64).copy()
    offshore = np.asarray(offshore, dtype=np.float64).copy()
    w_eff = np.maximum(w0 + y, 0.0)
    factor = 1.0 - np.exp(-w_eff / w_sat)
    potential = event.potential_retreat
    if event.forced_actual_retreat is not None:
        center_i = int(np.argmin(np.abs(grid.x - event.center)))
        center_factor = factor[center_i]
        potential = (event.forced_actual_retreat / center_factor) if center_factor > 0 else 0.0
    dy = np.minimum(potential * factor, w_eff)
    if event.gaussian:
        if sigma_e <= 0:
            raise ValueError("sigma_e must be positive for a Gaussian footprint")
        footprint = np.exp(-((grid.x - event.center) ** 2) / (2.0 * sigma_e**2))
        footprint /= footprint.max()
        dy *= footprint
    y -= dy
    offshore += h * dy
    inj = h * dy * grid.dx
    center_i = int(np.argmin(np.abs(grid.x - event.center)))
    return y, offshore, float(potential), float(dy[center_i]), float(inj.sum()), inj
