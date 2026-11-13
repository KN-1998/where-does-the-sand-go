"""Regressions for the observed JSON-key/matrix-order reporting defect."""
import csv
import json
from pathlib import Path
import tempfile
import unittest
import numpy as np
from scipy.stats import qmc
from tools.analyze_sensitivity_r2 import estimate, read


class SensitivityReportingTests(unittest.TestCase):
    def test_matrix_order_survives_sorted_json_and_shuffled_rows(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            (root/'summary.json').write_text(json.dumps({'n_base':2,
                'ranges':{'z_parameter':[0,1],'a_parameter':[0,1]},
                'output_labels':['response']},sort_keys=True),encoding='utf-8')
            with (root/'design_outputs.csv').open('w',newline='',encoding='utf-8') as h:
                w=csv.DictWriter(h,fieldnames=['matrix','index','z_parameter','a_parameter','output_0'])
                w.writeheader()
                for i in (1,0):w.writerow({'matrix':'A','index':i,'z_parameter':0,'a_parameter':1,'output_0':i+10})
            summary,values=read(root)
            self.assertEqual(summary['_parameter_order'],['z_parameter','a_parameter'])
            np.testing.assert_array_equal(values['A'][:,0],[10,11])

    def test_known_interaction_has_second_order_effect(self):
        unit=qmc.Sobol(4,scramble=True,seed=256).random_base2(13)
        a,b=unit[:,:2]*2-1,unit[:,2:]*2-1
        f=lambda x:(x[:,0]*x[:,1])[:,None]
        values={'A':f(a),'B':f(b)}
        for j in range(2):
            ab=a.copy();ab[:,j]=b[:,j];values[f'AB{j}']=f(ab)
            ba=b.copy();ba[:,j]=a[:,j];values[f'BA{j}']=f(ba)
        indices=estimate(values,len(a))[:,0]
        np.testing.assert_allclose(indices,[0,1,0,1,1],atol=.025)
