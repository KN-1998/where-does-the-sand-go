"""Cell-centered grid and conservative backward-Euler transport step."""

from dataclasses import dataclass

import numpy as np
from scipy.linalg import solve_banded


@dataclass(frozen=True)
class Grid:
    x: np.ndarray
    dx: float
    half_length: float
    central_half_length: float

    @classmethod
    def build(cls, half_length=4500.0, dx=25.0, central_half_length=2500.0):
        if dx <= 0 or half_length <= 0 or not 0 < central_half_length <= half_length:
            raise ValueError("grid lengths must be positive; reporting domain must lie inside full domain")
        n_float = 2.0 * half_length / dx
        c_float = 2.0 * central_half_length / dx
        if dx <= 0 or abs(n_float - round(n_float)) > 1e-10:
            raise ValueError("dx must divide the full domain into whole cells")
        if abs(c_float - round(c_float)) > 1e-10:
            raise ValueError("dx must divide the central reporting domain into whole cells")
        n = int(round(n_float))
        x = -half_length + dx / 2.0 + dx * np.arange(n, dtype=np.float64)
        return cls(x=x, dx=float(dx), half_length=float(half_length),
                   central_half_length=float(central_half_length))

    @property
    def central_mask(self):
        return np.abs(self.x) < self.central_half_length

    @property
    def length(self):
        return self.x.size * self.dx


def thomas(lower, diagonal, upper, rhs):
    """Solve a tridiagonal system; off-diagonal arrays have length n-1."""
    n = len(diagonal)
    c = np.zeros(n, dtype=np.float64)
    d = np.zeros(n, dtype=np.float64)
    c[0] = upper[0] / diagonal[0] if n > 1 else 0.0
    d[0] = rhs[0] / diagonal[0]
    for i in range(1, n):
        pivot = diagonal[i] - lower[i - 1] * c[i - 1]
        if abs(pivot) < 1e-30:
            raise ArithmeticError("singular tridiagonal system")
        d[i] = (rhs[i] - lower[i - 1] * d[i - 1]) / pivot
        c[i] = upper[i] / pivot if i < n - 1 else 0.0
    out = np.empty(n, dtype=np.float64)
    out[-1] = d[-1]
    for i in range(n - 2, -1, -1):
        out[i] = d[i] - c[i] * out[i + 1]
    return out


def _face_coefficients(n, dx, diffusivity, drift, boundary, y_boundary):
    if boundary not in {"zeroflux", "open", "dirichlet"}:
        raise ValueError(f"unsupported boundary condition: {boundary}")
    if boundary == "dirichlet" and y_boundary is None:
        raise ValueError("dirichlet boundary requires an explicit y_boundary")

    left = np.zeros(n + 1, dtype=np.float64)
    right = np.zeros(n + 1, dtype=np.float64)
    constant = np.zeros(n + 1, dtype=np.float64)
    d = diffusivity / dx

    left[1:n] = max(drift, 0.0) + d
    right[1:n] = min(drift, 0.0) - d

    if boundary == "open":
        # Zero diffusive gradient; extrapolate the nearest interior value for inflow.
        right[0] = drift
        left[n] = drift
    elif boundary == "dirichlet":
        boundary_values = np.asarray(y_boundary, dtype=np.float64)
        if boundary_values.ndim == 0:
            yl = yr = float(boundary_values)
        elif boundary_values.size == 2:
            yl, yr = boundary_values.reshape(2)
        else:
            raise ValueError("dirichlet y_boundary must be a scalar or pair")
        if drift >= 0.0:
            right[0] = -drift - 2.0 * d
            constant[0] = 2.0 * (drift + d) * yl
        else:
            right[0] = drift - 2.0 * d
            constant[0] = 2.0 * d * yl
        if drift >= 0.0:
            left[n] = drift + 2.0 * d
            constant[n] = -2.0 * d * yr
        else:
            left[n] = -drift + 2.0 * d
            constant[n] = 2.0 * (drift - d) * yr
    return left, right, constant


def face_fluxes(y, grid, diffusivity, drift, boundary="zeroflux", y_boundary=None):
    y = np.asarray(y, dtype=np.float64)
    left, right, constant = _face_coefficients(
        y.size, grid.dx, diffusivity, drift, boundary, y_boundary)
    flux = constant.copy()
    flux[0] += right[0] * y[0]
    flux[-1] += left[-1] * y[-1]
    if y.size > 1:
        flux[1:-1] += left[1:-1] * y[:-1] + right[1:-1] * y[1:]
    return flux


def backward_euler(y, source, dt, grid, diffusivity, drift=0.0,
                   boundary="zeroflux", y_boundary=None):
    """Advance y_t = -dF/dx + source and return y_next and face fluxes."""
    y = np.asarray(y, dtype=np.float64)
    source = np.broadcast_to(np.asarray(source, dtype=np.float64), y.shape)
    if dt <= 0 or diffusivity < 0:
        raise ValueError("dt must be positive and diffusivity nonnegative")
    n = y.size
    left, right, constant = _face_coefficients(
        n, grid.dx, diffusivity, drift, boundary, y_boundary)
    inv_dx = 1.0 / grid.dx
    op_diag = (right[:-1] - left[1:]) * inv_dx
    op_lower = left[1:-1] * inv_dx
    op_upper = -right[1:-1] * inv_dx
    boundary_source = (constant[:-1] - constant[1:]) * inv_dx
    diagonal = 1.0 - dt * op_diag
    lower = -dt * op_lower
    upper = -dt * op_upper
    rhs = y + dt * (source + boundary_source)
    bands = np.zeros((3, n))
    bands[0, 1:] = upper
    bands[1] = diagonal
    bands[2, :-1] = lower
    y_next = solve_banded((1, 1), bands, rhs, check_finite=False)
    flux = face_fluxes(y_next, grid, diffusivity, drift, boundary, y_boundary)
    return y_next, flux


def limited_transport(y, source, w0, dt, grid, diffusivity, drift,
                      boundary, y_boundary=None):
    """BE candidate flux, then conservative donor-stock limiting.

    Each face has one realized flux. Outgoing volume cannot exceed the
    donor's mobile beach stock; existing source-created deficit is retained.
    Incoming volume is deliberately not borrowed to fund same-step outflow.
    The limiter is first order and its activity is reported for sensitivity.
    """
    _, flux = backward_euler(y, source, dt, grid, diffusivity, drift,
                             boundary, y_boundary)
    outgoing = dt * (np.maximum(flux[1:], 0) + np.maximum(-flux[:-1], 0))
    source = np.broadcast_to(np.asarray(source, dtype=np.float64), y.shape)
    source_state = y + dt * source
    available = np.maximum(w0 + source_state, 0.0) * grid.dx
    scale = np.minimum(1.0, np.divide(available, outgoing,
                       out=np.ones_like(available), where=outgoing > 0))
    if np.all(scale >= 1.0 - 1e-13):
        return source_state + dt / grid.dx * (flux[:-1] - flux[1:]), flux, 0
    factors = np.ones_like(flux)
    factors[1:] = np.where(flux[1:] > 0, scale, factors[1:])
    factors[:-1] = np.where(flux[:-1] < 0, scale, factors[:-1])
    actual = flux * factors
    out = source_state + dt / grid.dx * (actual[:-1] - actual[1:])
    if np.any(np.maximum(-out-w0, 0) > np.maximum(-source_state-w0, 0) + 1e-9):
        raise ArithmeticError("transport increased the source-created deficit")
    return out, actual, int(np.count_nonzero(factors < 1.0 - 1e-13))
