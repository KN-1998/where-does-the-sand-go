"""Run independently reproducible cross-implementation regression probes."""
import argparse
from dataclasses import replace
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import numpy as np
from src.sim.io import load_config, write_json
from src.sim.model import ShorelineModel


def main():
    ap=argparse.ArgumentParser();ap.add_argument('--upstream',required=True);ap.add_argument('--out',required=True)
    args=ap.parse_args();sys.path.insert(0,str(Path(args.upstream)/'src'))
    from sim.params import load_params, Scenario, RunConfig
    from sim.model import Simulator
    from sim.placements import make_strategy
    from sim.storms import EventTable, StormEvent
    p=load_params().clone_with({'rho_e':0.,'rho_e_hotspot_amp':0.,'u_drift':0.,'lambda_s':0.,
                               'w0_far':25.,'w0_min':25.})
    scenario=Scenario('base',p)
    run=RunConfig(scenario='base',strategy='none',bc='open',t_end=1.,dt=.01)
    y=np.full(360,-40.)
    results={}
    for collect in (True,False):
        sim=Simulator(p,scenario,run,y0=y)
        res=sim.run_loop(events=EventTable(events=[]),strategy=make_strategy(p,run,sim.budget,placements=[]),collect=collect)
        results[str(collect)]={'E_b':res.metrics['E_b'],'T_first_fail_b':res.metrics['T_first_fail_b']}
    terminal=Simulator(p,scenario,run)
    r=terminal.run_loop(events=EventTable(events=[StormEvent(t=1.,dy_pot=30.)]),
        strategy=make_strategy(p,run,terminal.budget,placements=[]))
    results['terminal_event']={'reported_E_w':r.metrics['E_w'],'expected_E_w':0.,
                               'reported_first_fail_w':r.metrics['T_first_fail_w'],'expected_first_fail_w':1.}
    pp=load_config('configs/S1.yaml')
    pp['transport']['u_drift']['value']=0.
    pp['beach_state']['w0_far']['value']=25.;pp['beach_state']['w0_min']['value']=25.
    y=np.exp(-terminal.grid.x**2/(2*300.**2))
    sim=Simulator(p,scenario,run,y0=y)
    up=sim.run_loop(events=EventTable(events=[]),strategy=make_strategy(p,run,sim.budget,placements=[]))
    local=ShorelineModel(pp,scenario='S1',boundary='open',dt=.01,t_end=1.,rho_override=0.,
                         events=[],initial_y=y).run()
    results['matched_no_floor_transport']={'max_abs_y_difference_m':float(np.max(np.abs(up.y_end-local.fields['y'][-1]))),
        'local_relative_mass_residual':local.results['mass']['residual_rel_max']}
    results['source']={'upstream_ref':'origin/code @ 1e32280 / code-r1','export_path':args.upstream,
                      'interpretation':'Tests passing do not establish forecast metrics or jump timing correctness.'}
    write_json(args.out,results);print(results)


if __name__=='__main__':main()
