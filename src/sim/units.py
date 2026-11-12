# -*- coding: utf-8 -*-
"""The ONE place where shoreline anomaly ``y`` and sand volume ``V`` interconvert.

MODEL_SPEC §2.3::

    V(x,t) = V_0(x) + H * y(x,t)          (absolute stock, m^2 = m^3/m)
    w(x,t) = w_0(x) + y(x,t)              (dry-beach width, m)
    V_min(x) = V_ref - H * w_0(x)

``y`` is the anomaly relative to the 2027 reference shoreline (y(x,0) = 0).
Every other module must call these helpers instead of writing ``H * y`` itself;
CODER_SPEC §2.0 requires that the conversion appear in exactly one place.
"""
from __future__ import annotations

import numpy as np


def w_of_y(y: np.ndarray, w0: np.ndarray) -> np.ndarray:
    return w0 + y


def w_eff_of_y(y: np.ndarray, w0: np.ndarray) -> np.ndarray:
    """Effective (non-negative) dry-beach width used by storm/risk terms."""
    return np.maximum(w0 + y, 0.0)


def V_abs_of_y(y: np.ndarray, V_ref: float, H: float) -> np.ndarray:
    """Algebraic stock; may fall below ``V_min`` (that is what R_c records)."""
    return V_ref + H * y


def V_min_field(w0: np.ndarray, V_ref: float, H: float) -> np.ndarray:
    return V_ref - H * w0


def V_book(y: np.ndarray, V_min: np.ndarray, V_ref: float, H: float) -> np.ndarray:
    """Reported stock, floored at the per-cell minimum."""
    return np.maximum(V_abs_of_y(y, V_ref, H), V_min)


def deficit(y: np.ndarray, V_min: np.ndarray, V_ref: float, H: float) -> np.ndarray:
    """Current unmet deficit R_c = [V_min - V_abs]^+ (recoverable).

    Never use a running maximum here: the peak variant breaks closure once
    nourishment lifts the stock again (PROGRESS Round 17 / D15).
    """
    return np.maximum(V_min - V_abs_of_y(y, V_ref, H), 0.0)


def y_of_V(V: np.ndarray, V_ref: float, H: float) -> np.ndarray:
    return (V - V_ref) / H
