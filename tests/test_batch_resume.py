"""Changing only YAML inputs must invalidate an apparently complete MC cache."""
import copy
import unittest
from unittest.mock import patch
from src.sim.io import object_sha256
from tools.run_ensembles_r2 import valid_mc_cache


class BatchResumeTests(unittest.TestCase):
    def test_parameter_only_change_rejects_completed_cache(self):
        original={'seed':42,'t_end':15.,'adaptive_options':{'survey_cost_usd':50000.}}
        resolved=copy.deepcopy(original);resolved.pop('seed')
        resolved.update(scenario='S2',strategy='adaptive',bc='open',base_seed=4200,
            seed_rule='(base_seed*1000003+i) mod 2**32')
        old={'n':2,'runs':[{},{}],'code_sha256':'frozen',
             'resolved_config':resolved,'resolved_config_sha256':object_sha256(resolved)}
        job=('mc','unused','S2','adaptive',2)
        with patch('tools.run_ensembles_r2.tree_sha256',return_value='frozen'):
            with patch('tools.run_ensembles_r2.load_config',side_effect=lambda _:copy.deepcopy(original)):
                self.assertTrue(valid_mc_cache(old,job))
            original['adaptive_options']['survey_cost_usd']=100000.
            with patch('tools.run_ensembles_r2.load_config',side_effect=lambda _:copy.deepcopy(original)):
                self.assertFalse(valid_mc_cache(old,job))
