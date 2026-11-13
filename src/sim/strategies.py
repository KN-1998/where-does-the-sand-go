"""Placement geometry and per-project/cumulative cost constraints."""
from dataclasses import dataclass
import numpy as np

from .io import value


@dataclass(frozen=True)
class Placement:
    time: float
    volume: float
    center: float
    length: float
    label: str = "manual"
    planned_time: float | None = None
    project_id: str | None = None


def _entry(params, section, name, default=None):
    item = params.get(section, {}).get(name, default)
    return item.get("value", default) if isinstance(item, dict) else item


def cost_terms(params):
    mode = _entry(params, "management", "cost_model")
    supply = _entry(params, "management", "supply_scenario")
    if mode not in {"all_in", "marginal_plus_fixed"}:
        raise ValueError(f"unknown cost_model {mode!r}")
    unit_name = "c1" if mode == "all_in" else "c1_marginal"
    unit = float(_entry(params, "management", unit_name))
    if supply == "external":
        unit += float(_entry(params, "management", "transport_cost_add", 0.0))
    fixed = 0.0 if mode == "all_in" else float(_entry(params, "management", "c0", 0.0))
    return unit, fixed


def supply_cap(params):
    total = float(_entry(params, "management", "V15_total"))
    if _entry(params, "management", "supply_scenario") == "local":
        return min(total, float(_entry(params, "management", "S_borrow_total")) *
                   float(_entry(params, "management", "supply_availability")))
    return total


def feasible_volume(params, desired, used=0.0, spent=0.0, projects_remaining=1):
    unit, fixed = cost_terms(params)
    budget = float(_entry(params, "management", "C_max")) - spent
    if projects_remaining > 0:
        budget -= fixed
    return max(0.0, min(float(desired),
        float(_entry(params, "management", "V_event_max")),
        supply_cap(params) - used,
        float(_entry(params, "management", "V15_total")) - used,
        budget / unit if unit > 0 else 0.0))


def constrain_placements(params, placements):
    unit, fixed = cost_terms(params)
    used = spent = 0.0
    project_volume = {}
    accepted, skipped = [], []
    meaningful = float(_entry(params, "management", "V_min_meaningful", 1e5))
    for placement in sorted(placements, key=lambda item: item.time):
        group = placement.project_id or str(id(placement))
        used_project = project_volume.get(group, 0.)
        volume = feasible_volume(params, min(placement.volume,
            float(_entry(params,'management','V_event_max'))-used_project), used, spent,
            projects_remaining=int(group not in project_volume))
        if volume < meaningful:
            skipped.append({"planned_time": placement.planned_time if placement.planned_time is not None else placement.time,
                            "actual_time": placement.time, "designed_m3": placement.volume,
                            "skipped_m3": placement.volume, "reason": "below_minimum_meaningful_volume"})
            continue
        accepted.append(Placement(placement.time, volume, placement.center,
                                  placement.length, placement.label, placement.planned_time, placement.project_id))
        used += volume
        spent += (fixed if group not in project_volume else 0.) + unit * volume
        project_volume[group] = used_project+volume
        if volume < placement.volume:
            skipped.append({"planned_time": placement.planned_time if placement.planned_time is not None else placement.time,
                            "actual_time": placement.time, "designed_m3": placement.volume,
                            "skipped_m3": placement.volume-volume, "reason": "supply_or_budget_cap"})
    return accepted, skipped


def snap_up(time, dt):
    return float(np.ceil(float(time) / float(dt) - 1e-10) * float(dt))


def make_layout(layout, total_volume, x_hotspot=0.0, time=0.0):
    if total_volume < 0:
        raise ValueError("placement volume cannot be negative")
    if layout == "uniform":
        return [Placement(time, total_volume, 0.0, 5000.0, layout)]
    if layout == "hotspot":
        return [Placement(time, total_volume, x_hotspot, 1000.0, layout)]
    if layout == "multi":
        centers = x_hotspot + np.array([-1800.0, -900.0, 0.0, 900.0, 1800.0])
        return [Placement(time, total_volume / 5.0, float(x), 500.0, layout,
                          project_id=f'multi:{time:.12g}')
                for x in centers]
    raise ValueError(f"unknown layout {layout!r}")


def strategy_schedule(strategy, params, t_end, x_hotspot=0.0):
    if strategy == "adaptive":
        return []
    if strategy in {None, "none"}:
        return []
    if strategy in {"uniform", "hotspot", "multi"}:
        placements = make_layout(strategy, feasible_volume(params, supply_cap(params)), x_hotspot, 0.0)
        return constrain_placements(params, placements)[0]
    if strategy not in {"once", "repeat", "targeted", "fixed_hotspot"}:
        raise ValueError(f"unknown strategy {strategy!r}")

    n = 3 if strategy == "repeat" else 1
    unit, fixed = cost_terms(params)
    total = min(supply_cap(params), n * float(_entry(params, "management", "V_event_max")),
                (float(_entry(params, "management", "C_max")) - n * fixed) / unit)
    dt = float(_entry(params, "numerics", "dt", 0.02))
    delay = float(_entry(params, "management", "permit_delay")) + float(_entry(params, "management", "tau_build"))
    if strategy == 'targeted': total /= 4.0
    placements = []
    for i in range(n):
        planned = delay + 5.0 * i
        actual = snap_up(planned, dt)
        if actual > t_end + 1e-10:
            continue
        placements.append(Placement(
            actual, total / n, x_hotspot if strategy in {"targeted","fixed_hotspot"} else 0.0,
            1000.0 if strategy in {"targeted","fixed_hotspot"} else 5000.0, strategy, planned))
    return constrain_placements(params, placements)[0]


def apply_placement(y, volume, center, length, grid, h):
    if volume < 0 or length <= 0:
        raise ValueError("volume must be nonnegative and length positive")
    lo, hi = center - length / 2.0, center + length / 2.0
    if lo < -grid.half_length - 1e-10 or hi > grid.half_length + 1e-10:
        raise ValueError("placement footprint extends beyond computational domain")
    cell_lo, cell_hi = grid.x - grid.dx / 2.0, grid.x + grid.dx / 2.0
    overlap = np.clip(np.minimum(cell_hi, hi) - np.maximum(cell_lo, lo), 0.0, None)
    if overlap.sum() <= 0:
        raise ValueError("placement footprint has no grid overlap")
    added = volume * overlap / overlap.sum()
    delta_y = added / (h * grid.dx)
    actual = float(added.sum())
    if abs(actual - volume) / max(volume, 1.0) >= 1e-12:
        raise ArithmeticError("placement volume failed conservation check")
    return np.asarray(y, dtype=np.float64) + delta_y, actual, added
