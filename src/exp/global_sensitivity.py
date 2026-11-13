"""Independent-uniform Sobol experiment (exploratory, not fitted posteriors)."""
import copy
import csv
from pathlib import Path
import numpy as np
from scipy.stats import qmc
from src.sim.io import load_config, write_json, tree_sha256
from src.sim.model import ShorelineModel


GROUPS = {
 'transport':{'D_diff':(1e5,8e5),'rho_e':(1.,3.5),'u_drift':(0.,150.)},
 'storm':{'lambda_s':(.2,.8),'dy_ref':(4.,12.),'k_rec':(.33,1.)},
 'economy':{'V15_total':(3.5e6,6.8e6),'V_event_max':(1.5e6,3.5e6),
            'S_borrow_total':(1.5e6,3.2e6),'c1':(20.,35.)}}


def set_parameter(p,key,val):
    for section in ('transport','storm','management','geometry'):
        if key in p.get(section,{}):
            p[section][key]['value']=float(val)
            break
    if key in ('lambda_s','dy_ref'):
        p['scenarios']['S2_storm_soon'][key]=float(val)


def evaluate(p, group, seeds):
    outputs=[]
    for supply in (('local','external') if group=='economy' else ('local',)):
        p['management']['supply_scenario']['value']=supply
        for strategy in (('once','repeat','fixed_hotspot') if group=='economy' else ('once',)):
            runs=[ShorelineModel(p,scenario='S2',strategy=strategy,boundary='open',seed=s).run().results for s in seeds]
            for r in runs:
                if max(r['mass']['residual_rel_max'],r['mass']['residual_central_rel_max']) >= 1e-6:
                    raise ArithmeticError('global sensitivity run failed conservation')
            outputs.extend([np.mean([r['exposure']['E_b'] for r in runs]),
                np.mean([r['exposure']['E_w'] for r in runs]),
                np.mean([r['duration']['T_first_fail_w']['value'] if
                    r['duration']['T_first_fail_w']['value'] is not None else 15. for r in runs])])
    return outputs


def run(root, group, power=6, seed_count=2, design_seed=20261112):
    design=GROUPS[group];keys=list(design);d=len(keys);n=2**power
    unit=qmc.Sobol(2*d,scramble=True,seed=design_seed).random_base2(power)
    lo=np.array([design[k][0] for k in keys]);hi=np.array([design[k][1] for k in keys])
    a=lo+(hi-lo)*unit[:,:d];b=lo+(hi-lo)*unit[:,d:]
    base=load_config('configs/S2.yaml');seeds=[(4200*1000003+i)%2**32 for i in range(seed_count)]
    matrices={'A':a,'B':b}
    for j in range(d):
        ab=a.copy();ab[:,j]=b[:,j];matrices['AB'+str(j)]=ab
        ba=b.copy();ba[:,j]=a[:,j];matrices['BA'+str(j)]=ba
    vals={};rows=[]
    for name,points in matrices.items():
        out=[]
        for index,point in enumerate(points):
            p=copy.deepcopy(base)
            for k,v in zip(keys,point):set_parameter(p,k,v)
            vector=evaluate(p,group,seeds);out.append(vector)
            rows.append({'matrix':name,'index':index,**{k:float(v) for k,v in zip(keys,point)},
                         **{'output_'+str(i):float(v) for i,v in enumerate(vector)}})
        vals[name]=np.array(out)
    labels=[]
    for supply in (('local','external') if group=='economy' else ('local',)):
        for strategy in (('once','repeat','fixed_hotspot') if group=='economy' else ('once',)):
            labels.extend([supply+'_'+strategy+'_'+s for s in ('E_b','E_w','T_first_fail_w_restricted15')])
    variance=np.var(np.concatenate((vals['A'],vals['B'])),axis=0)
    mean=np.mean(np.concatenate((vals['A'],vals['B'])),axis=0)
    v={k:x-mean for k,x in vals.items()}
    first=[];total=[]
    for j in range(d):
        first.append(np.divide(np.mean(v['B']*(v['AB'+str(j)]-v['A']),axis=0),variance,
                               out=np.full_like(variance,np.nan),where=variance>1e-12))
        total.append(np.divide(.5*np.mean((v['A']-v['AB'+str(j)])**2,axis=0),variance,
                               out=np.full_like(variance,np.nan),where=variance>1e-12))
    effects=[]
    for i,label in enumerate(labels):
        for j,key in enumerate(keys):
            effects.append({'output':label,'parameter':key,'order':'first',
                'index':float(first[j][i]) if np.isfinite(first[j][i]) else None})
            effects.append({'output':label,'parameter':key,'order':'total',
                'index':float(total[j][i]) if np.isfinite(total[j][i]) else None})
        for j in range(d):
            for k in range(j+1,d):
                second=(np.mean(v['BA'+str(j)][:,i]*v['AB'+str(k)][:,i]-v['A'][:,i]*v['B'][:,i])/
                        variance[i]-first[j][i]-first[k][i]) if variance[i]>1e-12 else None
                effects.append({'output':label,'parameter':keys[j]+':'+keys[k],'order':'second','index':second})
    root=Path(root);root.mkdir(parents=True,exist_ok=True)
    for filename,records in (('design_outputs.csv',rows),('indices.csv',effects)):
        with (root/filename).open('w',encoding='utf-8',newline='') as h:
            w=csv.DictWriter(h,fieldnames=list(records[0]));w.writeheader();w.writerows(records)
    summary={'group':group,'n_base':n,'design_seed':design_seed,'seeds':seeds,'ranges':design,'code_sha256':tree_sha256('src'),
        'output_labels':labels,'indices':effects,
        'limits':'Exploratory Sobol first/total/second order; independent uniform design ranges, not posterior priors. Common storm seeds average stochastic outputs; low sample/seed count may give negative or >1 estimates. Do not rank uncertain indices without replication/convergence. Restricted failure time caps right-censored realizations at 15 solely for sensitivity, not reported as observed failure.'}
    if group=='economy':
        summary['ranking_counts']={}
        for si,supply in enumerate(('local','external')):
            exposures=vals['A'][:,[si*9,si*9+3,si*9+6]]
            winners=np.argmin(exposures,axis=1)
            summary['ranking_counts'][supply]={name:int(np.count_nonzero(winners==i)) for i,name in enumerate(('once','repeat','fixed_hotspot'))}
    write_json(root/'summary.json',summary)
    return summary
