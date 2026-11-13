"""Historical shoreline diagnostic; not an independent validation claim."""
import argparse
import csv
import hashlib
from pathlib import Path
import struct
import numpy as np
from src.sim.io import load_config, write_json
from src.sim.model import ShorelineModel


def read_dbf(path):
    blob = Path(path).read_bytes()
    n = struct.unpack_from('<I', blob, 4)[0]
    header, length = struct.unpack_from('<HH', blob, 8)
    fields = []
    for offset in range(32, header-1, 32):
        d = blob[offset:offset+32]
        if d[0] == 13:
            break
        fields.append((d[:11].split(b'\0')[0].decode('ascii'), chr(d[11]), d[16]))
    rows = []
    for i in range(n):
        record = blob[header+i*length:header+(i+1)*length]
        if record[:1] == b'*':
            continue
        row, offset = {}, 1
        for name, kind, width in fields:
            raw = record[offset:offset+width].decode('ascii').strip()
            offset += width
            row[name] = (float(raw) if raw else None) if kind in 'NF' else raw
        rows.append(row)
    return rows


def run(dbf, out):
    out = Path(out)
    out.mkdir(parents=True, exist_ok=True)
    rows = read_dbf(dbf)
    # Rule fixed before inspecting rate values; NAD83 UTM 18N northing window.
    chosen = [r for r in rows if r['StartY'] is not None and 3937500 <= r['StartY'] <= 3942500]
    summary = {'source_file':str(Path(dbf).resolve()),
        'source_sha256':hashlib.sha256(Path(dbf).read_bytes()).hexdigest(),
        'rule':'3937500 <= StartY <= 3942500 m; NAD83 UTM18N; no rate-based filtering',
        'n_all':len(rows), 'n_selected':len(chosen), 'observations':{},
        'limits':'Historical window, overlapping time periods; not independent of rate priors. Synthetic future corridor lacks georeferenced buildings/profiles. Metadata default shoreline-position accuracy is 4.4 m; this is not a slope error bar. DAS_km references an unrelated New York study area and is not used for selection.'}
    for field in ('LRR78_2002','LRR89_2002'):
        values = np.array([r[field] for r in chosen if r[field] is not None and np.isfinite(r[field]) and r[field] > -999])
        summary['observations'][field] = {'n':len(values),'mean_m_per_year':float(values.mean()),
            'median_m_per_year':float(np.median(values)),
            'p10_m_per_year':float(np.quantile(values,.1)),
            'p90_m_per_year':float(np.quantile(values,.9)),
            'min':float(values.min()),'max':float(values.max())}
    p = load_config(Path(__file__).resolve().parents[2]/'configs/S2.yaml')
    model = ShorelineModel(p,scenario='S2',boundary='open',storm_enabled=False)
    summary['model_chronic_corridor_mean_m_per_year'] = float(model._rho(0.)[model.grid.central_mask].mean())
    with (out/'selected_transects.csv').open('w',encoding='utf-8',newline='') as h:
        w = csv.DictWriter(h,fieldnames=list(chosen[0]));w.writeheader();w.writerows(chosen)
    write_json(out/'diagnostic.json',summary)
    return summary


def main(argv=None):
    p = argparse.ArgumentParser();p.add_argument('--dbf',required=True);p.add_argument('--out',required=True)
    args = p.parse_args(argv);run(args.dbf,args.out)


if __name__ == '__main__':
    main()
