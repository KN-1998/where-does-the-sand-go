"""Paired storm timing, supply/cost diagnostics and analytical phase map."""
import copy
import csv
from pathlib import Path
import numpy as np
from src.sim.io import load_config, write_json, tree_sha256
from src.sim.model import ShorelineModel
from src.sim.storms import StormEvent
from src.sim.strategies import Placement


def run(root, n=1000):
    root = Path(root)
    p = load_config('configs/S2.yaml')
    out = root/'timing';out.mkdir(parents=True,exist_ok=True)
    rows = []
    times = {'early':np.linspace(.25,4.75,6), 'spread':np.arange(1.25,15,2.5),
             'late':np.linspace(10.25,14.75,6)}
    # No forced event or stochastic extra events: exactly the same six marks.
    # Identical amplitudes/order by realization; only their timestamps differ.
    for index in range(n):
        rng = np.random.default_rng((4200*1000003+index)%2**32)
        magnitudes = rng.lognormal(np.log(8.),np.log(25/8)/1.645,6)
        for label, clock in times.items():
            events = [StormEvent(float(t),float(a)) for t,a in zip(clock,magnitudes)]
            r = ShorelineModel(p,scenario='S2',strategy='uniform',boundary='open',
                seed=index,events=events,t_end=15.,placements=[Placement(0.,2.45e6,0.,5000.)]).run().results
            rows.append({'index':index,'timing':label,'E_b':r['exposure']['E_b'],
                'E_w':r['exposure']['E_w'],'T_safe_cum_w':r['duration']['T_safe_cum_w'],
                'w_end_mean':r['state']['w_end_mean'],'residual_rel_max':r['mass']['residual_rel_max']})
    with (out/'runs.csv').open('w',encoding='utf-8',newline='') as h:
        w=csv.DictWriter(h,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
    summary = {'n':n,'times':{k:v.tolist() for k,v in times.items()},
        'design':'Same six potential-retreat marks and order per seed; uniform placement at t=0. Chronically adjusted S2 forcing held identical. Independent from the forced S2 scenario.',
        'code_sha256':tree_sha256('src'),'statistics':{}}
    for label in times:
        summary['statistics'][label]={key:{'p10':float(np.quantile([r[key] for r in rows if r['timing']==label],.1)),
            'p50':float(np.median([r[key] for r in rows if r['timing']==label])),
            'p90':float(np.quantile([r[key] for r in rows if r['timing']==label],.9))}
            for key in ('E_b','E_w','T_safe_cum_w','w_end_mean')}
    write_json(out/'summary.json',summary)
    # E7: instantaneous coverage feasibility, not a long-term policy forecast.
    phase = []
    for wmin in np.linspace(10,25,31):
        for volume in np.linspace(0,1e6,41):
            phase.append({'w_min_m':float(wmin),'volume_m3':float(volume),
                'threshold_volume_m3':float(10*5000*max(20-wmin,0)),
                'uniform_initially_feasible':bool(volume>=10*5000*max(20-wmin,0))})
    with (root/'phase_map.csv').open('w',encoding='utf-8',newline='') as h:
        w=csv.DictWriter(h,fieldnames=list(phase[0]));w.writeheader();w.writerows(phase)
    return summary
