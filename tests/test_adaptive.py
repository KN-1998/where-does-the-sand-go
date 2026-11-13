"""Policy regressions: no oracle, no zero-benefit spending, realized delay."""
import copy
import unittest
import numpy as np
from src.sim.adaptive import AdaptiveController, batch_transport
from src.sim.grid import Grid, limited_transport
from src.sim.io import load_config
from src.sim.model import ShorelineModel
from src.sim.strategies import make_layout, constrain_placements


class AdaptiveTests(unittest.TestCase):
    def setUp(self): self.p=load_config('configs/S2.yaml')

    def test_batched_forecast_matches_production_transport(self):
        g=Grid.build(dx=100.)
        rng=np.random.default_rng(51)
        y=rng.normal(0,4,(4,len(g.x)));w0=np.full(len(g.x),3.)
        source=rng.normal(-.5,1,y.shape)
        for boundary,yb in [('open',None),('zeroflux',None),('dirichlet',[1.,-2.])]:
            batched=batch_transport(y,source,w0,.1,g,3e5,50.,boundary,yb)
            expected=np.stack([limited_transport(a,b,w0,.1,g,3e5,50.,boundary,yb)[0]
                               for a,b in zip(y,source)])
            np.testing.assert_allclose(batched,expected,atol=1e-12)

    def test_future_realized_events_do_not_enter_forecast(self):
        from src.sim.storms import StormEvent
        a=ShorelineModel(self.p,scenario='S2',strategy='adaptive',events=[])
        b=ShorelineModel(self.p,scenario='S2',strategy='adaptive',events=[StormEvent(2.,99.)])
        fa=AdaptiveController(a).choose(0.,a.initial_y,a.initial_o,2.45e6)
        fb=AdaptiveController(b).choose(0.,b.initial_y,b.initial_o,2.45e6)
        self.assertEqual(fa,fb)
        self.assertGreater(fa['E_b_base_mean'],0.)
        self.assertTrue(any(row['delta_E_b']>0 for row in fa['candidates']))

    def test_approved_projects_have_positive_benefit_and_real_delay(self):
        m=ShorelineModel(self.p,scenario='S2',strategy='adaptive',boundary='open')
        r=m.run();approvals=[x for x in r.results['placements']['adaptive_decisions'] if x['action']=='approve']
        self.assertGreater(len(approvals),0)
        for row in approvals:
            self.assertGreater(row['best']['delta_E_b'],0.)
            self.assertGreaterEqual(row['completion']-row['t'],1.75-1e-9)
            self.assertGreaterEqual(row['best']['protection_q10'],3.)
        self.assertLessEqual(r.results['cost']['cost_used'],120e6)
        self.assertLessEqual(r.results['mass']['placed'],2.45e6)
        self.assertGreater(r.results['cost']['monitoring_cost'],0.)
        reviews=[x for x in r.results['placements']['adaptive_decisions'] if x['action']=='monitor_review']
        self.assertGreater(len(reviews),0)
        self.assertLess(r.results['mass']['residual_rel_max'],1e-6)

    def test_multisegment_layout_is_one_project(self):
        p=copy.deepcopy(self.p)
        p['management']['cost_model']['value']='marginal_plus_fixed'
        p['management']['c0']['value']=4e6
        layout=make_layout('multi',2.45e6)
        placements,skipped=constrain_placements(p,layout)
        self.assertFalse(skipped)
        r=ShorelineModel(p,placements=placements,t_end=.1,events=[]).run().results
        self.assertEqual(r['cost']['n_projects'],1)
        self.assertAlmostEqual(r['cost']['cost_used'],2.45e6*11+4e6)


if __name__=='__main__':unittest.main()
