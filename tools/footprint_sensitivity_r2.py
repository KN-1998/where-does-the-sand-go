"""Contract Gaussian-footprint sensitivity using explicit shared event tables.

The normal production generator uses regional uniform storms. This entry point
supplies Gaussian events explicitly; changing phi_shape in YAML alone is not an
implemented production switch. Peak normalization is in apply_storm, unchanged.
"""
import os
os.environ.setdefault('OPENBLAS_NUM_THREADS','1')
os.environ.setdefault('OMP_NUM_THREADS','1')
import argparse
from concurrent.futures import ProcessPoolExecutor,as_completed
import csv
from dataclasses import replace
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import numpy as np
from src.sim.io import load_config,write_json,tree_sha256,object_sha256
from src.sim.model import ShorelineModel
from src.sim.storms import generate_events


def one(job):
    index,strategy,sigma=job
    seed=(4400*1000003+index)%2**32;p=load_config('configs/S2.yaml')
    events,_=generate_events(p,'S2',15.,seed)
    rng=np.random.default_rng(np.random.SeedSequence([seed,741031]))
    centers=rng.uniform(-4500.,4500.,len(events))
    if sigma:
        events=[replace(e,gaussian=True,center=0. if e.forced else float(c)) for e,c in zip(events,centers)]
        p['storm']['sigma_e']['value']=sigma
    model=ShorelineModel(p,scenario='S2',strategy=strategy,boundary='open',seed=seed,events=events)
    sim=model.run();r=sim.results
    mass=max(r['mass']['residual_rel_max'],r['mass']['residual_central_rel_max'])
    if not np.isfinite(mass) or mass>=1e-6:raise ArithmeticError('footprint mass gate')
    marks=[(e.time,e.potential_retreat,e.forced_actual_retreat) for e in events]
    row={'index':index,'seed':seed,'strategy':strategy,'shape':'gaussian' if sigma else 'uniform',
         'sigma_m':sigma,'E_b':r['exposure']['E_b'],'E_w':r['exposure']['E_w'],
         'T_safe_w':r['duration']['T_safe_cum_w'],'placed':r['mass']['placed'],
         'cost':r['cost']['cost_used'],'residual_rel':mass,'mark_sha256':object_sha256(marks)}
    event_rows=[{'index':index,'seed':seed,'strategy':strategy,'shape':row['shape'],
        'sigma_m':sigma,'t':e.time,'potential_retreat':e.potential_retreat,
        'forced_actual_retreat':e.forced_actual_retreat,'center':e.center,
        'actual_center_retreat':record['actual_center_retreat'],
        'injected_full_m3':record['injected_full_m3'],'injected_central_m3':record['injected_central_m3']}
        for e,record in zip(events,sim.event_records)]
    return row,event_rows


def write(path,rows):
    with path.open('w',encoding='utf-8',newline='') as h:
        w=csv.DictWriter(h,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)


def main():
    p=argparse.ArgumentParser();p.add_argument('--root',required=True);p.add_argument('--n',type=int,default=100)
    p.add_argument('--workers',type=int,default=4);a=p.parse_args();out=Path(a.root)/'footprint';out.mkdir(parents=True,exist_ok=True)
    jobs=[(i,st,s) for st in ('once','repeat','fixed_hotspot') for s in (0.,1000.,2000.,5000.) for i in range(a.n)]
    rows=[];events=[]
    with ProcessPoolExecutor(max_workers=a.workers) as ex:
        for k,(r,er) in enumerate(ex.map(one,jobs),1):
            rows.append(r);events.extend(er)
            if k%100==0:print('FOOTPRINT',k,'/',len(jobs),flush=True)
    rows.sort(key=lambda r:(r['strategy'],r['sigma_m'],r['index']))
    write(out/'runs.csv',rows);write(out/'events.csv',events)
    comparison=[]
    for st in ('once','repeat','fixed_hotspot'):
        base={r['seed']:r for r in rows if r['strategy']==st and r['shape']=='uniform'}
        for sigma in (0.,1000.,2000.,5000.):
            rs=[r for r in rows if r['strategy']==st and r['sigma_m']==sigma]
            differences=np.array([base[r['seed']]['E_b']-r['E_b'] for r in rs])
            se=differences.std(ddof=1)/np.sqrt(len(rs))
            q=np.quantile([r['E_b'] for r in rs],[.1,.5,.9])
            comparison.append({'strategy':st,'shape':rs[0]['shape'],'sigma_m':sigma,'n':len(rs),
                'E_b_p10':q[0],'E_b_p50':q[1],'E_b_p90':q[2],
                'paired_mean_avoided_E_b_vs_uniform':differences.mean(),'MCSE':se,
                'mean_CI95_lo':differences.mean()-1.96*se,'mean_CI95_hi':differences.mean()+1.96*se})
    write(out/'comparison.csv',comparison)
    write_json(out/'design.json',{'code_sha256':tree_sha256('src'),'n_per_cell':a.n,'runs':len(rows),
        'strategies':['once','repeat','fixed_hotspot'],'sigma_m':[0.,1000.,2000.,5000.],
        'seed_rule':'(4400*1000003+i) mod 2**32','gaussian_center':'independent U(-4500,4500); forced stress event remains at x=0',
        'limits':'Same arrival/retreat marks and Gaussian centers across widths/strategies; peak-normalized footprint reduces integrated erosion. Not an equal-integrated-energy comparison. S2 forced actual retreat still depends on beach state.'})
    print('FOOTPRINT DONE',len(rows),flush=True)


if __name__=='__main__':main()
