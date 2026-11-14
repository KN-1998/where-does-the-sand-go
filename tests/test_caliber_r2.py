"""Check the diagnostic's scientific controls against independent expectations."""
from copy import deepcopy
import json
from pathlib import Path
import sys
import unittest

import numpy as np
import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from src.sim.model import ShorelineModel
from tools.caliber_r2 import DiagnosticModel, identity, mean_statistics, resolved_pair


class CaliberR2Tests(unittest.TestCase):
    def test_resolved_snapshots_change_only_storm_switch(self):
        a, b = resolved_pair(42)
        expected = deepcopy(a)
        expected["storm_enabled"] = True
        self.assertEqual(expected, b)
        text_a = yaml.safe_dump(a, allow_unicode=True, sort_keys=False)
        text_b = yaml.safe_dump(b, allow_unicode=True, sort_keys=False)
        self.assertEqual(text_a.replace("storm_enabled: false", "storm_enabled: true"), text_b)
        self.assertEqual(a["scenario"], "L0_diag")
        self.assertEqual(a["bc"], "open")
        self.assertEqual(a["strategy"], "none")
        self.assertEqual(a["t_end"], 15.)

    def test_chronic_field_is_unscaled_and_time_independent_in_both_groups(self):
        for config in resolved_pair(42):
            model = DiagnosticModel(config, 42)
            expected = 1.7 * (1 + 1.2 * np.exp(-model.grid.x**2 / (2 * 600.**2)))
            np.testing.assert_array_equal(model._rho(0.), expected)
            np.testing.assert_array_equal(model._rho(14.9), expected)
            self.assertEqual(model.grid.x.size, 360)
            self.assertEqual(model.grid.central_mask.sum(), 200)
            self.assertEqual(model.grid.dx, 25.)
            self.assertEqual(model.placements, [])

    def test_events_follow_stationary_poisson_lognormal_without_forced_shocks(self):
        a, b = resolved_pair(42)
        self.assertEqual(DiagnosticModel(a, 42).events, [])
        seed = 42
        arrival = np.random.default_rng((seed * 1000003 + 11) % 2**32)
        magnitude = np.random.default_rng((seed * 1000003 + 29) % 2**32)
        expected = []
        time = 0.
        while True:
            time += float(arrival.exponential(1 / .4))
            if time >= 15.:
                break
            expected.append((time, float(magnitude.lognormal(np.log(8.), np.log(25 / 8) / 1.645))))
        events = DiagnosticModel(b, seed).events
        self.assertGreater(len(events), 0)
        self.assertEqual([(event.time, event.potential_retreat) for event in events], expected)
        self.assertTrue(all(not event.forced and event.forced_actual_retreat is None for event in events))

    def test_extension_reuses_frozen_solver_without_altering_dynamics(self):
        config = resolved_pair(42)[1]
        config["t_end"] = 1.
        diagnostic = DiagnosticModel(config, 42)
        reference_params = deepcopy(config)
        reference_params["chronic_mode"] = "observed_direct"
        # Explicit events and observed_direct form an independent existing R2
        # interface for the same physical experiment, without the L0 subclass.
        reference = ShorelineModel(reference_params, scenario="S1", strategy="none",
                                   boundary="open", seed=42, t_end=1., dx=25., dt=.02,
                                   placements=[], events=diagnostic.events)
        actual, expected = diagnostic.run(), reference.run()
        np.testing.assert_array_equal(actual.fields["y"], expected.fields["y"])
        np.testing.assert_array_equal(actual.fields["O"], expected.fields["O"])
        self.assertLess(actual.results["mass"]["residual_rel_max"], 1e-6)
        self.assertLess(actual.results["mass"]["residual_central_rel_max"], 1e-6)

    def test_source_fingerprint_and_sample_mean_error(self):
        frozen = json.loads((ROOT / "CODE_VERSION.json").read_text(encoding="utf-8"))
        self.assertEqual(identity()["source_sha256"], frozen["src_sha256"])
        stats = mean_statistics([1., 2., 3., 4.])
        self.assertEqual(stats["n"], 4)
        self.assertEqual(stats["retreat_mean"], 2.5)
        self.assertAlmostEqual(stats["MCSE"], np.sqrt(5 / 3) / 2)
        self.assertAlmostEqual(stats["CI95"][0], 2.5 - 1.96 * np.sqrt(5 / 3) / 2)


if __name__ == "__main__":
    unittest.main()
