"""Production-solver T2/T4/T5/T7 and constraint regression gates."""
import copy
import unittest
import numpy as np
from scipy.optimize import brentq
from scipy.special import erf, ndtr
from src.sim.grid import Grid, backward_euler, limited_transport
from src.sim.io import load_config
from src.sim.model import ShorelineModel
from src.sim.strategies import Placement, strategy_schedule, cost_terms


class ValidationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.p = load_config('configs/base.yaml')

    def test_t2_be_first_order_with_dt_proportional_dx(self):
        errors = []
        for dx in (50., 25., 12.5):
            g = Grid.build(dx=dx)
            y = np.exp(-g.x**2/(2*200.**2))
            dt = .05 * dx / 100
            n = round(1/dt)
            for _ in range(n):
                y, _ = backward_euler(y, 0., 1/n, g, 3e5, 0., 'open')
            variance = 200.**2 + 6e5
            exact = 200./np.sqrt(variance)*np.exp(-g.x**2/(2*variance))
            errors.append(np.sqrt(np.mean((y-exact)**2)))
            self.assertGreaterEqual(y.min(), 0.)
        for ratio in np.array(errors[:-1])/errors[1:]:
            self.assertGreaterEqual(ratio, 1.8)
            self.assertLessEqual(ratio, 2.2)

    def test_t4_all_scenarios_first_failure_and_central_inventory(self):
        for scenario in ('S1', 'S2', 'S3'):
            coarse, fine = [ShorelineModel(self.p, scenario=scenario, boundary='open',
                t_end=15., dx=dx, dt=.0008*dx, seed=42).run() for dx in (50.,25.)]
            a, b = [r.results['duration']['T_first_fail_w']['value'] for r in (coarse,fine)]
            self.assertLess(abs(a-b)/b, .02)
            # Compare retained book inventory + reservoir at year 5 as well.
            inventory = []
            for dx, baseline in zip((50.,25.), (coarse,fine)):
                nourished = ShorelineModel(self.p, scenario=scenario, boundary='open',
                    t_end=15., dx=dx, dt=.0008*dx, seed=42,
                    placements=[Placement(0.,2.45e6,0.,5000.)]).run()
                def at5(r):
                    return np.interp(5., [a['t'] for a in r.ledger],
                        [a['V_central']+a['O_central'] for a in r.ledger])
                inventory.append((at5(nourished)-at5(baseline))/2.45e6)
            self.assertLess(abs(inventory[0]-inventory[1])/max(abs(inventory[1]),1e-12), .02)

    def test_t5_analytic_center_protection_benchmark(self):
        p = copy.deepcopy(self.p)
        p['transport']['u_drift']['value'] = 0.
        p['beach_state']['w0_far']['value'] = 18.
        p['beach_state']['w0_min']['value'] = 18.
        for length in (5000.,1000.,500.):
            r = ShorelineModel(p, boundary='open', t_end=10., storm_enabled=False,
                rho_override=2.3, placements=[Placement(0.,1e6,0.,length)]).run()
            centre_width = r.fields['w'][:, len(r.fields['x'])//2]
            hit = np.flatnonzero(centre_width < 20.)[0]
            t = r.fields['t']
            numerical = np.interp(20., centre_width[hit-1:hit+1][::-1], t[hit-1:hit+1][::-1])
            exact = brentq(lambda z: 1e6/(10*length)*erf(length/(4*np.sqrt(3e5*z)))-2.3*z-2., .001,20.)
            self.assertLess(abs(numerical-exact)/exact, .10)

    def test_t7_known_outflow_matches_infinite_gaussian_estimate(self):
        g = Grid.build(dx=25.)
        initial = np.exp(-g.x**2/(2*300.**2))
        estimates = {}
        for bc in ('open','zeroflux'):
            y, flux = initial.copy(), 0.
            for _ in range(500):
                y, faces = backward_euler(y, 0., .005, g, 3e4, 1800., bc)
                flux += (faces[-1]-faces[0])*.005
            estimates[bc] = flux
            self.assertAlmostEqual((initial.sum()-y.sum())*g.dx, flux, places=8)
        expected = initial.sum()*g.dx*(1-ndtr(0.))
        self.assertLess(abs(estimates['open']-expected)/expected,.10)
        self.assertEqual(estimates['zeroflux'], 0.)

    def test_limiter_actually_caps_flux_from_empty_donors(self):
        g = Grid.build(25.,10.,20.)
        y = np.array([1.,0,0,0,0])
        out, faces, count = limited_transport(y,0.,np.zeros(5),1.,g,0.,100.,'zeroflux')
        self.assertEqual(count, 3)
        np.testing.assert_allclose(out, [1/11,10/11,0,0,0],atol=1e-12)
        self.assertAlmostEqual(out.sum(),1.)
        self.assertEqual(faces[2],0.)

    def test_supply_budget_and_alternate_cost_modes(self):
        for supply in ('local','external'):
            for mode in ('all_in','marginal_plus_fixed'):
                p = copy.deepcopy(self.p)
                p['management']['supply_scenario']['value'] = supply
                p['management']['cost_model']['value'] = mode
                p['management']['c0']['value'] = 4e6
                for strategy in ('once','repeat','targeted'):
                    schedule = strategy_schedule(strategy,p,15.)
                    unit, fixed = cost_terms(p)
                    amount = sum(x.volume for x in schedule)
                    self.assertLessEqual(amount*unit + len(schedule)*fixed,120e6+1e-6)
                    self.assertLessEqual(amount,2.45e6+1e-6 if supply=='local' else 5e6+1e-6)
                    self.assertTrue(all(x.volume<=2.9e6+1e-6 for x in schedule))

    def test_safe_time_identity_in_production_and_exhausted_reservoir(self):
        from src.sim.storms import StormEvent
        r = ShorelineModel(self.p, scenario='S2', t_end=15., rho_override=12.,
            events=[StormEvent(.5,100.)]).run()
        for kind in ('w','b'):
            self.assertAlmostEqual(r.results['duration']['T_safe_cum_'+kind]+
                r.results['exposure']['E_'+kind]/5000.,15.,places=10)
        self.assertGreater(r.results['state']['exhausted_frac'],0.)
        self.assertLess(r.results['mass']['residual_rel_max'],1e-6)
        self.assertGreater(r.fields['O'][30].sum(),0.)

    def test_no_action_adaptive_equals_paired_baseline(self):
        p=copy.deepcopy(self.p)
        p['management']['delta_f_trig']['value']=2.
        p['beach_state']['d_bldg']['value']=1e6
        a = ShorelineModel(p,scenario='S2',strategy='adaptive',boundary='open',t_end=15.).run()
        b = ShorelineModel(p,scenario='S2',strategy='none',boundary='open',t_end=15.).run()
        self.assertEqual(a.results['mass']['placed'],0.)
        np.testing.assert_array_equal(a.fields['y'],b.fields['y'])
        self.assertEqual(a.results['exposure'],b.results['exposure'])


if __name__ == '__main__':
    unittest.main()
