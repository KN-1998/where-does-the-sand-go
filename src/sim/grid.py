# -*- coding: utf-8 -*-
"""Cell-centred finite-volume grid and the implicit transport operator.

Discretisation (MODEL_SPEC §3.1-§3.2, CODER_SPEC §2.2)::

    dy_i/dt = (F_i - F_{i+1}) / dx + sources_i
    F_j     = u * y_upwind - D * (y_j - y_{j-1}) / dx      (face j, between j-1 and j)

Face «j» is the LEFT face of cell «j».  Backward Euler gives a tridiagonal system
``A y^{n+1} = rhs``.  The operator is assembled in flux form, so

    sum_i (dy_i/dt) * dx = F_0 - F_N

holds exactly: the only leak is the boundary flux, which the ledger records.

Boundary conditions (MODEL_SPEC §4, CODER_SPEC §2.6)
----------------------------------------------------
* ``zeroflux``  : F_0 = F_N = 0 (both diffusion and advection).
* ``open``      : ghost = adjacent interior value.  Diffusion flux is zero at the
                  face; advection keeps the upwind state, so F = u * y_boundary.
* ``dirichlet`` : physical face value y_b, ghost = 2*y_b - y_interior.

Flux limiter (§2.4c)
--------------------
A cell at or below ``V_min`` has no sand to export.  Faces that would export sand
from such a cell are set to zero *before* the solve (a barrier).  Because a blocked
face is shared by exactly two cells, the discrete conservation identity is untouched;
only the actual (recorded) flux changes.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Tuple

import numpy as np
from scipy.linalg import solve_banded

BCS = ("open", "zeroflux", "dirichlet")


def thomas(a: np.ndarray, b: np.ndarray, c: np.ndarray, d: np.ndarray) -> np.ndarray:
    """Classic Thomas algorithm.  ``a`` has length n-1 (sub), ``c`` length n-1 (sup).

    Kept as an independent reference used by tests/test_mass.py; production runs
    use :func:`solve_tridiag` (LAPACK banded solve).
    """
    n = len(b)
    cp = np.zeros(n)
    dp = np.zeros(n)
    cp[0] = c[0] / b[0] if n > 1 else 0.0
    dp[0] = d[0] / b[0]
    for i in range(1, n):
        m = b[i] - a[i - 1] * cp[i - 1]
        dp[i] = (d[i] - a[i - 1] * dp[i - 1]) / m
        cp[i] = (c[i] / m) if i < n - 1 else 0.0
    x = np.zeros(n)
    x[-1] = dp[-1]
    for i in range(n - 2, -1, -1):
        x[i] = dp[i] - cp[i] * x[i + 1]
    return x


def solve_tridiag(lower: np.ndarray, main: np.ndarray, upper: np.ndarray,
                  rhs: np.ndarray) -> np.ndarray:
    """Solve a tridiagonal system with LAPACK (``solve_banded``)."""
    n = len(main)
    ab = np.zeros((3, n), dtype=np.float64)
    ab[0, 1:] = upper
    ab[1, :] = main
    ab[2, :-1] = lower
    return solve_banded((1, 1), ab, rhs, overwrite_ab=False, overwrite_b=False,
                        check_finite=False)


@dataclass
class Grid:
    """Uniform cell-centred grid on ``[-Lb, Lb]``."""

    Lb: float = 4500.0
    dx: float = 25.0

    def __post_init__(self) -> None:
        self.dx = float(self.dx)
        self.Lb = float(self.Lb)
        length = 2.0 * self.Lb
        nx = int(round(length / self.dx))
        if abs(nx * self.dx - length) > 1e-9:
            raise ValueError(
                f"dx={self.dx} does not divide 2*Lb={length} exactly "
                f"({length / self.dx:.6f} cells)"
            )
        self.nx = nx
        self.x = -self.Lb + self.dx / 2.0 + self.dx * np.arange(nx)
        # faces: x_face[j] = -Lb + j*dx, j = 0..nx
        self.x_face = -self.Lb + self.dx * np.arange(nx + 1)
        self.L_central = 5000.0
        self.central = np.abs(self.x) <= self.L_central / 2.0 + 1e-12
        self.n_central = int(self.central.sum())
        if self.Lb >= self.L_central / 2.0:
            if abs(self.n_central * self.dx - self.L_central) > 1e-9:
                raise ValueError(
                    f"central 5 km is not resolved by dx={self.dx} "
                    f"({self.n_central} cells = {self.n_central * self.dx} m)"
                )
        else:  # small test domain: the whole grid plays the role of the corridor
            self.central = np.ones(nx, dtype=bool)
            self.n_central = nx
            self.L_central = nx * self.dx
        j = int(round((self.Lb - self.L_central / 2.0) / self.dx))
        self.j_central_left = j
        self.j_central_right = nx - j
        self.idx_central_left = int(np.flatnonzero(self.central)[0])
        self.idx_central_right = int(np.flatnonzero(self.central)[-1])

    @property
    def length(self) -> float:
        return self.nx * self.dx

    def summary(self) -> dict:
        return {
            "nx": self.nx,
            "dx": self.dx,
            "Lb": self.Lb,
            "length": self.length,
            "n_central": self.n_central,
            "x_min": float(self.x[0]),
            "x_max": float(self.x[-1]),
        }


# ---------------------------------------------------------------------------
# Fields on the grid
# ---------------------------------------------------------------------------
def w0_field(x: np.ndarray, w_far: float, w_min: float, sigma_w: float) -> np.ndarray:
    """Initial dry-beach width field (ASSUME hotspot; MODEL_SPEC §4)."""
    return w_far - (w_far - w_min) * np.exp(-x ** 2 / (2.0 * sigma_w ** 2))


def rho_field(x: np.ndarray, rho0: float, a_h: float, sigma_h: float,
              x_h: float = 0.0) -> np.ndarray:
    """Observed long-term erosion field (MODEL_SPEC §3.5)."""
    return rho0 * (1.0 + a_h * np.exp(-(x - x_h) ** 2 / (2.0 * sigma_h ** 2)))


# ---------------------------------------------------------------------------
# Implicit transport operator
# ---------------------------------------------------------------------------
class Transport:
    """Flux-form diffusion + upwind advection, backward Euler, 1-D.

    Parameters that do not change during a run are stored here; ``D`` may be
    time dependent (S3 wave-climate channel), so it is passed per call.
    """

    def __init__(self, grid: Grid, u: float, bc: str):
        if bc not in BCS:
            raise ValueError(f"unknown bc {bc!r}; expected one of {BCS}")
        self.grid = grid
        self.u = float(u)
        self.bc = bc

    # -- helper: interior face coefficients -----------------------------
    def _interior_coeffs(self, D: float) -> Tuple[np.ndarray, np.ndarray]:
        g = self.grid
        r = D / g.dx
        nf = g.nx - 1
        alpha = np.full(nf, r)
        beta = np.full(nf, -r)
        if self.u >= 0.0:
            alpha += self.u
        else:
            beta += self.u
        return alpha, beta

    def _face_flux_prev(self, y: np.ndarray, D: float) -> np.ndarray:
        """Signed face fluxes evaluated on ``y`` (length nx+1); used for the limiter."""
        g = self.grid
        F = np.zeros(g.nx + 1)
        dydx = np.diff(y) / g.dx
        if self.u >= 0.0:
            F[1:-1] = self.u * y[:-1] - D * dydx
        else:
            F[1:-1] = self.u * y[1:] - D * dydx
        if self.bc == "open":
            F[0] = self.u * y[0]
            F[-1] = self.u * y[-1]
        elif self.bc == "dirichlet":
            # placeholder: the value does not matter for the barrier direction
            # except at the boundary cells, handled below
            F[0] = self.u * y[0]
            F[-1] = self.u * y[-1]
        return F

    def assemble(self, dt: float, y_prev: np.ndarray, D: float,
                 barrier: Optional[np.ndarray] = None,
                 yb_left: float = 0.0, yb_right: float = 0.0
                 ) -> dict:
        """Assemble ``A y = rhs`` for transport only (rhs-constant returned).

        Returns a dict with ``lower/main/upper`` and the constant shift that the
        caller must add to ``rhs`` (Dirichlet faces), plus blocked-face masks.
        """
        g = self.grid
        n = g.nx
        lower = np.zeros(n - 1)
        main = np.ones(n)
        upper = np.zeros(n - 1)
        const = np.zeros(n)  # transported to rhs as +const
        alpha, beta = self._interior_coeffs(D)
        k = dt / g.dx

        F = self._face_flux_prev(y_prev, D)
        barrier = np.zeros(n, dtype=bool) if barrier is None else np.asarray(barrier, bool)
        blocked_int = np.zeros(n - 1, dtype=bool)
        if barrier.any():
            blocked_int = ((barrier[:-1] & (F[1:-1] > 0.0)) |
                           (barrier[1:] & (F[1:-1] < 0.0)))
        mask = ~blocked_int

        # interior faces j=1..n-1 -> arrays index k=0..n-2
        main[:-1] += k * alpha * mask
        upper += k * beta * mask
        lower -= k * alpha * mask
        main[1:] -= k * beta * mask

        # left boundary face (j=0): only affects row 0 with -dt*F_0/dx
        b0_blocked = False
        if self.bc == "zeroflux":
            beta0 = gamma0 = 0.0
        elif self.bc == "open":
            beta0, gamma0 = self.u, 0.0
        else:  # dirichlet
            beta0 = -2.0 * D / g.dx + (-self.u if self.u > 0.0 else self.u)
            gamma0 = 2.0 * D * yb_left / g.dx + (2.0 * self.u * yb_left if self.u > 0.0 else 0.0)
        if barrier[0] and F[0] < 0.0:  # would export sand through the left face
            b0_blocked = True
            beta0 = gamma0 = 0.0
        main[0] -= k * beta0
        const[0] += k * gamma0

        # right boundary face (j=n): only affects row n-1 with +dt*F_n/dx
        bn_blocked = False
        if self.bc == "zeroflux":
            alpha_n = gamma_n = 0.0
        elif self.bc == "open":
            alpha_n, gamma_n = self.u, 0.0
        else:
            if self.u > 0.0:
                alpha_n = self.u + 2.0 * D / g.dx
                gamma_n = -2.0 * D * yb_right / g.dx
            else:
                alpha_n = -self.u + 2.0 * D / g.dx
                gamma_n = 2.0 * self.u * yb_right - 2.0 * D * yb_right / g.dx
        if barrier[-1] and F[-1] > 0.0:  # would export sand through the right face
            bn_blocked = True
            alpha_n = gamma_n = 0.0
        main[-1] += k * alpha_n
        const[-1] -= k * gamma_n

        return {
            "lower": lower,
            "main": main,
            "upper": upper,
            "const": const,
            "blocked_int": blocked_int,
            "blocked_left": b0_blocked,
            "blocked_right": bn_blocked,
        }

    # -- after the solve -------------------------------------------------
    def face_fluxes(self, y: np.ndarray, D: float, sys: Optional[dict] = None,
                    yb_left: float = 0.0, yb_right: float = 0.0) -> np.ndarray:
        """Signed face fluxes ``F_j`` (m^2/yr) for the accepted solution."""
        g = self.grid
        F = np.zeros(g.nx + 1)
        dydx = np.diff(y) / g.dx
        if self.u >= 0.0:
            F[1:-1] = self.u * y[:-1] - D * dydx
        else:
            F[1:-1] = self.u * y[1:] - D * dydx
        if sys is not None:
            F[1:-1][sys["blocked_int"]] = 0.0
        if self.bc == "zeroflux":
            F[0] = 0.0
            F[-1] = 0.0
        elif self.bc == "open":
            F[0] = self.u * y[0]
            F[-1] = self.u * y[-1]
            if sys is not None and sys["blocked_left"]:
                F[0] = 0.0
            if sys is not None and sys["blocked_right"]:
                F[-1] = 0.0
        else:  # dirichlet
            ghost_l = 2.0 * yb_left - y[0]
            ghost_r = 2.0 * yb_right - y[-1]
            F[0] = (self.u * (ghost_l if self.u > 0.0 else y[0])
                    - D * (y[0] - ghost_l) / g.dx)
            F[-1] = (self.u * (y[-1] if self.u > 0.0 else ghost_r)
                     - D * (ghost_r - y[-1]) / g.dx)
            if sys is not None and sys["blocked_left"]:
                F[0] = 0.0
            if sys is not None and sys["blocked_right"]:
                F[-1] = 0.0
        return F

    def limited_volume(self, y: np.ndarray, D: float, sys: dict, dt: float,
                       H: float) -> float:
        """Diagnostic: volume (m^3) that the limiter refused to move this step."""
        g = self.grid
        if sys is None:
            return 0.0
        F = self.face_fluxes(y, D, sys=None)
        vol = 0.0
        if sys["blocked_int"].any():
            vol += float(np.abs(F[1:-1][sys["blocked_int"]]).sum()) * dt * H
        if sys["blocked_left"]:
            vol += abs(float(F[0])) * dt * H
        if sys["blocked_right"]:
            vol += abs(float(F[-1])) * dt * H
        return vol
