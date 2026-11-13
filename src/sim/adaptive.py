"""Observable-state rolling ensemble policy. All surveys here are SYNTHETIC.

The controller never receives the realized future event table or latent O.
The reduced forecast uses the same FV donor-limited BE equations, with
multiple candidate right-hand sides solved together. Its coarser grid is an
explicit decision approximation, checked separately against the full solver.
"""
import copy
import numpy as np
from scipy.linalg import solve_banded
from .grid import Grid, _face_coefficients
from .io import value
from .metrics import reconstructed_risk_metrics, spatial_failure_fraction
from .storms import generate_events
from .strategies import Placement, apply_placement, cost_terms, feasible_volume, snap_up, supply_cap


def smooth(values, n):
    n = max(1, int(n)); left = (n-1)//2
    return np.convolve(np.pad(values, (left, n-1-left), mode='edge'),
                       np.ones(n)/n, mode='valid')


def batch_transport(y, source, w0, dt, grid, D, u, boundary, y_boundary=None):
    """Exactly the production BE/face limiter, with candidate rows batched."""
    n = y.shape[-1]
    l, r, c = _face_coefficients(n, grid.dx, D, u, boundary, y_boundary)
    bands = np.zeros((3, n))
    bands[0, 1:] = dt*r[1:-1]/grid.dx
    bands[1] = 1-dt*(r[:-1]-l[1:])/grid.dx
    bands[2, :-1] = -dt*l[1:-1]/grid.dx
    src = y+dt*source
    pred = solve_banded((1, 1), bands, (src+dt*(c[:-1]-c[1:])/grid.dx).T,
                        check_finite=False).T
    flux = np.broadcast_to(c, (y.shape[0], n+1)).copy()
    flux[:, 0] += r[0]*pred[:, 0]; flux[:, -1] += l[-1]*pred[:, -1]
    flux[:, 1:-1] += l[1:-1]*pred[:, :-1]+r[1:-1]*pred[:, 1:]
    outgoing = dt*(np.maximum(flux[:, 1:], 0)+np.maximum(-flux[:, :-1], 0))
    available = np.maximum(w0+src, 0)*grid.dx
    scale = np.minimum(1, np.divide(available, outgoing, out=np.ones_like(y), where=outgoing>0))
    factors = np.ones_like(flux)
    factors[:, 1:] = np.where(flux[:, 1:] > 0, scale, factors[:, 1:])
    factors[:, :-1] = np.where(flux[:, :-1] < 0, scale, factors[:, :-1])
    flux *= factors
    return src+dt/grid.dx*(flux[:, :-1]-flux[:, 1:])


