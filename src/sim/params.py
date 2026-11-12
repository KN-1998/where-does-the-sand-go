# -*- coding: utf-8 -*-
"""Parameter and configuration loading.

Sources of truth
----------------
* ``modeling/params.yaml``  -- frozen parameter registry (owner: modeler).
* ``configs/*.yaml``        -- run configuration; may override any flat key.

Nothing in this module invents parameter values: every number comes from the
registry or from the config file, and every lookup that fails raises, so a typo
in a config cannot silently fall back to a default.
"""
from __future__ import annotations

import hashlib
import json
import math
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_PARAMS = REPO_ROOT / "modeling" / "params.yaml"

#: scenario name -> block in params.yaml ``scenarios:``
SCENARIO_BLOCKS = {
    "S1": "S1_calm",
    "S2": "S2_storm_soon",
    "S3": "S3_repeat",
}

#: name of the reference (unscaled) parameter field; used as L0 baseline
SCENARIO_BASE = "base"


def _flatten(node: Dict[str, Any], out: Dict[str, Any], info: Dict[str, Any]) -> None:
    """Collect every leaf dict that carries a ``value`` key."""
    for key, value in node.items():
        if isinstance(value, dict):
            if "value" in value:
                out[key] = value["value"]
                info[key] = value
            else:
                _flatten(value, out, info)


class Params:
    """Flat, read-only view of ``params.yaml`` with provenance metadata."""

    def __init__(self, raw: Dict[str, Any], path: Path):
        self.raw = raw
        self.path = Path(path)
        self.flat: Dict[str, Any] = {}
        self.info: Dict[str, Dict[str, Any]] = {}
        for section, body in raw.items():
            if section in ("meta", "scenarios", "numerics"):
                continue
            if isinstance(body, dict):
                _flatten(body, self.flat, self.info)
        self.scenarios: Dict[str, Any] = raw.get("scenarios", {}) or {}
        self.numerics: Dict[str, Any] = {
            k: (v["value"] if isinstance(v, dict) and "value" in v else v)
            for k, v in (raw.get("numerics", {}) or {}).items()
        }
        self.meta: Dict[str, Any] = raw.get("meta", {}) or {}
        self.md5 = hashlib.md5(self.path.read_bytes()).hexdigest()

    # -- access ---------------------------------------------------------
    def __getitem__(self, key: str) -> Any:
        try:
            return self.flat[key]
        except KeyError as exc:  # pragma: no cover - defensive
            raise KeyError(
                f"parameter {key!r} not found in {self.path.name}; "
                "check params.yaml or the config overrides"
            ) from exc

    def get(self, key: str, default: Any = None) -> Any:
        return self.flat.get(key, default)

    def probe(self, key: str) -> Dict[str, Any]:
        """Full leaf dict (symbol/unit/source_type/evidence_id/...)."""
        return self.info.get(key, {})

    def clone_with(self, overrides: Dict[str, Any]) -> "Params":
        if not overrides:
            return self
        raw = json.loads(json.dumps(self.raw))  # deep copy, JSON-safe
        # override flat leaves in place where possible
        found = {}
        for section, body in raw.items():
            if not isinstance(body, dict) or section in ("meta",):
                continue
            for key, value in list(body.items()):
                if not isinstance(value, dict):
                    continue
                if "value" in value:
                    if key in overrides:
                        value["value"] = overrides[key]
                        found[key] = True
                else:
                    for k2, v2 in value.items():
                        if isinstance(v2, dict) and "value" in v2 and k2 in overrides:
                            v2["value"] = overrides[k2]
                            found[k2] = True
        missing = [k for k in overrides if k not in found]
        if missing:
            raise KeyError(f"override key(s) not present in params.yaml: {missing}")
        obj = Params.__new__(Params)
        obj.raw = raw
        obj.path = self.path
        obj.flat = dict(self.flat)
        obj.flat.update(overrides)
        obj.info = self.info
        obj.scenarios = self.scenarios
        obj.numerics = self.numerics
        obj.meta = self.meta
        obj.md5 = self.md5
        return obj


