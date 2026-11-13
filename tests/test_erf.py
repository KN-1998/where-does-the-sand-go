"""T2: smooth diffusion limit and grid-refinement convergence."""

import sys
import unittest
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.sim.grid import Grid, backward_euler


class DiffusionLimitTests(unittest.TestCase):
    def _error(self, dx):
        diffusivity = 3.0e5
        sigma = 250.0
        horizon = 0.02
        grid = Grid.build(half_length=4500.0, dx=dx, central_half_length=2500.0)
        y = np.exp(-(grid.x ** 2) / (2.0 * sigma ** 2))
        # Keep the temporal truncation error at the same order as the spatial
        # error so the refinement ratio tests the FV operator, not a time-step
        # artifact.
        dt_target = 2.0e-4 * (dx / 100.0) ** 2
        steps = int(round(horizon / dt_target))
        dt = horizon / steps
        for _ in range(steps):
            y, _ = backward_euler(y, 0.0, dt, grid, diffusivity, 0.0,
                                  "zeroflux")
        variance = sigma ** 2 + 2.0 * diffusivity * horizon
        exact = (sigma / np.sqrt(variance)) * np.exp(-(grid.x ** 2) / (2.0 * variance))
        return float(np.sqrt(np.mean((y - exact) ** 2)))

    def test_gaussian_erf_limit_converges_second_order(self):
        errors = [self._error(dx) for dx in (100.0, 50.0, 25.0)]
        self.assertLess(errors[1] / errors[0], 0.35)
        self.assertLess(errors[2] / errors[1], 0.35)


if __name__ == "__main__":
    unittest.main()
