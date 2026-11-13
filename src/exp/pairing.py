"""Counterfactual sand attribution. These are signed effects, not grain tags."""
import numpy as np
from src.sim.units import book_volume


def at_times(simulation, model, report_times):
    t=simulation.fields['t']; central=model.grid.central_mask
    inventory=(book_volume(simulation.fields['y'],model.w0,model.h,model.v_ref)+simulation.fields['O'])
    return np.array([np.interp(report_times,t,inventory[:,central].sum(axis=1)*model.grid.dx)]).ravel()


def fate_effects(sim,baseline,model):
    central=model.grid.central_mask
    footprint=np.zeros(len(model.grid.x),bool)
    for p in model.placements:
        footprint |= np.abs(model.grid.x-p.center)<p.length/2
    db=(book_volume(sim.fields['y'][-1],model.w0,model.h,model.v_ref)-
        book_volume(baseline.fields['y'][-1],model.w0,model.h,model.v_ref))*model.grid.dx
    return {'beach_original_footprint':float(db[footprint].sum()),
        'beach_other_central':float(db[central & ~footprint].sum()),
        'beach_buffers':float(db[~central & ~footprint].sum()),
        'nearshore_reservoir':float((sim.fields['O'][-1]-baseline.fields['O'][-1]).sum()*model.grid.dx),
        'boundary_net_outflow':sim.results['mass']['flux_out']-baseline.results['mass']['flux_out'],
        'permanent_offshore_loss':sim.results['mass']['offshore']-baseline.results['mass']['offshore'],
        'avoided_current_deficit':baseline.results['mass']['R_c']-sim.results['mass']['R_c']}
