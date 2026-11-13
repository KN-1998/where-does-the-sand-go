"""Check realized dry-width retreat against assumed scenario target means."""
import argparse
import csv
import json
from pathlib import Path
import statistics
import math


def main():
    p=argparse.ArgumentParser();p.add_argument('--root',required=True);a=p.parse_args();root=Path(a.root)
    records=[]
    for scenario,target in [('S1',1.7),('S2',3.),('S3',4.)]:
        initial=json.loads((root/f'{scenario}_baseline/results.json').read_text(encoding='utf-8'))['initial']['w_mean']
        mc=json.loads((root/f'MC_{scenario}_none/summary.json').read_text(encoding='utf-8'))
        values=[(initial-r['w_end_mean'])/15 for r in mc['runs']]
        mean=statistics.mean(values);se=statistics.stdev(values)/math.sqrt(len(values))
        records.append({'scenario':scenario,'n':len(values),'scenario_time_mean_target_myr':target,
            'realized_dry_width_retreat_mean_myr':mean,'MCSE_myr':se,
            'MC_mean_CI95_low':mean-1.96*se,'MC_mean_CI95_high':mean+1.96*se,
            'relative_difference_from_target':(mean-target)/target,
            'exceeds_30percent':abs(mean-target)/target>.3})
    with (root/'erosion_target_diagnostic.csv').open('w',encoding='utf-8',newline='') as h:
        w=csv.DictWriter(h,fieldnames=list(records[0]));w.writeheader();w.writerows(records)
    (root/'erosion_target_diagnostic.md').write_text(
        '# Scenario target diagnostic\n\n'+
        '\n'.join(f"- {r['scenario']}: dry-width retreat mean {r['realized_dry_width_retreat_mean_myr']:.4f} m/yr; assumed target {r['scenario_time_mean_target_myr']:.2f}; difference {r['relative_difference_from_target']:+.1%}." for r in records)+
        '\n\nThis is a model consistency diagnostic, not observational validation. The wide-beach storm compensation is approximate: realized retreat includes width-limited storms, incomplete recovery and transport. The forced S2 event is additional to its Poisson pressure. S3 is nonstationary; 4 m/yr is the time average of its assumed endpoints. MC intervals cover storm sampling error only. No parameters are silently retuned.\n',encoding='utf-8')
    print(records)


if __name__=='__main__':main()
