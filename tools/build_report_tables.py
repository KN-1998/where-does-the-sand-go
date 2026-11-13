"""Flatten audited Monte Carlo summaries without imputing censored times."""
import argparse
import csv
import json
from pathlib import Path
import numpy as np


def main():
    p=argparse.ArgumentParser();p.add_argument('--root',default='results/release_20261113')
    args=p.parse_args();root=Path(args.root);rows=[];summaries={}
    for path in sorted(root.glob('MC_*/summary.json')):
        data=json.loads(path.read_text(encoding='utf-8'))
        summaries[(data['scenario'],data['strategy'])]=data
        baseline=json.loads((root/f"MC_{data['scenario']}_none"/'summary.json').read_text(encoding='utf-8'))
        if data['event_table_hashes']!=baseline['event_table_hashes']:
            raise RuntimeError('Comparison requires paired storms')
        runs=data['runs'];base=baseline['runs']
        if [r['seed'] for r in runs]!=[r['seed'] for r in base]:raise RuntimeError('Unpaired seeds')
        row={'scenario':data['scenario'],'strategy':data['strategy'],'n':data['n'],
             'E_b_p10':data['quantiles']['E_b']['p10'],'E_b_p50':data['quantiles']['E_b']['p50'],
             'E_b_p90':data['quantiles']['E_b']['p90'],
             'E_w_p50':data['quantiles']['E_w']['p50'],
             'T_first_b_KM_p50':data['kaplan_meier']['b']['p50'],
             'T_first_b_censored_n':data['kaplan_meier']['b']['censored_count'],
             'mean_placed_m3':float(np.mean([r['placed_m3'] for r in runs])),
             'mean_n_projects':float(np.mean([r['n_projects'] for r in runs])),
             'mean_construction_cost_usd':float(np.mean([r['construction_cost'] for r in runs])),
             'mean_monitoring_cost_usd':float(np.mean([r['monitoring_cost'] for r in runs])),
             'mean_cost_usd':float(np.mean([r['cost_used'] for r in runs]))}
        for metric in ('E_b','E_w'):
            benefit=np.array([b[metric]-r[metric] for b,r in zip(base,runs)])
            mean=float(benefit.mean());se=float(benefit.std(ddof=1)/np.sqrt(len(benefit)))
            row['paired_mean_avoided_'+metric]=mean
            row['MCSE_avoided_'+metric]=se
            row['mean_CI95_lo_'+metric]=mean-1.96*se
            row['mean_CI95_hi_'+metric]=mean+1.96*se
        rows.append(row)
    with (root/'mc_comparison.csv').open('w',encoding='utf-8',newline='') as h:
        writer=csv.DictWriter(h,fieldnames=list(rows[0]));writer.writeheader();writer.writerows(rows)
    print('wrote mc_comparison.csv:',len(rows),'groups')
    comparisons=[]
    for scenario in ('S1','S2','S3'):
        reference=summaries.get((scenario,'once'))
        if reference is None:continue
        for strategy in ('repeat','targeted','adaptive'):
            candidate=summaries.get((scenario,strategy))
            if candidate is None:continue
            base,runs=reference['runs'],candidate['runs']
            if [r['seed'] for r in base]!=[r['seed'] for r in runs]:raise RuntimeError('Unpaired policy comparison')
            row={'scenario':scenario,'policy_minus_once':strategy,'n':len(runs)}
            for metric in ('E_b','E_w'):
                differences=np.array([r[metric]-b[metric] for b,r in zip(base,runs)])
                se=float(differences.std(ddof=1)/np.sqrt(len(differences)))
                row[metric+'_mean_difference']=float(differences.mean())
                row[metric+'_MCSE']=se
                row[metric+'_mean_CI95_lo']=float(differences.mean()-1.96*se)
                row[metric+'_mean_CI95_hi']=float(differences.mean()+1.96*se)
            row['mean_cost_difference_usd']=float(np.mean([r['cost_used']-b['cost_used'] for b,r in zip(base,runs)]))
            row['mean_placed_difference_m3']=float(np.mean([r['placed_m3']-b['placed_m3'] for b,r in zip(base,runs)]))
            comparisons.append(row)
    if comparisons:
        with (root/'policy_pairwise.csv').open('w',encoding='utf-8',newline='') as h:
            writer=csv.DictWriter(h,fieldnames=list(comparisons[0]));writer.writeheader();writer.writerows(comparisons)
    economic=root/'GLOBAL_economy/design_outputs.csv'
    if economic.exists():
        design=list(csv.DictReader(economic.open(encoding='utf-8')))
        labels=json.loads(economic.with_name('summary.json').read_text(encoding='utf-8'))['output_labels']
        ranking=[]
        for supply in ('local','external'):
            counts={}
            names=('once','repeat','fixed_hotspot')
            columns=[labels.index(supply+'_'+s+'_E_b') for s in names]
            for r in design:
                if r['matrix']!='A':continue
                values=np.array([float(r['output_'+str(c)]) for c in columns])
                best=np.flatnonzero(values<=values.min()+1e-6)
                key='+'.join(names[i] for i in best);counts[key]=counts.get(key,0)+1
            for name,count in counts.items():ranking.append({'supply':supply,
                'best_set_with_ties':name,'n_of_design_points':count,
                'base_n':json.loads(economic.with_name('summary.json').read_text(encoding='utf-8'))['n_base'],'storm_seeds':2})
        with economic.with_name('ranking_with_ties.csv').open('w',encoding='utf-8',newline='') as h:
            writer=csv.DictWriter(h,fieldnames=list(ranking[0]));writer.writeheader();writer.writerows(ranking)


if __name__=='__main__':main()