def load_params(path: Optional[str | Path] = None) -> Params:
    path = Path(path) if path else DEFAULT_PARAMS
    if not path.exists():
        raise FileNotFoundError(f"params.yaml not found: {path}")
    with path.open("r", encoding="utf-8") as fh:
        raw = yaml.safe_load(fh)
    if not isinstance(raw, dict):
        raise ValueError(f"{path} did not parse as a mapping")
    return Params(raw, path)


# ---------------------------------------------------------------------------
# Scenario time laws (CODER_SPEC §2.0)
# ---------------------------------------------------------------------------
class Scenario:
    """Time-dependent scenario inputs.

    S1 and S2 are stationary.  S3 linearly interpolates lambda_s, dy_ref and the
    corridor-mean erosion target between 2027 and 2042 and scales D with the
    +3%/decade wave-height trend (D ~ Hb^(5/2)).
    """

    def __init__(self, name: str, params: Params, overrides: Optional[Dict[str, Any]] = None):
        self.name = name
        self.p = params
        self.overrides = overrides or {}
        # Lognormal shape is frozen by CODER_SPEC §3.5: P95/median = 3.125.
        # It is defined once on the reference pair (8 m median, 25 m P95) and is
        # NOT rescaled by scenario: scenarios only move the median dy_ref(t).
        self.sigma_ln = math.log(float(params["dy_p95"]) / 8.0) / 1.645
        self.k = float(params["k_rec"])
        self.lam = float(params["lam_off"])
        self.corridor_mean = float(params["rho_e_corridor_mean"])
        self.forced_events: List[Dict[str, Any]] = []

        if name == SCENARIO_BASE:
            self.block = None
            self.lam0 = self.lam1 = float(params["lambda_s"])
            self.dy0 = self.dy1 = float(params["dy_ref"])
            self.target0 = self.target1 = float(params["rho_e_corridor_mean"])
            self.interpolate = False
        else:
            if name not in SCENARIO_BLOCKS:
                raise KeyError(f"unknown scenario {name!r}; expected base|S1|S2|S3")
            self.block = params.scenarios[SCENARIO_BLOCKS[name]]
            self.lam0 = _series(self.block["lambda_s"], 0.0)
            self.lam1 = _series(self.block["lambda_s"], 1.0)
            self.dy0 = _series(self.block["dy_ref"], 0.0)
            self.dy1 = _series(self.block["dy_ref"], 1.0)
            self.target0 = _series(self.block["rho_e"], 0.0)
            self.target1 = _series(self.block["rho_e"], 1.0)
            self.interpolate = name == "S3"
            if name == "S2":
                self.forced_events = [{
                    "t": float(self.block.get("forced_event_at", 2.25)),
                    "dy_actual": float(self.block.get("forced_dy", 25.0)),
                    "mode": "actual",
                }]
        self.T_sim = float(params["T_sim"])

    # -- helpers --------------------------------------------------------
    def _frac(self, t: float) -> float:
        if not self.interpolate:
            return 0.0
        return min(max(float(t) / self.T_sim, 0.0), 1.0)

    def lam_s(self, t: float) -> float:
        return self.lam0 + (self.lam1 - self.lam0) * self._frac(t)

    def dy_ref(self, t: float) -> float:
        return self.dy0 + (self.dy1 - self.dy0) * self._frac(t)

    def target_total(self, t: float) -> float:
        return self.target0 + (self.target1 - self.target0) * self._frac(t)

    def rho_storm(self, t: float) -> float:
        mean_dy = self.dy_ref(t) * math.exp(self.sigma_ln ** 2 / 2.0)
        return self.lam_s(t) * mean_dy * self.lam / (self.k + self.lam)

    def rho_scale(self, t: float) -> float:
        """Corridor-mean target minus the scenario's own storm contribution."""
        if self.name == SCENARIO_BASE:
            return 1.0
        if "rho_e_scale" in self.overrides:
            return float(self.overrides["rho_e_scale"])
        return (self.target_total(t) - self.rho_storm(t)) / self.corridor_mean

    def D_factor(self, t: float) -> float:
        if self.name != "S3":
            return 1.0
        trend = float(self.p["Hs_trend"]) / 100.0  # per decade -> fraction
        return (1.0 + trend * float(t) / 10.0) ** 2.5

    def as_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "sigma_ln": self.sigma_ln,
            "lambda_s_0": self.lam0,
            "lambda_s_15": self.lam1,
            "dy_ref_0": self.dy0,
            "dy_ref_15": self.dy1,
            "target_0": self.target0,
            "target_15": self.target1,
            "rho_scale_0": self.rho_scale(0.0),
            "rho_scale_15": self.rho_scale(self.T_sim),
        }


