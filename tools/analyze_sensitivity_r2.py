"""Nested sample-size and independent-scramble diagnostics (no index clipping)."""
import argparse
import csv
import json
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import numpy as np
from src.sim.io import write_json,tree_sha256


def estimate(values,n,indices=None):
    v={k:a[:n] if indices is None else a[:n][indices] for k,a in values.items()}
    mean=np.mean(np.concatenate((v['A'],v['B'])),axis=0)
    variance=np.var(np.concatenate((v['A'],v['B'])),axis=0)
    centered={k:a-mean for k,a in v.items()}
    result=[]
    d=sum(k.startswith('AB') for k in v)
    for j in range(d):
        first=np.divide(np.mean(centered['B']*(centered[f'AB{j}']-centered['A']),axis=0),variance,
                         out=np.full_like(variance,np.nan),where=variance>1e-12)
        total=np.divide(.5*np.mean((v['A']-v[f'AB{j}'])**2,axis=0),variance,
                         out=np.full_like(variance,np.nan),where=variance>1e-12)
        result.extend((first,total))
    for j in range(d):
        for k in range(j+1,d):
            result.append(np.divide(np.mean(centered[f'BA{j}']*centered[f'AB{k}']-
                centered['A']*centered['B'],axis=0),variance,
                out=np.full_like(variance,np.nan),where=variance>1e-12)-result[2*j]-result[2*k])
    return np.array(result)


def read(path):
    summary=json.loads((path/'summary.json').read_text(encoding='utf-8'))
    with (path/'design_outputs.csv').open(encoding='utf-8') as handle:
        rows=list(csv.DictReader(handle))
    # write_json sorts object keys. Only the saved CSV preserves the parameter
    # order used to construct AB0/AB1/...; alphabetic ranges order is unsafe.
    summary['_parameter_order']=[key for key in rows[0] if key in summary['ranges']]
    labels=summary['output_labels'];names=sorted(set(r['matrix'] for r in rows))
    values={}
    for name in names:
        matrix_rows=sorted((r for r in rows if r['matrix']==name),key=lambda r:int(r['index']))
        if [int(r['index']) for r in matrix_rows]!=list(range(summary['n_base'])):
            raise RuntimeError(f'Missing or duplicate Sobol rows: {path} {name}')
        values[name]=np.array([[float(r[f'output_{j}']) for j in range(len(labels))] for r in matrix_rows])
    return summary,values


def number(value):
    return float(value) if np.isfinite(value) else None


def main():
    p=argparse.ArgumentParser();p.add_argument('--root',required=True);args=p.parse_args();root=Path(args.root)
    rows=[];warnings=[];groups={};code=tree_sha256('src');rng=np.random.default_rng(33661113)
    for group in ('transport','storm','economy'):
        s,v=read(root/f'GLOBAL_{group}');r,w=read(root/f'GLOBAL_{group}_rep2')
        if s['code_sha256']!=code or r['code_sha256']!=code:raise RuntimeError('stale Sobol outputs')
        if s['_parameter_order']!=r['_parameter_order']:raise RuntimeError('inconsistent matrix column order')
        n=s['n_base'];full=estimate(v,n);other=estimate(w,n)
        keys=s['_parameter_order']
        descriptors=[(key,order) for key in keys for order in ('first','total')]
        descriptors += [(keys[j]+':'+keys[k],'second') for j in range(len(keys)) for k in range(j+1,len(keys))]
        for i,(key,order) in enumerate(descriptors):
            for k,label in enumerate(s['output_labels']):
                saved=next(a['index'] for a in s['indices'] if
                    a['parameter']==key and a['order']==order and a['output']==label)
                if not ((saved is None and not np.isfinite(full[i,k])) or
                        (saved is not None and np.isclose(saved,full[i,k],rtol=1e-10,atol=1e-12))):
                    raise RuntimeError(f'Index/order mismatch: {group} {key} {order} {label}')
        bootstrap=np.stack([estimate(v,n,rng.integers(n,size=n)) for _ in range(200)])
        nested={k:estimate(v,k) for k in (64,128,256,512) if k<=n}
        keyrows=[];secondrows=[]
        for i,(key,order) in enumerate(descriptors):
                for k,label in enumerate(s['output_labels']):
                    valid=np.isfinite(full[i,k])
                    finite_boot=bootstrap[:,i,k][np.isfinite(bootstrap[:,i,k])]
                    lo,hi=np.quantile(finite_boot,[.025,.975]) if valid and len(finite_boot)>1 else (np.nan,np.nan)
                    change=abs(full[i,k]-nested[256][i,k]) if valid else np.nan
                    replication=abs(full[i,k]-other[i,k]) if valid else np.nan
                    stable=valid and change<=.10 and replication<=.10 and hi-lo<=.30
                    row={'group':group,'output':label,'parameter':key,'order':order,
                         **{f'N_{nn}':float(xx[i,k]) if np.isfinite(xx[i,k]) else None for nn,xx in nested.items()},
                         'replicate_N512':number(other[i,k]),
                         'bootstrap_diagnostic_lo':number(lo),
                         'bootstrap_diagnostic_hi':number(hi),
                         'difference_256_to_512':number(change),
                         'independent_scramble_difference':number(replication),
                         'stable_at_diagnostic_tolerance':bool(stable),
                         'status':'stable_diagnostic' if stable else 'unresolved_sampling' if valid else 'constant_output'}
                    rows.append(row)
                    if label=='local_once_E_b':
                        (secondrows if order=='second' else keyrows).append(row)
        groups[group]={'key_output':'local_once_E_b','indices':keyrows,
            'stable_key_estimates':sum(r['stable_at_diagnostic_tolerance'] for r in keyrows),
            'key_estimates':len(keyrows),'second_order_indices':secondrows,
            'stable_second_order_estimates':sum(r['stable_at_diagnostic_tolerance'] for r in secondrows),
            'second_order_estimates':len(secondrows),
            'parameter_matrix_order':keys,'n_base':n,'scrambles':[s['design_seed'],r['design_seed']]}
    with (root/'sensitivity_convergence.csv').open('w',encoding='utf-8',newline='') as h:
        writer=csv.DictWriter(h,fieldnames=list(rows[0]));writer.writeheader();writer.writerows(rows)
    write_json(root/'sensitivity_convergence.json',{'code_sha256':code,'groups':groups,
        'limits':'Nested doubling and two independent scrambled QMC designs completed. Row bootstrap is a diagnostic interval, not a rigorous confidence interval for QMC. Two storm seeds approximate a conditional mean, not storm-process uncertainty. Unresolved indices are retained without clipping and must not be reported as precise variance shares. Economic inputs are independent; min constraints cause interactions/inactive inputs, not input collinearity.'})
    print('CONVERGENCE', {g:(s['stable_key_estimates'],s['key_estimates']) for g,s in groups.items()})


if __name__=='__main__':main()
