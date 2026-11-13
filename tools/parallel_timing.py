"""Process-parallel reproduction of src.exp.supplement's paired timing test."""
import os
os.environ.setdefault('OPENBLAS_NUM_THREADS','1')
os.environ.setdefault('OMP_NUM_THREADS','1')
import argparse
from concurrent.futures import ProcessPoolExecutor, as_completed
import csv
import hashlib
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import numpy as np
from src.sim.io import load_config, write_json, tree_sha256
from src.sim.model import ShorelineModel
from src.sim.storms import StormEvent
from src.sim.strategies import Placement

CLOCKS={'early':np.linspace(.25,4.75,6),'spread':np.arange(1.25,15,2.5),'late':np.linspace(10.25,14.75,6)}


def one(index):
    p=load_config('configs/S2.yaml');rng=np.random.default_rng((4200*1000003+index)%2**32)
    magnitudes=rng.lognormal(np.log(8.),np.log(25/8)/1.645,6);rows=[]
    for label,times in CLOCKS.items():
        events=[StormEvent(float(t),float(a)) for t,a in zip(times,magnitudes)]
        r=ShorelineModel(p,scenario='S2',strategy='uniform',boundary='open',seed=index,
            events=events,t_end=15.,placements=[Placement(0.,2.45e6,0.,5000.)]).run().results
        if max(r['mass']['residual_rel_max'],r['mass']['residual_central_rel_max'])>=1e-6:
            raise ArithmeticError('timing run failed conservation')
        rows.append({'index':index,'timing':label,'E_b':r['exposure']['E_b'],'E_w':r['exposure']['E_w'],
            'T_safe_cum_w':r['duration']['T_safe_cum_w'],'w_end_mean':r['state']['w_end_mean'],
            'residual_rel_max':r['mass']['residual_rel_max']})
    return rows


def main():
    p=argparse.ArgumentParser();p.add_argument('--root',default='results/release_20261113')
    p.add_argument('--n',type=int,default=1000);p.add_argument('--workers',type=int,default=4)
    args=p.parse_args();root=Path(args.root);out=root/'timing';out.mkdir(parents=True,exist_ok=True)
    rows=[]
    with ProcessPoolExecutor(max_workers=args.workers) as executor:
        futures=[executor.submit(one,i) for i in range(args.n)]
        for future in as_completed(futures):
            rows.extend(future.result())
            if len(rows)%600==0:print('Timing completed',len(rows)//3,'/',args.n,flush=True)
    order={name:i for i,name in enumerate(CLOCKS)}
    rows.sort(key=lambda r:(r['index'],order[r['timing']]))
    with (out/'runs.csv').open('w',encoding='utf-8',newline='') as h:
        w=csv.DictWriter(h,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
    summary={'n':args.n,'times':{k:v.tolist() for k,v in CLOCKS.items()},
        'design':'Same six potential-retreat marks and order per seed; uniform placement at t=0. Chronically adjusted S2 forcing held identical. Independent from the forced S2 scenario.',
        'code_sha256':tree_sha256('src'),'statistics':{}}
    for label in CLOCKS:
        summary['statistics'][label]={key:{'p10':float(np.quantile([r[key] for r in rows if r['timing']==label],.1)),
            'p50':float(np.median([r[key] for r in rows if r['timing']==label])),
            'p90':float(np.quantile([r[key] for r in rows if r['timing']==label],.9))}
            for key in ('E_b','E_w','T_safe_cum_w','w_end_mean')}
    write_json(out/'summary.json',summary)
    write_json(out/'execution.json',{'workers':args.workers,'method':'same equations and paired design as serial supplement.py',
        'driver_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest()})
    phase=[]
    for wmin in np.linspace(10,25,31):
        for volume in np.linspace(0,1e6,41):
            phase.append({'w_min_m':float(wmin),'volume_m3':float(volume),
                'threshold_volume_m3':float(10*5000*max(20-wmin,0)),
                'uniform_initially_feasible':bool(volume>=10*5000*max(20-wmin,0))})
    with (root/'phase_map.csv').open('w',encoding='utf-8',newline='') as h:
        w=csv.DictWriter(h,fieldnames=list(phase[0]));w.writeheader();w.writerows(phase)
    print('Finished paired timing',args.n,flush=True)


if __name__=='__main__':main()