def _series(value: Any, frac: float) -> float:
    if isinstance(value, (list, tuple)):
        if len(value) != 2:
            raise ValueError(f"scenario series must have 2 ends, got {value!r}")
        return float(value[0]) + (float(value[1]) - float(value[0])) * frac
    return float(value)


# ---------------------------------------------------------------------------
# Run configuration
# ---------------------------------------------------------------------------
@dataclass
class RunConfig:
    scenario: str = "S1"
    strategy: str = "none"
    bc: str = "open"
    seed: int = 42
    t_end: float = 5.0
    dx: float = 25.0
    dt: float = 0.02
    Lb: float = 4500.0
    phi_shape: str = "uniform"
    cost_model: str = "all_in"
    supply: str = "local"
    limiter: bool = True
    overrides: Dict[str, Any] = field(default_factory=dict)
    placements: Optional[List[Dict[str, Any]]] = None
    forced_events: List[Dict[str, Any]] = field(default_factory=list)
    dirichlet_yb: Optional[float] = None
    label: str = "run"
    source_config: Optional[str] = None

    def as_dict(self) -> Dict[str, Any]:
        d = dict(self.__dict__)
        d.pop("placements", None)
        return d


def load_config(path: str | Path) -> tuple[Params, Scenario, RunConfig]:
    """Load a ``configs/*.yaml`` file on top of ``modeling/params.yaml``."""
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(path)
    with path.open("r", encoding="utf-8") as fh:
        cfg = yaml.safe_load(fh) or {}
    inherit = cfg.get("inherit", "modeling/params.yaml")
    params_path = (REPO_ROOT / inherit) if not Path(inherit).is_absolute() else Path(inherit)
    params = load_params(params_path)

    overrides = dict(cfg.get("overrides") or {})
    scenario_name = cfg.get("scenario", "S1")
    scenario = Scenario(scenario_name, params, overrides)

    if overrides:
        params = params.clone_with(overrides)
        # rebuild scenario against overridden parameters (k, lambda, ...)
        scenario = Scenario(scenario_name, params, overrides)

    numerics = params.numerics
    run = RunConfig(
        scenario=scenario_name,
        strategy=cfg.get("strategy", "none"),
        bc=cfg.get("bc", "open"),
        seed=int(cfg.get("seed", 42)),
        t_end=float(cfg.get("t_end", numerics.get("t_end", 15.0))),
        dx=float(cfg.get("dx", numerics.get("dx", 25.0))),
        dt=float(cfg.get("dt", numerics.get("dt", 0.02))),
        Lb=float(cfg.get("Lb", params["L_corridor"] / 2.0 + params["L_buffer"])),
        phi_shape=cfg.get("phi_shape", numerics.get("phi_shape", "uniform")),
        cost_model=cfg.get("cost_model", params["cost_model"]),
        supply=cfg.get("supply", params["supply_scenario"]),
        limiter=bool(cfg.get("limiter", True)),
        overrides=overrides,
        placements=cfg.get("placement"),
        forced_events=list(cfg.get("forced_events") or []) + list(scenario.forced_events),
        dirichlet_yb=cfg.get("dirichlet_yb"),
        label=cfg.get("label", path.stem),
        source_config=str(path),
    )
    return params, scenario, run
