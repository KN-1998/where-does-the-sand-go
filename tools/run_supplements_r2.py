"""Joint uncertainty, durable phase map, and policy approximation checks.

Ranges and monitoring capabilities are assumptions. No output is empirical
calibration or independent field validation. Each task has a reproducible seed.
"""
import os
os.environ.setdefault('OPENBLAS_NUM_THREADS','1');os.environ.setdefault('OMP_NUM_THREADS','1')
import argparse
import copy
import csv
from concurrent.futures import ProcessPoolExecutor,as_completed
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import numpy as np
from src.sim.io import load_config,write_json,tree_sha256
from src.sim.model import ShorelineModel
from src.sim.strategies import Placement


def one(job):
    kind,scenario,index,setting=job
    p=load_config(f'configs/{scenario}.yaml');seed=(4300*1000003+index)%2**32
    changes={}
    if kind=='joint':
        rng=np.random.default_rng(np.random.SeedSequence([index,135002]))
        changes={'D_diff':float(np.exp(rng.uniform(np.log(1e5),np.log(8e5)))),
            'H_dep':float(rng.triangular(8.,10.,12.)),
            'rho_e':float(p['transport']['rho_e']['value']*rng.uniform(.8,1.2)),
            'k_rec':float(p['storm']['k_rec']['value']*rng.uniform(.5,1.5)),
            'lam_off':float(p['storm']['lam_off']['value']*rng.uniform(.5,1.5))}
        for k,v in changes.items():
            section=next(s for s in ('transport','geometry','storm') if k in p[s]);p[section][k]['value']=v
        strategies=('none','once')
    elif kind=='policy':
        p['adaptive_options'].update(setting[1]);strategies=('adaptive',)
    else:
        volume,w_min,strategy=setting
        p['beach_state']['w0_min']['value']=w_min
        placements=[Placement(0.,volume,0.,5000. if strategy=='uniform' else 1000.)]
        strategies=(strategy,)
    runs=[]
    for st in strategies:
        kwargs={'placements':placements} if kind=='phase' else {}
        r=ShorelineModel(p,scenario=scenario,strategy=st,boundary='open',seed=seed,**kwargs).run().results
        if max(r['mass']['residual_rel_max'],r['mass']['residual_central_rel_max'])>=1e-6:
            raise ArithmeticError('supplement mass gate failed')
        runs.append(r)
    r=runs[-1]
    row={'kind':kind,'scenario':scenario,'index':index,'seed':seed,'E_b':r['exposure']['E_b'],
        'E_w':r['exposure']['E_w'],'T_safe_w':r['duration']['T_safe_cum_w'],
        'T_first_b':r['duration']['T_first_fail_b']['value'],
        'T_first_b_censored':r['duration']['T_first_fail_b']['censored'],
        'placed':r['mass']['placed'],'cost':r['cost']['cost_used'],
        'residual_rel':max(r['mass']['residual_rel_max'],r['mass']['residual_central_rel_max'])}
    if kind=='joint':row.update(changes,avoided_E_b=runs[0]['exposure']['E_b']-r['exposure']['E_b'])
    elif kind=='policy':row['setting']=setting[0]
    else:row.update(volume=volume,w_min=w_min,strategy=strategy)
    return row


def write_csv(path,rows):
    with path.open('w',encoding='utf-8',newline='') as h:
        w=csv.DictWriter(h,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)


def main():
    p=argparse.ArgumentParser();p.add_argument('--root',required=True);p.add_argument('--workers',type=int,default=8)
    p.add_argument('--joint-n',type=int,default=1000);p.add_argument('--policy-n',type=int,default=100)
    p.add_argument('--phase-n',type=int,default=32);p.add_argument('--only',default='joint,policy,phase')
    a=p.parse_args();root=Path(a.root)/'supplements';root.mkdir(parents=True,exist_ok=True)
    jobs=[]
    if 'joint' in a.only.split(','):
        jobs += [('joint',s,i,None) for s in ('S1','S2','S3') for i in range(a.joint_n)]
    settings=[('default',{}),('refined',{'members':16,'forecast_dx':50.,'forecast_dt':.05}),
              ('survey_10k',{'survey_cost_usd':10000.}),('survey_100k',{'survey_cost_usd':100000.}),
              ('nearshore_noisier',{'nearshore_sigma_m2':60.})]
    if 'policy' in a.only.split(','):
        jobs += [('policy','S2',i,s) for s in settings for i in range(a.policy_n)]
    if 'phase' in a.only.split(','):
        jobs += [('phase','S1',i,(float(v),float(w),st)) for v in np.linspace(.25e6,2.45e6,8)
            for w in np.linspace(10.,25.,8) for st in ('uniform','hotspot') for i in range(a.phase_n)]
    rows={k:[] for k in ('joint','policy','phase')}
    with ProcessPoolExecutor(max_workers=a.workers) as ex:
        futures=[ex.submit(one,j) for j in jobs]
        for n,f in enumerate(as_completed(futures),1):
            row=f.result();rows[row['kind']].append(row)
            if n%200==0:print('SUPPLEMENT',n,'/',len(jobs),flush=True)
    for kind,rs in rows.items():
        if rs:
            rs.sort(key=lambda r:(r['scenario'],str(r.get('setting','')),r.get('volume',0),r.get('w_min',0),str(r.get('strategy','')),r['index']))
            write_csv(root/f'{kind}_runs.csv',rs)
    design={'code_sha256':tree_sha256('src'),'joint_n':a.joint_n,'policy_n':a.policy_n,'phase_n':a.phase_n,
            'rows':{k:len(v) for k,v in rows.items()},'policy_settings':settings,
            'joint_assumed_distributions':{'D':'log-uniform [1e5,8e5]','H':'triangular [8,10,12]',
                'rho_background_multiplier':'uniform [.8,1.2]','k_multiplier':'uniform [.5,1.5]',
                'lambda_off_multiplier':'uniform [.5,1.5]'},
            'limits':'Independent assumed inputs, not fitted priors. Phase map includes S1 storms. Policy comparison shares realized storms and survey seed but decision-dependent extra surveys can change later observation noise.'}
    old=root/'design.json'
    if old.exists():
        import json
        prior=json.loads(old.read_text(encoding='utf-8'))
        if prior['code_sha256']!=design['code_sha256']:raise RuntimeError('stale supplement outputs')
        design['rows']={k:max(prior['rows'].get(k,0),v) for k,v in design['rows'].items()}
    write_json(old,design);print('SUPPLEMENTS DONE',design['rows'],flush=True)


if __name__=='__main__':main()
