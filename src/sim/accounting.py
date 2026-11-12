# -*- coding: utf-8 -*-
"""Sand ledger and mass-closure identity (CODER_SPEC §4.3, MODEL_SPEC §3.6).

Closure (full 9 km domain)::

    placed_cum = (V_book + O)_domain + flux_outer_left + flux_outer_right
                 + offshore_loss_cum + chronic_loss_cum - (R_c_cum - R_c_start)

with ``V_book = V_abs + R_c``.  Since ``V_domain`` in the CSV is the *increment of
V_abs* (``H * sum(y))``), the identity that is actually evaluated is::

    placed_cum = V_domain + O_domain + flux_out + offshore + chronic_loss

(the ``R_c`` terms cancel algebraically; they are kept in the code so the ledger
reads like the contract and a sign error is impossible to hide).

Units: ``F`` is m^2/yr, so a boundary volume over a step is ``H * F * dt`` (m^3).
Outflow is positive: left outflow = ``-F(0)``, right outflow = ``+F(L)``.
"""
from __future__ import annotations

import csv
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List

REQUIRED_COLUMNS = [
    "t", "V_central", "O_central", "V_domain", "O_domain", "R_c_cum",
    "placed_cum", "flux_inner_left_cum", "flux_inner_right_cum",
    "flux_outer_left_cum", "flux_outer_right_cum",
    "offshore_loss_cum", "chronic_loss_cum", "storm_injected_cum",
    "recovery_cum", "residual", "residual_rel",
]
DIAGNOSTIC_COLUMNS = ["D_max_cum", "Q_limited_cum", "n_events_applied"]
COLUMNS = REQUIRED_COLUMNS + DIAGNOSTIC_COLUMNS


def closure(placed_cum: float, V_domain: float, O_domain: float,
            R_c_cum: float, R_c_start: float,
            flux_left: float, flux_right: float,
            offshore: float, chronic: float) -> tuple[float, float, float]:
    """Return ``(residual, residual_rel, rhs)`` for the documented identity."""
    V_book = V_domain + (R_c_cum - R_c_start)
    rhs_doc = (V_book + O_domain + flux_left + flux_right
               + offshore + chronic - (R_c_cum - R_c_start))
    # algebraically equal to V_domain + O_domain + flux + offshore + chronic
    residual = placed_cum - rhs_doc
    scale = max(1.0, abs(placed_cum))
    return residual, residual / scale, rhs_doc


@dataclass
class Ledger:
    """Row store; one row per accepted time level (including t=0)."""

    rows: List[Dict[str, float]] = field(default_factory=list)

    def add(self, **kwargs) -> Dict[str, float]:
        row = {k: float(kwargs[k]) for k in COLUMNS}
        self.rows.append(row)
        return row

    @property
    def max_abs_rel(self) -> float:
        return max((abs(r["residual_rel"]) for r in self.rows), default=0.0)

    def write(self, path: str | Path) -> None:
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", newline="", encoding="utf-8") as fh:
            writer = csv.DictWriter(fh, fieldnames=COLUMNS)
            writer.writeheader()
            for row in self.rows:
                writer.writerow(row)
