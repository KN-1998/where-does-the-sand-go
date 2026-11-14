"""Check completeness as well as conservation before delivery."""
import argparse
import csv
import hashlib
import json
import os
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import numpy as np
from src.sim.io import tree_sha256, write_json
from tools.run_ensembles_r2 import valid_mc_cache
from tools.policy_rule_diagnostic import diagnose


def main():
    project_root=Path(__file__).resolve().parents[1]
    p=argparse.ArgumentParser();p.add_argument('--root',default=str(project_root/'results/release_20261113_r2'))
    args=p.parse_args();root=Path(args.root).resolve()
    os.chdir(project_root)
    code=tree_sha256('src');errors=[];maximum=0.
    design=json.loads((root/'batch_design.json').read_text(encoding='utf-8'))
    deterministic=list(root.glob('*/results.json'))
    if len(deterministic)!=design['deterministic_expected']:errors.append('deterministic count')
    for path in deterministic:
        j=json.loads(path.read_text(encoding='utf-8'))
        if j['meta']['code_sha256']!=code:errors.append(str(path)+': stale source')
        if any(not np.isfinite(j['mass'][key]) or not 0<=j['mass'][key]<1e-6
               for key in ('residual_rel_max','residual_central_rel_max')):
            errors.append(str(path)+': nonfinite or excessive conservation residual')
        if not path.with_name('resolved_config.yaml').exists():errors.append(str(path)+': no portable replay config')
        c=j['cost']
        if abs(c['construction_cost']+c['monitoring_cost']-c['cost_used'])>1e-6:
            errors.append(str(path)+': cost components')
        for d in j['placements']['adaptive_decisions']:
            if d['action']=='approve':
                if d['best']['delta_E_b']<=0 or d['completion']-d['t']<1.75-1e-9:
                    errors.append(str(path)+': unsupported project approval')
                if d['uses_real_future_events']:errors.append(str(path)+': future-event leakage')
            if 'posterior_weights' in d and abs(sum(d['posterior_weights'])-1)>1e-12:
                errors.append(str(path)+': posterior normalization')
    mc_paths=list(root.glob('MC_*/summary.json'))
    if len(mc_paths)!=design['MC_groups_expected']:errors.append('MC group count')
    for path in mc_paths:
        j=json.loads(path.read_text(encoding='utf-8'))
        if not valid_mc_cache(j,('mc',str(root),j['scenario'],j['strategy'],design['n'])):
            errors.append(str(path)+': current parameter snapshot does not match cache')
        if j['code_sha256']!=code or j['n']!=design['n'] or len(j['runs'])!=design['n']:errors.append(str(path)+': version/count')
        if any(j['resolved_config'].get(k)!=j[k] for k in ('scenario','strategy','bc')):
            errors.append(str(path)+': incorrect effective controls')
        if 'width_trajectory' not in j:errors.append(str(path)+': missing time-space uncertainty')
        for r in j['runs']:
            if any(not np.isfinite(r[key]) or r[key]<0 for key in
                   ('residual_rel_max','residual_central_rel_max','placed_m3','cost_used','construction_cost','monitoring_cost')):
                errors.append(str(path)+': nonfinite or negative scalar')
            maximum=max(maximum,r['residual_rel_max'],r['residual_central_rel_max'])
            if abs(r['construction_cost']+r['monitoring_cost']-r['cost_used'])>1e-6:
                errors.append(str(path)+': MC cost components')
            if r['placed_m3']>2.45e6+1e-6 or r['cost_used']>120e6+1e-6:errors.append(str(path)+': resources')
            for kind in ('w','b'):
                exposure=r['E_'+kind]
                if not np.isfinite(exposure) or not -1e-7<=exposure<=75000+1e-7:errors.append(str(path)+': exposure')
                if abs(r['T_safe_cum_'+kind]+exposure/5000.-15.)>1e-8:errors.append(str(path)+': safe time')
                time=r['T_first_fail_'+kind];censored=r['T_first_fail_'+kind+'_censored']
                if (time is None)!=censored or (time is not None and not 0<=time<=15):errors.append(str(path)+': censoring')
    if maximum>=1e-6:errors.append('MC conservation')
    oat=root/'OAT_S2_once/oat.csv'
    if not oat.exists():errors.append('missing OAT')
    else:
        rows=list(csv.DictReader(oat.open(encoding='utf-8')))
        if len(rows)!=52*design['oat_seeds_per_value']:errors.append('OAT count')
        for r in rows:
            residual=float(r['residual_rel_max'])
            if not np.isfinite(residual) or not 0<=residual<1e-6:errors.append('OAT conservation')
    timing=root/'timing/runs.csv'
    if not timing.exists() or len(list(csv.DictReader(timing.open(encoding='utf-8'))))!=3*design['n']:
        errors.append('timing count')
    for group in ('transport','storm','economy'):
      for replicate, design_seed in enumerate(design.get('global_scrambles', [20261112])):
        suffix='' if replicate==0 else f'_rep{replicate+1}'
        path=root/f'GLOBAL_{group}{suffix}/summary.json'
        if not path.exists():errors.append('missing global '+group)
        else:
            j=json.loads(path.read_text(encoding='utf-8'))
            if j['code_sha256']!=code or j['n_base']!=design['global_base_n']:errors.append('global version/count '+group)
            if j['design_seed']!=design_seed:errors.append(str(path)+': wrong scramble')
            raw=list(csv.DictReader(path.with_name('design_outputs.csv').open(encoding='utf-8')))
            dimensions=len(j['ranges'])
            if len(raw)!=design['global_base_n']*(2+2*dimensions):errors.append('global design matrix count '+group)
            expected={(matrix,index) for matrix in ['A','B']+[f'{kind}{i}' for i in range(dimensions) for kind in ('AB','BA')]
                      for index in range(design['global_base_n'])}
            if {(r['matrix'],int(r['index'])) for r in raw}!=expected:
                errors.append(str(path)+': missing or duplicate design coordinates')
            if any(not np.isfinite(float(value)) for row in raw for key,value in row.items() if key.startswith('output_')):
                errors.append('nonfinite global outputs '+group)
    figures=list((root/'figures').glob('*.png'));pdfs=list((root/'figures').glob('*.pdf'))
    if len(figures)!=design['matlab_figure_pairs_expected'] or len(pdfs)!=len(figures):errors.append('MATLAB figure count')
    visual_path=root/'visual_QA.json'
    if not visual_path.exists():errors.append('missing manual visual QA')
    else:
        visual=json.loads(visual_path.read_text(encoding='utf-8'))
        if visual['status']!='PASS':errors.append('visual QA not passed')
        current={path.name:hashlib.sha256(path.read_bytes()).hexdigest() for path in figures+pdfs}
        if visual.get('figures')!=current:errors.append('figure files changed after visual QA')
        if visual.get('figure_code_sha256')!=hashlib.sha256(Path('matlab/plot_results.m').read_bytes()).hexdigest():
            errors.append('MATLAB plot source changed after visual QA')
    supplement_design=json.loads((root/'supplements/design.json').read_text(encoding='utf-8'))
    if supplement_design['code_sha256']!=code:errors.append('stale supplements')
    for name,n in [('joint',3000),('policy',500),('phase',4096)]:
        path=root/f'supplements/{name}_runs.csv'
        if not path.exists():errors.append('missing supplement '+name)
        else:
            rows=list(csv.DictReader(path.open(encoding='utf-8')))
            if len(rows)!=n:errors.append('supplement count '+name)
            if supplement_design['rows'].get(name)!=n:errors.append('supplement design count '+name)
            for row in rows:
                for key in ('E_b','E_w','T_safe_w','placed','cost','residual_rel'):
                    if not np.isfinite(float(row[key])):errors.append('nonfinite supplement '+name+': '+key)
                if not 0<=float(row['residual_rel'])<1e-6:errors.append('supplement conservation '+name)
                if not -1e-6<=float(row['placed'])<=2.45e6+1e-6 or not 0<=float(row['cost'])<=120e6+1e-6:
                    errors.append('supplement resources '+name)
                if abs(float(row['T_safe_w'])+float(row['E_w'])/5000-15)>1e-8:
                    errors.append('supplement safe time '+name)
            seed_groups={}
            for row in rows:
                group=(row['scenario'],row.get('setting',''),row.get('volume',''),row.get('w_min',''),row.get('strategy',''))
                seed_groups.setdefault(group,[]).append((int(row['index']),int(row['seed'])))
            expected_n=supplement_design[name+'_n']
            expected_pairs={(i,(4300*1000003+i)%2**32) for i in range(expected_n)}
            if any(len(rs)!=expected_n or set(rs)!=expected_pairs for rs in seed_groups.values()):
                errors.append('unpaired or incomplete supplement seeds '+name)
    if not (root/'sensitivity_convergence.json').exists():errors.append('missing replicated convergence analysis')
    else:
        convergence=json.loads((root/'sensitivity_convergence.json').read_text(encoding='utf-8'))
        if set(convergence['groups'])!={'transport','storm','economy'}:errors.append('incomplete convergence groups')
    if not (root/'history/holdout_fit.json').exists():errors.append('missing reduced historical holdout')
    policy_diagnostic=root/'policy_rule_diagnostic.json'
    if not policy_diagnostic.exists():errors.append('missing policy-rule diagnostic')
    elif json.loads(policy_diagnostic.read_text(encoding='utf-8'))!=diagnose(root):
        errors.append('stale policy-rule diagnostic')
    footprint=root/'footprint/runs.csv'
    if not footprint.exists():errors.append('missing footprint sensitivity')
    else:
        fp=json.loads(footprint.with_name('design.json').read_text(encoding='utf-8'))
        rows=list(csv.DictReader(footprint.open(encoding='utf-8')))
        if fp['code_sha256']!=code or len(rows)!=1200 or fp['runs']!=len(rows):errors.append('footprint source/count')
        footprint_groups={};marks={}
        for row in rows:
            footprint_groups.setdefault((row['strategy'],float(row['sigma_m'])),[]).append(int(row['index']))
            seed=int(row['seed']);marks.setdefault(seed,set()).add(row['mark_sha256'])
            if seed!=(4400*1000003+int(row['index']))%2**32:errors.append('footprint seed rule')
            if not np.isfinite(float(row['residual_rel'])) or not 0<=float(row['residual_rel'])<1e-6:
                errors.append('footprint mass balance')
            if not -1e-6<=float(row['placed'])<=2.45e6+1e-6 or not 0<=float(row['cost'])<=120e6+1e-6:
                errors.append('footprint resources')
            if not all(np.isfinite(float(row[k])) and 0<=float(row[k])<=75000 for k in ('E_b','E_w')):
                errors.append('footprint exposure')
        if len(footprint_groups)!=12 or any(sorted(v)!=list(range(100)) for v in footprint_groups.values()):errors.append('footprint cells')
        if any(len(v)!=1 for v in marks.values()):errors.append('unpaired footprint storm marks')
    report={'status':'PASS' if not errors else 'FAIL','errors':errors,'code_sha256':code,
        'deterministic_runs':len(deterministic),'MC_groups':len(mc_paths),'MC_runs':sum(
            len(json.loads(p.read_text(encoding='utf-8'))['runs']) for p in mc_paths),
        'MC_max_full_or_central_residual':maximum,'MATLAB_png':len(figures),'MATLAB_pdf':len(pdfs),
        'limits':'Numerical completeness only. Ensemble adaptive uses synthetic observations and assumed monitoring costs; Sobol diagnostics assess replication without guaranteeing convergence; no empirical posterior or independent field validation.'}
    write_json(root/'completeness.json',report);print(json.dumps(report,ensure_ascii=False,indent=2))
    if errors:raise SystemExit(1)


if __name__=='__main__':main()
