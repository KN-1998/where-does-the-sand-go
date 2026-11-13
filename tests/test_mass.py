"""Executable first gate: T1/T3/T13 for the production model."""

import sys
import unittest
import copy
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.sim.grid import Grid, backward_euler, face_fluxes, limited_transport
from src.sim.io import load_config
from src.sim.model import ShorelineModel
from src.sim.strategies import Placement
from src.sim.storms import StormEvent


class MassTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.params = load_config(ROOT / "configs" / "base.yaml")

    def test_grid_and_zero_source(self):
        grid = Grid.build()
        self.assertEqual(grid.x.size, 360)
        self.assertAlmostEqual(grid.length, 9000.0)
        y = np.full(grid.x.size, 3.0)
        out, _ = backward_euler(y, 0.0, 0.02, grid, 300000.0, 0.0, "zeroflux")
        self.assertLess(np.max(np.abs(out - y)), 1e-12)

    def test_t1_closure(self):
        model = ShorelineModel(self.params, scenario="S1", boundary="zeroflux",
                               t_end=5.0, seed=42)
        result = model.run()
        self.assertLess(result.results["mass"]["residual_rel_max"], 1e-6)

    def test_open_boundary_model_closes_with_recorded_outflow(self):
        model = ShorelineModel(self.params, scenario="S1", boundary="open",
                               t_end=2.0, seed=42)
        result = model.run()
        self.assertLess(result.results["mass"]["residual_rel_max"], 1e-6)
        self.assertGreater(abs(result.results["mass"]["flux_out"]), 0.0)

    def test_t13_refill(self):
        placement = Placement(5.0, 1.5e7, 0.0, 5000.0, "refill")
        model = ShorelineModel(self.params, scenario="S1", boundary="zeroflux",
                               t_end=10.0, dt=0.02, seed=42,
                               rho_override=12.0, placements=[placement])
        result = model.run()
        self.assertLess(result.results["mass"]["residual_rel_max"], 1e-6)
        self.assertLess(result.ledger[-1]["R_c_cum"], result.ledger[250]["R_c_cum"])

    def test_terminal_storm_is_applied_and_recorded_once(self):
        event = StormEvent(1.0, 0.0, forced_actual_retreat=1.0, forced=True)
        model = ShorelineModel(self.params, scenario="S1", boundary="zeroflux",
                               t_end=1.0, dt=0.02, events=[event])
        result = model.run()
        self.assertEqual(result.results["events"]["n_events_applied"], 1)
        record = result.event_records[0]
        self.assertAlmostEqual(record["t"], 1.0)
        self.assertAlmostEqual(record["injected_full_m3"],
                               result.fields["O"][-1].sum() * model.grid.dx)
        self.assertAlmostEqual(record["injected_central_m3"],
                               result.fields["O"][-1, model.grid.central_mask].sum() * model.grid.dx)
        self.assertLess(result.results["mass"]["residual_rel_max"], 1e-6)

    def test_s3_wave_trend_changes_diffusivity(self):
        model = ShorelineModel(self.params, scenario="S3", t_end=15.0)
        expected = model.diffusivity * (1.0 + 0.03 * 15.0 / 10.0) ** 2.5
        self.assertAlmostEqual(model._diffusivity(15.0), expected, places=9)
        self.assertEqual(ShorelineModel(self.params, scenario="S1")._diffusivity(15.0),
                         model.diffusivity)

    def test_s3_interpolation_uses_fixed_15_year_horizon(self):
        short = ShorelineModel(self.params, scenario="S3", t_end=5.0)
        full = ShorelineModel(self.params, scenario="S3", t_end=15.0)
        np.testing.assert_allclose(short._rho(5.0), full._rho(5.0))

    def test_direct_strategy_respects_local_supply_cap(self):
        model = ShorelineModel(self.params, scenario="S1", strategy="uniform",
                               t_end=0.1, storm_enabled=False)
        self.assertEqual(len(model.placements), 1)
        self.assertAlmostEqual(model.placements[0].volume, 2.45e6)

    def test_adaptive_is_executable_and_dirichlet_requires_values(self):
        adaptive = ShorelineModel(self.params, scenario="S1", strategy="adaptive",
                                  t_end=1.0, storm_enabled=False)
        result = adaptive.run()
        self.assertIn("adaptive_decisions", result.results["placements"])
        with self.assertRaisesRegex(ValueError, "explicit adjacent-shoreline"):
            ShorelineModel(self.params, scenario="S1", boundary="dirichlet")

    def test_adaptive_does_not_spend_on_zero_building_benefit(self):
        params = copy.deepcopy(self.params)
        params["management"]["delta_f_trig"]["value"] = 0.01
        params["management"]["sigma_m"]["value"] = 0.0
        params["beach_state"]["w_mgmt"]["value"] = 16.5
        params["scenarios"]["S1_calm"]["rho_e"] = 0.5
        result = ShorelineModel(params, scenario="S1", strategy="adaptive",
                                t_end=15.0, storm_enabled=False).run()
        decisions = result.results["placements"]["adaptive_decisions"]
        approvals = [item for item in decisions if item["action"] == "approve"]
        self.assertEqual(len(approvals), 0)
        self.assertEqual(result.results["mass"]["placed"], 0.)

    def test_strategy_runs_share_scenario_event_table(self):
        baseline = ShorelineModel(self.params, scenario="S2", strategy="none",
                                  t_end=5.0, seed=42)
        intervention = ShorelineModel(self.params, scenario="S2", strategy="once",
                                      t_end=5.0, seed=42)
        self.assertEqual(baseline.events, intervention.events)

    def test_historical_deficit_uses_unclipped_shoreline(self):
        model = ShorelineModel(self.params, scenario="S1", t_end=1.0,
                               storm_enabled=False, rho_override=12.0)
        result = model.run()
        raw_w = result.fields["w"]
        expected = float(np.max(np.maximum(-raw_w, 0.0).sum(axis=1) * model.h * model.grid.dx))
        self.assertAlmostEqual(result.results["mass"]["D_max_cum"], expected)

    def test_exposure_and_cost_fields_are_computed(self):
        model = ShorelineModel(self.params, scenario="S1", strategy="uniform",
                               t_end=0.1, storm_enabled=False)
        result = model.run().results
        self.assertGreaterEqual(result["exposure"]["E_w"], 0.0)
        self.assertLessEqual(result["exposure"]["E_w"], 5000.0 * 0.1)
        self.assertEqual(result["cost"]["n_projects"], 1)
        self.assertAlmostEqual(result["cost"]["cost_used"], 2.45e6 * 27.0)

    def test_initial_metric_fractions_follow_length_weighted_definition(self):
        result = ShorelineModel(self.params, scenario="S1", t_end=0.1,
                                storm_enabled=False).run().results
        self.assertAlmostEqual(result["initial"]["f_w0"], 0.3036, delta=0.01)
        self.assertAlmostEqual(result["initial"]["f_b0"], 0.0, delta=1e-12)

    def test_single_storm_recovery_fraction(self):
        event = StormEvent(0.0, 0.0, forced_actual_retreat=2.0, forced=True)
        model = ShorelineModel(self.params, scenario="S1", t_end=20.0,
                               dt=0.02, rho_override=0.0, events=[event])
        result = model.run().results
        fraction = result["mass"]["recovery"] / result["mass"]["storm_injected"]
        expected = float(model.k / (model.k + model.lam))
        self.assertAlmostEqual(fraction, expected, delta=1e-3)

    def test_recovery_metric_reports_recovery_and_right_censoring(self):
        event = StormEvent(0.5, 0.0, forced_actual_retreat=25.0, forced=True)
        recovered = ShorelineModel(self.params, scenario="S1", t_end=20.0,
                                   dt=0.02, rho_override=0.0, events=[event]).run()
        rw = recovered.results["duration"]["T_recovery_w"]
        self.assertGreater(rw["n"], 0)
        self.assertFalse(rw["censored"])
        self.assertGreater(rw["value"], 0.0)

        censored = ShorelineModel(self.params, scenario="S1", t_end=1.0,
                                  dt=0.02, rho_override=0.0, events=[event]).run()
        rw_short = censored.results["duration"]["T_recovery_w"]
        self.assertGreater(rw_short["n"], 0)
        self.assertTrue(rw_short["censored"])
        self.assertIsNone(rw_short["value"])

    def test_non_grid_event_is_applied_once(self):
        event = StormEvent(1.01, 0.0, forced_actual_retreat=1.0, forced=True)
        model = ShorelineModel(self.params, scenario="S1", t_end=1.01,
                               dt=0.02, rho_override=0.0, events=[event])
        result = model.run()
        self.assertEqual(result.results["events"]["n_events_applied"], 1)
        self.assertAlmostEqual(result.event_records[0]["t"], 1.01)

    def test_open_boundary_has_outflow_and_zeroflux_does_not(self):
        grid = Grid.build()
        y = np.exp(-((grid.x - 3900.0) ** 2) / (2.0 * 200.0 ** 2))
        _, open_flux = backward_euler(y, 0.0, 0.01, grid, 300000.0, 50.0, "open")
        _, closed_flux = backward_euler(y, 0.0, 0.01, grid, 300000.0, 50.0, "zeroflux")
        open_out = -10.0 * open_flux[0] * 0.01 + 10.0 * open_flux[-1] * 0.01
        closed_out = -10.0 * closed_flux[0] * 0.01 + 10.0 * closed_flux[-1] * 0.01
        self.assertGreater(open_out, 0.0)
        self.assertAlmostEqual(closed_out, 0.0, delta=1e-10)

    def test_dirichlet_constant_boundary_preserves_constant_state(self):
        grid = Grid.build(half_length=50.0, dx=10.0, central_half_length=20.0)
        y = np.full(grid.x.size, 3.0)
        out, flux = backward_euler(y, 0.0, 0.1, grid, 300000.0, 50.0,
                                   "dirichlet", [3.0, 3.0])
        np.testing.assert_allclose(out, y, atol=1e-12)
        # A uniform advective state has nonzero through-flux u*y, but zero
        # divergence; the state and net boundary balance remain unchanged.
        np.testing.assert_allclose(flux, 150.0, atol=1e-10)

    def test_dirichlet_flux_signs_match_inward_boundary_convention(self):
        grid = Grid.build(half_length=50.0, dx=10.0, central_half_length=20.0)
        y = np.zeros(grid.x.size)
        _, flux = backward_euler(y, 0.0, 0.1, grid, 1.0, 0.0,
                                "dirichlet", [1.0, 2.0])
        self.assertGreater(flux[0], 0.0)
        self.assertLess(flux[-1], 0.0)

    def test_limiter_does_not_move_more_than_donor_stock(self):
        grid = Grid.build(half_length=50.0, dx=10.0, central_half_length=20.0)
        y = np.array([0.0, 0.0, 0.0, 0.0, 1.0])
        w0 = np.zeros(5)
        out, flux, limited = limited_transport(y, 0.0, w0, 1.0, grid,
                                                0.0, 1e8, "open")
        self.assertGreater(limited, 0)
        self.assertGreaterEqual(np.min(w0 + out), -1e-10)
        self.assertLess(float(np.sum(out-y)*grid.dx), 0.0)
        self.assertAlmostEqual(float(np.sum(out-y)*grid.dx),
                               float((flux[0]-flux[-1])*1.0), places=9)

    def test_same_seed_and_events_are_reproducible(self):
        events = [StormEvent(0.37, 3.0)]
        first = ShorelineModel(self.params, scenario="S1", t_end=1.0,
                               events=events).run()
        second = ShorelineModel(self.params, scenario="S1", t_end=1.0,
                                events=events).run()
        self.assertEqual(first.results, second.results)
        np.testing.assert_array_equal(first.fields["y"], second.fields["y"])

    def test_nonzero_restart_state_has_correct_initial_ledger(self):
        y=np.full(360,-40.);o=np.full(360,25.)
        result=ShorelineModel(self.params,scenario='S1',events=[],initial_y=y,
            initial_o=o,t_start=2.,t_end=3.,rho_override=0.).run()
        self.assertEqual(result.fields['t'][0],2.)
        self.assertAlmostEqual(result.ledger[0]['residual'],0.)
        self.assertLess(result.results['mass']['residual_rel_max'],1e-6)

    def test_same_time_storm_then_placement_preserves_instant_failure(self):
        p=copy.deepcopy(self.params)
        p['beach_state']['w0_far']['value']=25.
        p['beach_state']['w0_min']['value']=25.
        r=ShorelineModel(p,scenario='S1',events=[StormEvent(1.,100.)],
            placements=[Placement(1.,5e6,0.,5000.)],t_end=1.,rho_override=0.).run()
        self.assertAlmostEqual(r.results['exposure']['E_w'],0.)
        self.assertEqual(r.results['duration']['T_first_fail_w']['value'],1.)
        self.assertTrue(np.all(r.fields['w'][-1,np.abs(r.fields['x'])<2500]>20.))


if __name__ == "__main__":
    unittest.main()
