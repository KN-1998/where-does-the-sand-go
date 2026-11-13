"""Rebuild the reviewed programming package, with bounded process concurrency."""
import os
os.environ.setdefault('OPENBLAS_NUM_THREADS','1')
os.environ.setdefault('OMP_NUM_THREADS','1')
import argparse
from concurrent.futures import ProcessPoolExecutor, as_completed
import csv
import hashlib
import json
from pathlib import Path
import yaml
import numpy as np
from src.exp.run_one import main as run_one
from src.exp.mc import run_mc
from src.exp.sweep import run_sweep
from src.exp.summarize import summarize, FIELDS
from src.exp.export_mat import export
from src.exp.supplement import run as timing
from src.exp.global_sensitivity import run as global_run
from src.exp.history import run as history
from src.sim.io import write_json, tree_sha256
from src.sim.strategies import supply_cap


def generated_config(root, name, changes):
    path=root/'configs'/f'{name}.yaml';path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(yaml.safe_dump({'inherit':str(Path('configs/S2.yaml').resolve()),**changes},
                                  allow_unicode=True,sort_keys=False),encoding='utf-8')
    return str(path)


def deterministic(root):
    for scenario in ('S1','S2','S3'):
        for strategy in ('none','once','repeat','targeted','adaptive'):
            label='baseline' if strategy=='none' else strategy
            run_one(['--config',f'configs/{scenario}.yaml','--scenario',scenario,'--strategy',strategy,
                '--bc','open','--t-end','15','--paired-retention','--out',str(root/f'{scenario}_{label}')])
    for strategy in ('uniform','hotspot','multi'):
        run_one(['--config','configs/S1.yaml','--scenario','S1','--strategy',strategy,'--bc','open',
                 '--paired-retention','--out',str(root/f'S1_{strategy}')])
    diagnostics={
        'BC_S2_once_zeroflux':({},'zeroflux',None),
        'BC_S2_once_dirichlet':({},'dirichlet',['0','0']),
        'DIAG_S2_once_unadjusted':({'chronic_mode':'scenario_unadjusted'},'open',None),
        'DIAG_S2_once_observed_direct':({'chronic_mode':'observed_direct'},'open',None)}
    for supply in ('local','external'):
        for mode in ('all_in','marginal_plus_fixed'):
            for strategy in ('once','repeat','targeted'):
                name=f'DIAG_{supply}_{mode}_{strategy}'
                overrides={'supply_scenario':supply,'cost_model':mode,'c0':4e6 if mode=='marginal_plus_fixed' else 0.}
                diagnostics[name]=({'overrides':overrides,'strategy':strategy},'open',None)
    diagnostics['DIAG_availability08_repeat']=({'overrides':{'supply_availability':.8},'strategy':'repeat'},'open',None)
    for c0 in (0.,2e6,6e6,10e6):
        for strategy in ('once','repeat','targeted'):
            diagnostics[f'DIAG_c0_{int(c0)}_{strategy}']=({'overrides':{
                'cost_model':'marginal_plus_fixed','c0':c0},'strategy':strategy},'open',None)
    for label,(changes,bc,values) in diagnostics.items():
        cfg=generated_config(root,label,changes)
        args=['--config',cfg,'--scenario','S2','--strategy',changes.get('strategy','once'),
              '--bc',bc,'--paired-retention','--out',str(root/label)]
        if values:args+=['--y-boundary',*values]
        run_one(args)
    with (root/'summary.csv').open('w',encoding='utf-8',newline='') as h:
        writer=csv.DictWriter(h,fieldnames=FIELDS);writer.writeheader();writer.writerows(summarize(root))
    dbf=Path('data/raw/Hatteras_Transects.dbf')
    if dbf.exists():history(dbf,root/'history')
    export(root)


def task(job):
    kind,root,scenario,strategy,n=job
    root=Path(root)
    if kind=='mc':
        run_mc(f'configs/{scenario}.yaml',scenario,strategy,n,4200,
               root/f'MC_{scenario}_{strategy}',boundary='open')
    elif kind=='oat':run_sweep('configs/S2.yaml','S2','once',n,4200,root/'OAT_S2_once',boundary='open')
    elif kind=='timing':timing(root,n)
    elif kind=='global':global_run(root/f'GLOBAL_{scenario}',scenario,power=n)
    return f'{kind} {scenario} {strategy}'


