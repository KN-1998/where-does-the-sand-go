"""Export paired S1 layout E_w quantiles from the frozen R2 ensemble."""
import argparse
import csv
import hashlib
import json
from pathlib import Path

import numpy as np


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--root', type=Path, default=Path(__file__).resolve().parents[1] / 'results/release_20261113_r2')
    args = parser.parse_args()
    rows = []
    reference_pairs = None
    for strategy in ('uniform', 'multi', 'hotspot'):
        source = args.root / f'MC_S1_{strategy}' / 'summary.json'
        summary = json.loads(source.read_text(encoding='utf-8'))
        pairs = [(run['index'], run['seed']) for run in summary['runs']]
        if reference_pairs is None:
            reference_pairs = pairs
        if pairs != reference_pairs:
            raise ValueError('Layout ensembles do not have matching paired seeds')
        values = np.asarray([run['E_w'] for run in summary['runs']], dtype=float)
        p10, p50, p90 = np.quantile(values, [.1, .5, .9], method='linear')
        rows.append(dict(scenario=summary['scenario'], strategy=strategy, n=len(values),
                         E_w_P10=p10, E_w_P50=p50, E_w_P90=p90, units='m*yr',
                         quantile_method='linear', source_sha256=hashlib.sha256(source.read_bytes()).hexdigest()))
    output = args.root / 'layout_quantiles.csv'
    with output.open('w', encoding='utf-8', newline='') as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    print(output)


if __name__ == '__main__':
    main()
