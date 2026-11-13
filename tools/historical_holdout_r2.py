"""Train 1978-1989 rate field; hold out 1989-2002. Not full PDE validation.

The periods share the 1989 shoreline, so their rate errors can be correlated.
No uncertainty in shoreline position is reinterpreted as a regression-rate SE.
"""
import argparse
import csv
import hashlib
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import numpy as np
from scipy.optimize import least_squares
from src.exp.history import read_dbf
from src.sim.io import write_json


def rate(x,p):
    baseline,amplitude,sigma=p
    return baseline+amplitude*np.exp(-x*x/(2*sigma*sigma))


def score(y,pred):
    error=pred-y
    denom=float(np.sum((y-y.mean())**2))
    return {'n':len(y),'rmse_myr':float(np.sqrt(np.mean(error**2))),
        'mae_myr':float(np.mean(np.abs(error))),'bias_pred_minus_obs_myr':float(error.mean()),
        'R_squared':float(1-np.sum(error**2)/denom) if denom>0 else None}


def main():
    p=argparse.ArgumentParser();p.add_argument('--root',required=True);a=p.parse_args();out=Path(a.root)/'history'
    out.mkdir(parents=True,exist_ok=True);source=Path('data/raw/Hatteras_Transects.dbf')
    rows=[r for r in read_dbf(source) if 3937500<=r['StartY']<=3942500]
    fields=('LRR78_1989','LRR89_2002')
    valid=[r for r in rows if all(r[f] is not None and np.isfinite(r[f]) and r[f] not in (-999.,-9999.) for f in fields)]
    x=np.array([r['StartY']-3940000 for r in valid])
    train=-np.array([r[fields[0]] for r in valid]);test=-np.array([r[fields[1]] for r in valid])
    # Specification and bounds fixed before fitting; no test rates enter fit.
    opt=least_squares(lambda par:rate(x,par)-train,[2.,3.,700.],
                      bounds=([0.,0.,200.],[20.,30.,2000.]))
    pred=rate(x,opt.x);singular=np.linalg.svd(opt.jac,compute_uv=False)
    summary={'source_sha256':hashlib.sha256(source.read_bytes()).hexdigest(),
        'selection':'3937500<=StartY<=3942500; complete paired periods; missing sentinels only',
        'train_field':fields[0],'holdout_field':fields[1],'n_geographic':len(rows),'n_paired':len(valid),
        'coordinate':'StartY-3940000 in NAD83 UTM18N m; northing proxy, not surveyed alongshore arclength',
        'rate_sign':'positive=erosion; original LRR sign reversed',
        'fitted_model':'rho0 + A*exp(-x^2/(2*sigma^2)); center fixed at preselected corridor center',
        'parameters':dict(zip(('rho0_myr','A_myr','sigma_m'),map(float,opt.x))),
        'parameter_bounds':[[0.,20.],[0.,30.],[200.,2000.]],
        'active_parameter_bounds':opt.active_mask.tolist(),
        'jacobian_rank':int(np.linalg.matrix_rank(opt.jac)),
        'jacobian_condition':float(singular[0]/singular[-1]) if singular[-1]>0 else None,
        'train':score(train,pred),'temporal_holdout':score(test,pred),
        'holdout_constant_training_mean':score(test,np.full(len(test),train.mean())),
        'holdout_local_rate_persistence':score(test,train),
        'mean_train_retreat_myr':float(train.mean()),'mean_test_retreat_myr':float(test.mean()),
        'limits':'Reduced empirical net-rate field only, not calibration/validation of D,H,k,lambda or full storm PDE. Periods share 1989 shoreline, giving potentially correlated errors. Spatial samples are dependent, no regression-rate SE is supplied, and no independent local nourishment response is observed. A Gaussian shape may fail; test results never tune the fit. Parameters are not substituted into the synthetic future scenarios.'}
    write_json(out/'holdout_fit.json',summary)
    with (out/'holdout_predictions.csv').open('w',encoding='utf-8',newline='') as h:
        w=csv.DictWriter(h,fieldnames=['x_northing_proxy_m','train_retreat_myr','heldout_retreat_myr','predicted_retreat_myr'])
        w.writeheader();w.writerows(dict(zip(w.fieldnames,map(float,row))) for row in zip(x,train,test,pred))
    print(summary)


if __name__=='__main__':main()