def audit(root):
    root=Path(root);expected=tree_sha256('src');failures=[];records=[]
    for path in sorted(root.rglob('results.json')):
        r=json.loads(path.read_text(encoding='utf-8'));m=r['mass'];p=r['parameters']
        residual=max(m['residual_rel_max'],m['residual_central_rel_max'])
        if residual>=1e-6:failures.append(str(path)+': residual')
        if r['meta']['code_sha256']!=expected:failures.append(str(path)+': stale code')
        if m['placed']>supply_cap(p)+1e-6 or r['cost']['cost_used']>p['management']['C_max']['value']+1e-6:
            failures.append(str(path)+': constraints')
        for suffix in ('w','b'):
            if abs(r['duration']['T_safe_cum_'+suffix]+r['exposure']['E_'+suffix]/5000-p['t_end'])>1e-8:
                failures.append(str(path)+': metric identity')
        if 'sand_attribution' in r and abs(r['sand_attribution']['closure_m3'])>1e-6*max(m['placed'],1):
            failures.append(str(path)+': paired sand attribution')
        records.append({'path':path.relative_to(root).as_posix(),'residual':residual,'code_sha256':r['meta']['code_sha256']})
    mc={}
    for path in sorted(root.glob('MC_*/summary.json')):
        r=json.loads(path.read_text(encoding='utf-8'))
        if r['code_sha256']!=expected:failures.append(str(path)+': stale code')
        scenario=r['scenario'];mc.setdefault(scenario,[]).append(r['event_table_hashes'])
        if max(max(a['residual_rel_max'],a['residual_central_rel_max']) for a in r['runs'])>=1e-6:
            failures.append(str(path)+': MC residual')
    for scenario,tables in mc.items():
        if any(a!=tables[0] for a in tables[1:]):failures.append(scenario+': unpaired events')
    for path in [*root.glob('OAT_*/design.json'),*root.glob('GLOBAL_*/summary.json'),root/'timing/summary.json']:
        if path.exists() and json.loads(path.read_text(encoding='utf-8'))['code_sha256']!=expected:
            failures.append(str(path)+': stale code')
    manifest={}
    for path in sorted(root.rglob('*')):
        if path.is_file() and path.name not in ('manifest.json','audit.json'):
            manifest[path.relative_to(root).as_posix()]=hashlib.sha256(path.read_bytes()).hexdigest()
    report={'status':'PASS' if not failures else 'FAIL','failures':failures,
        'code_sha256':expected,'n_deterministic':len(records),'n_mc_batches':sum(len(a) for a in mc.values()),
        'deterministic':records,'max_deterministic_residual':max([a['residual'] for a in records],default=0.)}
    write_json(root/'audit.json',report);write_json(root/'manifest.json',manifest)
    if failures:raise RuntimeError('; '.join(failures))
    print('AUDIT PASS',len(records),'deterministic runs;',report['n_mc_batches'],'MC batches',flush=True)
    return report


def main(argv=None):
    p=argparse.ArgumentParser();p.add_argument('--root',default='results/release_20261112_matlab')
    p.add_argument('--stage',choices=['all','deterministic','ensembles','audit'],default='all')
    p.add_argument('--n',type=int,default=1000);p.add_argument('--oat-n',type=int,default=20)
    p.add_argument('--global-power',type=int,default=6);p.add_argument('--workers',type=int,default=6)
    args=p.parse_args(argv);root=Path(args.root);root.mkdir(parents=True,exist_ok=True)
    if args.stage in ('all','deterministic'):deterministic(root)
    if args.stage in ('all','ensembles'):
        jobs=[('mc',str(root),s,st,args.n) for s in ('S1','S2','S3') for st in
              ('none','once','repeat','targeted','adaptive')]
        jobs += [('mc',str(root),'S1',st,args.n) for st in ('uniform','hotspot','multi')]
        jobs += [('oat',str(root),'S2','once',args.oat_n),('timing',str(root),'S2','uniform',args.n)]
        jobs += [('global',str(root),group,'once',args.global_power) for group in ('transport','storm','economy')]
        write_json(root/'batch_design.json',{'n':args.n,'oat_seeds_per_value':args.oat_n,
            'global_base_n':2**args.global_power,'workers':args.workers,'code_sha256':tree_sha256('src'),
            'jobs':jobs,'scientific_status':'conditional scenarios; observable-state ensemble adaptive; synthetic monitoring only'})
        with ProcessPoolExecutor(max_workers=args.workers) as executor:
            futures=[executor.submit(task,j) for j in jobs]
            for f in as_completed(futures):print('FINISHED',f.result(),flush=True)
    if args.stage in ('all','audit'):audit(root)
    return 0


if __name__=='__main__':
    raise SystemExit(main())
