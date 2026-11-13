"""Effective snapshots and uncertainty products must reflect executed controls."""
import tempfile
from pathlib import Path
import unittest
from src.exp.mc import run_mc


class EnsembleTests(unittest.TestCase):
    def test_mc_controls_and_paired_retention_are_exported(self):
        with tempfile.TemporaryDirectory() as directory:
            r=run_mc('configs/S1.yaml','S1','uniform',2,42,Path(directory),boundary='open')
            self.assertEqual(r['resolved_config']['bc'],'open')
            self.assertEqual(r['resolved_config']['strategy'],'uniform')
            self.assertNotIn('seed',r['resolved_config'])
            self.assertIn('R_ret_15yr',r['retention_quantiles'])
            self.assertEqual(len(r['width_trajectory']['t']),31)
            self.assertEqual(len(r['width_trajectory']['p50']),31)
            self.assertEqual(len(r['runs']),2)


if __name__=='__main__':unittest.main()
