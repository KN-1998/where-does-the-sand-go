"""Parallel cache for the unchanged global-sensitivity evaluator/estimator.

The source implementation remains the reference serial reproduction. This
driver precomputes identical evaluations and reuses its original aggregator.
"""
import os
os.environ.setdefault('OPENBLAS_NUM_THREADS','1')
os.environ.setdefault('OMP_NUM_THREADS','1')
import argparse
from concurrent.futures import ProcessPoolExecutor, as_completed
import copy
import hashlib
import json
from pathlib import Path
import sys
import time
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import numpy as np
from scipy.stats import qmc
import src.exp.global_sensitivity as gs
from src.sim.io import load_config, write_json, tree_sha256, object_sha256


def evaluate_point(job):
    group,keys,point,seed_count=job
    p=load_config('configs/S2.yaml')
    for key,val in zip(keys,point):gs.set_parameter(p,key,val)
    seeds=[(4200*1000003+i)%2**32 for i in range(seed_count)]
    return tuple(point),gs.evaluate(p,group,seeds)


def lock_output(root):
    """Serialize cache writers when resumed jobs meet a still-running job."""
    handle=(root/'.driver.lock').open('a+b')
    handle.seek(0)
    if os.name=='nt':
        import msvcrt
        waiting=False
        while True:
            try:
                msvcrt.locking(handle.fileno(),msvcrt.LK_NBLCK,1)
                break
            except OSError:
                if not waiting:print('WAITING FOR EXISTING CACHE WRITER',root,flush=True);waiting=True
                time.sleep(1.)
    else:
        import fcntl
        fcntl.flock(handle,fcntl.LOCK_EX)
    if os.fstat(handle.fileno()).st_size==0:
        handle.write(b'0');handle.flush()
    return handle


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--group',default='economy',choices=list(gs.GROUPS))
    parser.add_argument('--root',default='results/release_20261113/GLOBAL_economy')
    parser.add_argument('--power',type=int,default=6);parser.add_argument('--workers',type=int,default=8)
    parser.add_argument('--seed-count',type=int,default=2)
    parser.add_argument('--design-seed',type=int,default=20261112)
    args=parser.parse_args();keys=list(gs.GROUPS[args.group]);d=len(keys)
    unit=qmc.Sobol(2*d,scramble=True,seed=args.design_seed).random_base2(args.power)
    lo=np.array([gs.GROUPS[args.group][k][0] for k in keys]);hi=np.array([gs.GROUPS[args.group][k][1] for k in keys])
    a=lo+(hi-lo)*unit[:,:d];b=lo+(hi-lo)*unit[:,d:]
    points=[a,b]
    for j in range(d):
        ab=a.copy();ab[:,j]=b[:,j];points.append(ab)
        ba=b.copy();ba[:,j]=a[:,j];points.append(ba)
    unique=list(dict.fromkeys(tuple(point) for matrix in points for point in matrix))
    root=Path(args.root);root.mkdir(parents=True,exist_ok=True)
    output_lock=lock_output(root)  # Keep open until aggregation has finished.
    control={'code_sha256':tree_sha256('src'),'config_sha256':object_sha256(load_config('configs/S2.yaml')),
             'group':args.group,'power':args.power,'seed_count':args.seed_count,'design_seed':args.design_seed}
    stamp=object_sha256(control)
    checkpoint=root/f'point_cache_{stamp[:16]}.jsonl'
    write_json(root/'cache_controls.json',control)
    cache={}
    if checkpoint.exists():
        for line in checkpoint.read_text(encoding='utf-8').splitlines():
            try:
                record=json.loads(line);cache[tuple(record['point'])]=record['outputs']
            except json.JSONDecodeError:
                # An interrupted final write is not a completed evaluation.
                continue
    print('RESUME CACHE',len(cache),'/',len(unique),flush=True)
    with ProcessPoolExecutor(max_workers=args.workers) as executor:
        futures=[executor.submit(evaluate_point,(args.group,keys,p,args.seed_count)) for p in unique if p not in cache]
        with checkpoint.open('a',encoding='utf-8') as handle:
            for f in as_completed(futures):
                point,result=f.result();cache[point]=result
                handle.write(json.dumps({'point':point,'outputs':result})+'\n')
                if len(cache)%64==0:
                    handle.flush();print('Cached',len(cache),'/',len(unique),flush=True)
    def lookup(p,group,seeds):
        point=[]
        for key in keys:
            if key in ('lambda_s','dy_ref'):v=p['scenarios']['S2_storm_soon'][key]
            else:
                section=next(s for s in ('transport','storm','management','geometry') if key in p.get(s,{}))
                v=p[section][key]['value']
            point.append(float(v))
        return cache[tuple(point)]
    original=gs.evaluate
    try:
        gs.evaluate=lookup
        gs.run(args.root,args.group,power=args.power,seed_count=args.seed_count,design_seed=args.design_seed)
    finally:gs.evaluate=original
    write_json(Path(args.root)/'execution.json',{'method':'parallel cache; reference serial evaluator and estimator unchanged',
        'unique_points':len(cache),'workers':args.workers,
        'driver_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest()})
    print('Finished parallel global',args.group,flush=True)


if __name__=='__main__':main()
