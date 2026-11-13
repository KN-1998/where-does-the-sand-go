import unittest
import numpy as np
from src.sim.grid import Grid
from src.sim.storms import StormEvent,apply_storm


class StormFootprintTests(unittest.TestCase):
    def test_gaussian_keeps_peak_and_conserves_exchange_with_lower_total(self):
        grid=Grid.build(4500.,25.,2500.)
        y=np.zeros_like(grid.x);offshore=np.zeros_like(y);w0=np.full_like(y,25.)
        regional=apply_storm(y,offshore,w0,grid,10.,StormEvent(0.,8.),30.,1000.)
        local=apply_storm(y,offshore,w0,grid,10.,StormEvent(0.,8.,gaussian=True),30.,1000.)
        self.assertAlmostEqual(regional[3],local[3],places=12)
        self.assertLess(local[4],regional[4])
        self.assertAlmostEqual(local[4]/regional[4],np.sqrt(2*np.pi)*1000/9000,delta=.001)
        np.testing.assert_allclose(10.*local[0]+local[1],0.,atol=1e-13)
        self.assertAlmostEqual(float(local[1].sum()*grid.dx),local[4],places=8)
