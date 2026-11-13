"""Matched policy effects and marginal parameter/phase summaries, no censor imputation."""
import argparse
import csv
import json
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import numpy as np
from src.sim.io import tree_sha256,write_json


def read(path):
    with path.open(encoding='utf-8') as h:return list(csv.DictReader(h))


def write(path,rows):
    with path.open('w',encoding='utf-8',newline='') as h:
        w=csv.DictWriter(h,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)


def quantiles(rows,key,prefix):
    values=np.array([float(r[key]) for r in rows])
    return {prefix+'_'+p:float(v) for p,v in zip(('p10','p50','p90'),np.quantile(values,[.1,.5,.9]))}


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--root',required=True);args=parser.parse_args()
    root=Path(args.root);folder=root/'supplements';design=json.loads((folder/'design.json').read_text(encoding='utf-8'))
    if design['code_sha256']!=tree_sha256('src'):raise RuntimeError('stale supplement source')
    policy=read(folder/'policy_runs.csv');default={int(r['seed']):r for r in policy if r['setting']=='default'}
    rows=[]
    for setting in sorted({r['setting'] for r in policy}):
        rs=sorted((r for r in policy if r['setting']==setting),key=lambda r:int(r['seed']))
        if {int(r['seed']) for r in rs}!=set(default):raise RuntimeError('policy seeds are not paired')
        row={'setting':setting,'n':len(rs),**quantiles(rs,'E_b','E_b'),**quantiles(rs,'E_w','E_w')}
        for key in ('cost','placed'):
            row['mean_'+key]=float(np.mean([float(r[key]) for r in rs]))
        # Positive avoided exposure means this setting improves on default.
        diff=np.array([float(default[int(r['seed'])]['E_b'])-float(r['E_b']) for r in rs])
        se=float(diff.std(ddof=1)/np.sqrt(len(diff)))
        row.update(paired_mean_avoided_E_b_vs_default=float(diff.mean()),MCSE=se,
            mean_CI95_lo=float(diff.mean()-1.96*se),mean_CI95_hi=float(diff.mean()+1.96*se))
        rows.append(row)
    write(folder/'policy_comparison.csv',rows)
    joint=read(folder/'joint_runs.csv');rows=[]
    for scenario in sorted({r['scenario'] for r in joint}):
        rs=[r for r in joint if r['scenario']==scenario]
        rows.append({'scenario':scenario,'n':len(rs),**quantiles(rs,'E_b','E_b'),
            **quantiles(rs,'E_w','E_w'),**quantiles(rs,'avoided_E_b','paired_avoided_E_b')})
    write(folder/'joint_comparison.csv',rows)
    phase=read(folder/'phase_runs.csv');rows=[]
    groups=sorted({(float(r['volume']),float(r['w_min']),r['strategy']) for r in phase})
    for volume,width,strategy in groups:
        rs=[r for r in phase if float(r['volume'])==volume and float(r['w_min'])==width and r['strategy']==strategy]
        rows.append({'volume':volume,'w_min':width,'strategy':strategy,'n':len(rs),
            **quantiles(rs,'T_safe_w','length_weighted_safe_years'),**quantiles(rs,'E_b','E_b'),
            'first_building_failure_right_censored_n':sum(r['T_first_b_censored']=='True' for r in rs)})
    write(folder/'phase_comparison.csv',rows)
    write_json(folder/'summary_scope.json',{'code_sha256':design['code_sha256'],
        'policy':'100 realized-storm seeds matched to default; decision-dependent extra surveys can alter later observation noise. Normal mean CI describes finite Monte Carlo error only.',
        'joint':'Assumed independent parameter distributions plus storms; no empirical posterior. Marginal bands must not be subtracted as paired effects against the separate fixed-parameter ensemble.',
        'phase':'32 common storm seeds per point; safe years are length-weighted cumulative safety, not uninterrupted protection. Null first-failure times stay censored.'})
    print('SUPPLEMENT TABLES WRITTEN',len(policy),'policy,',len(joint),'joint,',len(phase),'phase runs')


if __name__=='__main__':main()
