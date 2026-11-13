"""Conversions between shoreline anomaly and the modeled beach inventory."""

import numpy as np


def absolute_volume(y, h, v_ref):
    return v_ref + h * np.asarray(y, dtype=np.float64)


def minimum_volume(w0, h, v_ref):
    return v_ref - h * np.asarray(w0, dtype=np.float64)


def book_volume(y, w0, h, v_ref):
    v_abs = absolute_volume(y, h, v_ref)
    v_min = minimum_volume(w0, h, v_ref)
    return np.maximum(v_abs, v_min)


def current_deficit(y, w0, h, v_ref):
    return np.maximum(minimum_volume(w0, h, v_ref) - absolute_volume(y, h, v_ref), 0.0)
