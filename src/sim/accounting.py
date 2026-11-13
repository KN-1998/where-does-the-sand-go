"""Mass-balance diagnostics for domain and central reporting controls."""

import numpy as np

from .units import book_volume, current_deficit


def control_totals(y, offshore, w0, grid, h, v_ref, mask=None):
    if mask is None:
        mask = np.ones(y.size, dtype=bool)
    v = book_volume(y, w0, h, v_ref)
    deficit = current_deficit(y, w0, h, v_ref)
    return {
        "V_delta": float(((v[mask] - v_ref).sum()) * grid.dx),
        "O": float(offshore[mask].sum() * grid.dx),
        "deficit": float(deficit[mask].sum() * grid.dx),
    }


def residual(placed, flux_out, offshore_loss, chronic_loss, current_total,
             initial_total, deficit, initial_deficit):
    delta_total = current_total - initial_total
    return float(placed - flux_out - offshore_loss - chronic_loss
                 - delta_total + deficit - initial_deficit)


def relative_residual(value, placed):
    return abs(float(value)) / max(1.0, abs(float(placed)))
