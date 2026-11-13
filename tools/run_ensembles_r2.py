"""Rebuild primary paired ensembles, keeping expensive Sobol jobs separate."""
import os
os.environ.setdefault('OPENBLAS_NUM_THREADS','1');os.environ.setdefault('OMP_NUM_THREADS','1')
import argparse
from concurrent.futures import ProcessPoolExecutor,as_completed
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from src.exp.batch import task
from src.sim.io import write_json,tree_sha256,load_config,object_sha256


def valid_mc_cache(old,job):
    _,_,scenario,strategy,n=job
    expected=load_config(f'configs/{scenario}.yaml')
    expected.update(scenario=scenario,strategy=strategy,bc='open',
        t_end=float(expected.get('t_end',15.)),base_seed=4200,
        seed_rule='(base_seed*1000003+i) mod 2**32')
    expected.pop('seed',None)
    return (old.get('n')==n and len(old.get('runs',[]))==n and
        old.get('code_sha256')==tree_sha256('src') and
        old.get('resolved_config_sha256')==object_sha256(expected) and
        object_sha256(old.get('resolved_config',{}))==object_sha256(expected))


def main():
    p=argparse.ArgumentParser();p.add_argument('--root',required=True);p.add_argument('--workers',type=int,default=10)
    p.add_argument('--n',type=int,default=1000);p.add_argument('--oat-n',type=int,default=20)
    a=p.parse_args();root=Path(a.root);root.mkdir(parents=True,exist_ok=True)
    jobs=[('mc',str(root),s,st,a.n) for s in ('S1','S2','S3')
          for st in ('none','once','repeat','targeted','adaptive')]
    jobs += [('mc',str(root),'S1',st,a.n) for st in ('uniform','hotspot','multi')]
    jobs += [('oat',str(root),'S2','once',a.oat_n),('timing',str(root),'S2','uniform',a.n)]
    write_json(root/'batch_design.json',{'n':a.n,'oat_seeds_per_value':a.oat_n,'global_base_n':512,
        'global_scrambles':[20261112,20261113],'workers':a.workers,'jobs':jobs,
        'deterministic_expected':47,'MC_groups_expected':18,'matlab_figure_pairs_expected':17,
        'code_sha256':tree_sha256('src'),'scientific_status':'conditional scenarios; synthetic observations; no local empirical validation'})
    with ProcessPoolExecutor(max_workers=a.workers) as ex:
        futures=[]
        for j in jobs:
            if j[0]=='mc' and (root/f'MC_{j[2]}_{j[3]}'/'summary.json').exists():
                import json
                old=json.loads((root/f'MC_{j[2]}_{j[3]}'/'summary.json').read_text(encoding='utf-8'))
                if valid_mc_cache(old,j):
                    print('RESUME SKIP',j,flush=True);continue
            futures.append(ex.submit(task,j))
        for f in as_completed(futures):print('FINISHED',f.result(),flush=True)


if __name__=='__main__':main()