class AdaptiveController:
    def __init__(self, model):
        self.m = model
        self.p = model.params
        self.options = self.p.get('adaptive_options', {})
        self.rng = np.random.default_rng(np.random.SeedSequence([model.seed, 71071]))
        self.baseline = None
        self.last = -1e90
        if model.strategy=='targeted' and model.placements: self.last=0.
        self.logs = []
        self.monitor_cost = 0.
        self.survey_cost = float(self.options.get('survey_cost_usd', 50000.))
        self.bank = None
        self.banks = []
        self.reset_reference = False
        self.particles = np.array([(rho, D) for rho in (.8, 1., 1.2) for D in (.7, 1., 1.3)])
        self.weights = np.full(len(self.particles), 1/len(self.particles))
        self.last_survey = None

    def next_monitor_times(self, t):
        return sorted(set(x for bank in self.banks for x in bank['times'] if x > t+1e-9))

    def survey(self, t, y, offshore):
        """Synthetic instrument: noisy shoreline AND nearshore profile survey.

        O is not handed to the planner. This instrument adds independent
        error to the latent volume, and is an ASSUME measurement capability.
        Real observations can replace this method without changing choose().
        """
        if self.last_survey is not None and abs(t-self.last_survey) < 1e-9:
            return None
        self.last_survey = t
        sigma = float(value(self.p, 'management', 'sigma_m', 3.))
        raw_y = y+self.rng.normal(0, sigma, len(y))
        obs_y = smooth(raw_y, round(500/self.m.grid.dx))
        sigma_o = float(self.options.get('nearshore_sigma_m2', 30.))
        obs_o = np.maximum(0., smooth(offshore+self.rng.normal(0, sigma_o, len(y)),
                                      round(500/self.m.grid.dx)))
        self.monitor_cost += self.survey_cost
        return raw_y, obs_y, obs_o

    def _review_bank(self, t, observed):
        if self.bank is None:
            return False
        hits = [i for i, x in enumerate(self.bank['times']) if abs(x-t) < 1e-8]
        if not hits:
            return False
        i = hits[0]
        observed = np.interp(self.bank['x'], self.m.grid.x, observed)
        forecast = self.bank['predictions'][:, i]
        median = np.median(forecast, axis=0)
        ref = self.bank['reference']
        central = np.abs(self.bank['x']) < self.m.grid.central_half_length
        discrepancy = float(np.sqrt(np.mean((observed[central]-median[central])**2)))
        scale = max(3., float(np.sqrt(np.mean((median[central]-ref[central])**2))))
        update = discrepancy/scale > .30
        log = {'t':float(t), 'action':'monitor_review', 'relative_rmse':discrepancy/scale,
               'rmse_m':discrepancy, 'posterior_updated':update,
               'evidence':'synthetic survey; predictive mismatch is not uniquely parameter error'}
        if update:
            # Approximate predictive likelihood, block scale 500 m; variance
            # includes ensemble spread and a 3 m structural-error floor.
            variance = np.var(forecast, axis=0)+9.
            ll = -.5*np.mean((forecast[:, central]-observed[central])**2/
                            variance[central], axis=1)
            likelihood = np.exp(np.clip(ll-ll.max(), -50, 0))
            posterior = np.full(len(self.particles), 1e-3)
            for particle, prob in zip(self.bank['particle_ids'], likelihood):
                posterior[particle] += prob
            posterior /= posterior.sum()
            self.weights = .9*posterior+.1/len(posterior)
            log['posterior_weights'] = self.weights.tolist()
            log['effective_particles'] = float(1/np.sum(self.weights**2))
        self.logs.append(log)
        return update

    def _review(self,t,observed):
        updated=False
        for bank in self.banks:
            self.bank=bank
            updated=self._review_bank(t,observed) or updated
        return updated

    def choose(self, t, obs_y, obs_o, volume, horizon=None):
        """Five-year paired independent-storm forecast; cost-normalized E_b."""
        m, opt = self.m, self.options
        horizon = min(float(opt.get('forecast_years', 5.)) if horizon is None else horizon,
                      m.t_end-t)
        n_members = int(opt.get('members', 8))
        dx = float(opt.get('forecast_dx', 100.))
        dt = float(opt.get('forecast_dt', .10))
        g = Grid.build(m.grid.half_length, dx, m.grid.central_half_length)
        w0 = np.interp(g.x, m.grid.x, m.w0)
        y0, o0 = (np.interp(g.x, m.grid.x, a) for a in (obs_y, obs_o))
        delay = float(value(self.p,'management','permit_delay'))+float(value(self.p,'management','tau_build'))
        completion = snap_up(t+delay, m.dt)
        lengths = opt.get('candidate_lengths_m', [1000.,2000.])
        centers = opt.get('candidate_centers_m', [-1500.,0.,1500.])
        shares = opt.get('volume_shares', [.5,1.])
        candidates = [(float(c),float(l),float(volume*s)) for c in centers for l in lengths
                      for s in shares if abs(c)+l/2 <= g.central_half_length+1e-9 and
                      volume*s >= float(value(self.p,'management','V_min_meaningful',1e5))]
        candidates = [(0.,0.,0.)]+candidates
        count = len(candidates)
        Eb = np.zeros((n_members,count)); tf = np.full((n_members,count), horizon)
        censored = np.ones((n_members,count), bool)
        monitor_times = [completion+offset for offset in (.5,1.,2.) if completion+offset <= t+horizon+1e-9]
        predictions = []
        fseed = np.random.SeedSequence([m.seed, 924731, int(round(t*1000000))])
        rng = np.random.default_rng(fseed)
        # Separate forecast seeds from reality and from survey RNG.
        ids = rng.choice(len(self.particles), size=n_members, p=self.weights)
        threshold = float(value(self.p,'management','f_thr'))
        offset = float(value(self.p,'beach_state','d_bldg'))-float(value(self.p,'beach_state','m_safe'))
        for member, particle in enumerate(ids):
            rho_mult, D_mult = self.particles[particle]
            fp = copy.deepcopy(self.p)
            # Forced actual S2 stress event is deliberately invisible to policy.
            fp['scenarios']['S2_storm_soon']['forced_event_at'] = t+horizon+1
            events = [e for e in generate_events(fp,m.scenario,t+horizon,int(rng.integers(2**32)))[0]
                      if e.time > t+1e-9]
            yy = np.broadcast_to(y0,(count,len(g.x))).copy()
            oo = np.broadcast_to(o0,(count,len(g.x))).copy()
            schedule = sorted(set([t,t+horizon,completion] +
                list(np.arange(t+dt,t+horizon,dt))+[e.time for e in events]+monitor_times))
            schedule = [x for x in schedule if t-1e-9 <= x <= t+horizon+1e-9]
            ts, hist = [t], [yy.copy()]
            monitor_hist = []
            for a,b in zip(schedule[:-1],schedule[1:]):
                h = b-a
                total = m.k+m.lam
                after = oo*np.exp(-total*h)
                rec = (oo-after)*m.k/total if total else np.zeros_like(oo)
                rho = np.interp(g.x,m.grid.x,m._rho((a+b)/2))*rho_mult
                yy = batch_transport(yy,rec/(m.h*h)-rho,w0,h,g,
                     m._diffusivity((a+b)/2)*D_mult,m.drift,m.boundary,m.y_boundary)
                oo = after
                ts.append(b); hist.append(yy.copy())
                for e in events:
                    if abs(e.time-b)<1e-9:
                        effective = np.maximum(w0+yy,0)
                        dy = np.minimum(e.potential_retreat*(1-np.exp(-effective/m.w_sat)),effective)
                        yy -= dy; oo += m.h*dy
                        ts.append(b); hist.append(yy.copy())
                if abs(b-completion)<1e-9:
                    for j,(center,length,v) in enumerate(candidates[1:],1):
                        yy[j] = apply_placement(yy[j],v,center,length,g,m.h)[0]
                    ts.append(b); hist.append(yy.copy())
                if any(abs(b-q)<1e-9 for q in monitor_times):
                    monitor_hist.append(yy.copy())
            hist = np.asarray(hist)
            for j in range(count):
                first,_,exposure = reconstructed_risk_metrics(ts,hist[:,j,g.central_mask]+offset,threshold)
                Eb[member,j] = exposure*g.central_mask.sum()*g.dx
                censored[member,j] = first['censored']
                if first['value'] is not None: tf[member,j] = first['value']-t
            predictions.append(np.asarray(monitor_hist))
        unit,fixed = cost_terms(self.p)
        rows=[]
        q = float(opt.get('protection_quantile', .1))
        for j,(center,length,v) in enumerate(candidates[1:],1):
            benefit=float(np.mean(Eb[:,0]-Eb[:,j])); cost=unit*v+fixed
            lower=float(np.quantile(tf[:,j],q))
            rows.append({'center':center,'length':length,'volume':v,'delta_E_b':benefit,
                         'cost':cost,'score':benefit/max(cost,1.),'protection_q10':lower,
                         'first_fail_censored_count':int(censored[:,j].sum()),'candidate_index':j})
        best=max(rows,key=lambda r:r['score']) if rows else None
        log={'forecast_horizon':horizon,'members':n_members,'forecast_dx':dx,'forecast_dt':dt,
             'candidates':rows,'E_b_base_mean':float(Eb[:,0].mean()),'parameter_weights':self.weights.tolist(),
             'forecast_seed_entropy':list(fseed.entropy),'completion':completion,
             'uses_real_future_events':False,'protection_origin':'decision time; censored at forecast end'}
        if best is None or best['delta_E_b'] <= float(opt.get('minimum_benefit_myr',1e-6)):
            log.update(action='wait',reason='no_positive_forecast_building_benefit')
        elif m.strategy=='adaptive' and best['protection_q10'] < float(value(self.p,'management','T_min',3.)):
            log.update(action='retreat_assessment',reason='forecast_protection_below_minimum',best=best)
        elif horizon < float(value(self.p,'management','T_min',3.)):
            log.update(action='wait',reason='insufficient_forecast_window',best=best)
        else:
            j=best['candidate_index']
            log.update(action='approve',reason='largest_avoided_E_b_per_construction_dollar',best=best)
            self.bank={'times':monitor_times,'x':g.x,'reference':y0,
                       'predictions':np.asarray(predictions)[:,:,j,:], 'particle_ids':ids}
        return log

    def observe(self,t,y,offshore,placed,projects,pending):
        quarter = abs(t/.25-round(t/.25)) < 1e-8
        monitoring = any(abs(t-x)<1e-8 for x in self.next_monitor_times(t-1e-7))
        if not (quarter or monitoring or self.reset_reference): return None
        survey = self.survey(t,y,offshore)
        if survey is None: return None
        raw, obs, oo = survey
        update = self._review(t,obs)
        central = self.m.grid.central_mask
        fw=float(spatial_failure_fraction((self.m.w0+obs-float(value(self.p,'beach_state','w_mgmt')))[central]))
        if self.reset_reference:
            self.baseline=fw; self.reset_reference=False
            self.logs.append({'t':float(t),'action':'completion_survey','f_w':fw})
        hard=bool(np.any((float(value(self.p,'beach_state','d_bldg'))+raw)[central] <
                        float(value(self.p,'beach_state','m_safe'))+2))
        if self.baseline is None:
            self.baseline=fw
            volume=feasible_volume(self.p,float(value(self.p,'management','V_event_max')),
                                   placed,self.monitor_cost)
            initial=self.choose(t,obs,oo,volume)
            initial.update(t=float(t),action='initial_assessment',reason='survey_only_no_construction')
            self.bank=None
            self.logs.append(initial);return None
        trigger=fw-self.baseline >= float(value(self.p,'management','delta_f_trig',.1)) or hard or update
        cooldown=float(value(self.p,'management','permit_delay'))+float(value(self.p,'management','tau_build'))+float(value(self.p,'management','cooldown_extra',1.))
        if not trigger or pending or t-self.last < cooldown:
            self.logs.append({'t':float(t),'action':'wait','reason':'pending_project' if pending else
                              'cooldown' if t-self.last<cooldown else 'no_trigger','f_w':fw})
            return None
        if self.m.strategy=='targeted' and projects>=4:
            self.logs.append({'t':float(t),'action':'wait','reason':'four_project_limit'})
            return None
        unit,fixed=cost_terms(self.p)
        # Reserve scheduled quarterly surveys through the stated horizon.
        reserve=np.floor((self.m.t_end-t)/.25+1e-9)*self.survey_cost
        volume=feasible_volume(self.p,float(value(self.p,'management','V_event_max')),placed,
                               placed*unit+projects*fixed+self.monitor_cost+reserve+
                               (4+len(self.next_monitor_times(t)))*self.survey_cost)
        if self.m.strategy=='targeted': volume=min(volume,supply_cap(self.p)/4.)
        if volume < float(value(self.p,'management','V_min_meaningful',1e5)):
            self.logs.append({'t':float(t),'action':'retreat_assessment','reason':'resource_cap'})
            self.last=t; return None
        log=self.choose(t,obs,oo,volume)
        log.update(t=float(t),f_w=fw,synthetic_observations=True)
        self.logs.append(log);self.last=t
        if log['action']!='approve': return None
        self.banks.append(self.bank)
        b=log['best'];self.baseline=fw
        return Placement(log['completion'],b['volume'],b['center'],b['length'],'adaptive',
                         t+float(value(self.p,'management','permit_delay'))+float(value(self.p,'management','tau_build')))
