"""Regression tests for scientific metric definitions and censoring."""
import unittest
import numpy as np
from src.sim.metrics import (historical_deficit, km_quantile, length_risk_metrics,
    reconstructed_risk_metrics, recovery_samples, recovery_statistics)


class MetricTests(unittest.TestCase):
    def test_jump_does_not_smear_backwards(self):
        t = [0., 1., 1., 2.]
        a = np.array([[1., 1.], [1., 1.], [-1., -1.], [-1., -1.]])
        for fn in (length_risk_metrics, reconstructed_risk_metrics):
            first, safe, exposed = fn(t, a, .5)
            self.assertEqual(first['value'], 1.)
            self.assertAlmostEqual(exposed, 1.)
            self.assertAlmostEqual(safe, 1.)

    def test_crossing_interpolates_and_safe_exposure_are_complements(self):
        first, safe, exposed = reconstructed_risk_metrics([0., 2.],
            np.array([[1., 1.], [-1., -1.]]), .5)
        self.assertAlmostEqual(first['value'], 1., places=8)
        self.assertAlmostEqual(safe + exposed, 2.)
        self.assertAlmostEqual(exposed, 1., places=10)
        self.assertAlmostEqual(safe, 1., places=10)

    def test_non_midpoint_crossing_integrates_exactly(self):
        first, safe, exposed = reconstructed_risk_metrics([0., 2.],
            np.array([[1.,1.],[-3.,-3.]]), .5)
        self.assertAlmostEqual(exposed,1.5,places=10)
        self.assertAlmostEqual(first['value'],.5,places=8)

    def test_nourishment_censors_natural_recovery(self):
        risk=np.array([[0],[1],[1],[0],[0]],bool)
        samples=recovery_samples([0.,1.,2.,2.,3.],risk,
            [(1.,[0],[1])],[1.],3.,[1],placement_times=[2.])
        self.assertTrue(samples[0]['censored'])
        self.assertEqual(samples[0]['censor_reason'],'nourishment')

    def test_within_step_failure_can_be_hidden_at_both_endpoints(self):
        a=[.2929832428,1.5284995476,-2.6877596011,.8984026948]
        b=[-1.9296333586,-1.0626130828,1.4414347713,.8595657368]
        first,_,_=reconstructed_risk_metrics([0.,1.],[a,b],.5)
        self.assertFalse(first['censored'])
        self.assertAlmostEqual(first['value'],.2287717303,places=8)

    def test_historical_deficit_is_sum_of_cellwise_peaks(self):
        a = [[-2., 0.], [0., -3.]]
        self.assertEqual(historical_deficit(a, 10., 25.), 1250.)

    def test_central_mask_and_next_storm_censor(self):
        t = np.array([0., 1., 1., 2., 2., 3.])
        risk = np.array([[0,0,0], [0,0,0], [1,1,1], [1,1,0], [0,0,0], [0,0,0]], bool)
        samples = recovery_samples(t, risk, [(1., risk[1], risk[2])],
                                   [1., 2.], 3., [0,1,0])
        self.assertEqual(len(samples), 1)
        self.assertEqual(samples[0]['cell'], 1)
        self.assertEqual(samples[0]['duration'], 1.)
        self.assertTrue(samples[0]['censored'])
        self.assertEqual(samples[0]['censor_reason'], 'next_storm')

    def test_raw_km_handles_actual_censor_times_and_ties(self):
        self.assertEqual(km_quantile([1., 2., 3.], [True, False, False], .5), 2.)
        self.assertEqual(km_quantile([1., 1.], [True, False], .5), 1.)
        self.assertIsNone(km_quantile([.25, .5], [True, True], .5))
        summary = recovery_statistics([])
        self.assertEqual(summary['n'], 0)
        self.assertIsNone(summary['value'])


if __name__ == '__main__':
    unittest.main()
