"""Censor-aware statistics. Recovery observations are event-cell pairs."""
import numpy as np


def length_risk_metrics(times, margins, fraction_threshold):
    """Integrate unsafe length with linear crossings between saved states.

    Repeated times are instantaneous jumps, with no exposure assigned to
    the preceding interval. First failure is the infimum crossing time.
    """
    times = np.asarray(times, dtype=float)
    margins = np.asarray(margins, dtype=float)
    risk = margins < 0.0
    steps = np.diff(times)
    before, after = margins[:-1], margins[1:]
    changed = risk[:-1] != risk[1:]
    crossing = np.divide(before, before - after, out=np.zeros_like(before),
                         where=changed)
    unsafe_fraction = risk[:-1].astype(float)
    unsafe_fraction[changed & ~risk[:-1]] = 1.0 - crossing[changed & ~risk[:-1]]
    unsafe_fraction[changed & risk[:-1]] = crossing[changed & risk[:-1]]
    exposure_per_length = float(np.sum(steps * unsafe_fraction.mean(axis=1)))
    needed = int(np.ceil(margins.shape[1] * fraction_threshold - 1e-10))
    first = None
    for index, row in enumerate(risk):
        if int(row.sum()) >= needed:
            first = float(times[index])
            break
        if index == len(steps) or steps[index] == 0:
            continue
        cells = np.flatnonzero(changed[index])
        if not cells.size:
            continue
        fractions = crossing[index, cells]
        order = np.argsort(fractions)
        delta = np.where(risk[index + 1, cells[order]], 1, -1)
        unique, starts = np.unique(fractions[order], return_index=True)
        counts = int(row.sum()) + np.cumsum(np.add.reduceat(delta, starts))
        hits = np.flatnonzero(counts >= needed)
        if hits.size:
            first = float(times[index] + steps[index] * unique[hits[0]])
            break
    return ({"value": first, "censored": first is None},
            float(times[-1] - times[0] - exposure_per_length), exposure_per_length)


def historical_deficit(width, h, dx):
    return float(np.maximum(-np.asarray(width), 0.0).max(axis=0).sum() * h * dx)


def spatial_failure_fraction(margins):
    """Unsafe length of a linear reconstruction through cell centres.

    Constant half-cells close the two reporting-domain ends. This avoids
    the one-cell timing bias of a staircase spatial indicator.
    """
    a = np.asarray(margins, dtype=float)
    left, right = a[..., :-1], a[..., 1:]
    neg_l, neg_r = left < 0, right < 0
    changed = neg_l != neg_r
    cross = np.divide(left, left - right, out=np.zeros_like(left), where=changed)
    portions = np.where(changed, np.where(neg_l, cross, 1.0 - cross), neg_l)
    return (portions.sum(axis=-1) + .5 * (a[..., 0] < 0) +
            .5 * (a[..., -1] < 0)) / a.shape[-1]


def _unsafe_time(a, b):
    changed = (a < 0) != (b < 0)
    root = np.divide(a, a-b, out=np.zeros_like(a), where=changed)
    return np.where(changed, np.where(a < 0, root, 1-root), a < 0)


def _edge_time_integral(a, b):
    """Exact time integral for linear-in-time, linear-in-space margins.

    Split each edge at its two nodal zero times. On each piece the unsafe
    portion is constant or a ratio of affine functions. Its integral is
    evaluated analytically (stable log/series), rather than sampling a step
    function with Gaussian quadrature.
    """
    a, b = np.asarray(a, float), np.asarray(b, float)
    da = b-a
    roots = np.clip(np.divide(-a, da, out=np.zeros_like(a), where=da != 0), 0, 1)
    cuts = np.sort(np.stack((np.zeros_like(a[..., :-1]), roots[..., :-1],
                            roots[..., 1:], np.ones_like(a[..., :-1]))), axis=0)
    accum = np.zeros_like(a[..., :-1])
    for lo, hi in zip(cuts[:-1], cuts[1:]):
        mid, width = (lo+hi)/2, hi-lo
        left = a[..., :-1] + mid*da[..., :-1]
        right = a[..., 1:] + mid*da[..., 1:]
        cross = ((left < 0) != (right < 0)) & (width > 0)
        accum += width*((left < 0) & (right < 0))
        # fraction = negative endpoint / (negative - positive endpoint)
        n = np.where(left < 0, left, right)
        dn = np.where(left < 0, da[..., :-1], da[..., 1:])
        den = np.where(left < 0, left-right, right-left)
        dd = np.where(left < 0, da[..., :-1]-da[..., 1:], da[..., 1:]-da[..., :-1])
        frac = np.divide(n, den, out=np.zeros_like(n), where=cross)
        # average ratio about the midpoint: f_mid + (dn/den-f_mid*dd/den)*h(q)
        q = np.divide(dd*width/2, den, out=np.zeros_like(den), where=cross)
        h = np.zeros_like(q)
        small = cross & (np.abs(q) < 1e-3)
        h[small] = -q[small]/3-q[small]**3/5-q[small]**5/7
        regular = cross & ~small & (np.abs(q) < 1-1e-12)
        h[regular] = (1-np.arctanh(q[regular])/q[regular])/q[regular]
        correction = np.divide(dn-frac*dd, den, out=np.zeros_like(den), where=cross)*width/2
        # At |q|=1 both endpoint margins vanish together; the ratio is constant.
        accum += np.where(cross, width*(frac+correction*h), 0)
    return accum.sum(axis=-1)


def integrated_spatial_fraction(a, b):
    """Exact integral, evaluating logarithms only on edges near a crossing."""
    a,b=np.asarray(a,float),np.asarray(b,float)
    al,ar,bl,br=a[...,:-1],a[...,1:],b[...,:-1],b[...,1:]
    negative=(al<0)&(ar<0)&(bl<0)&(br<0)
    positive=(al>=0)&(ar>=0)&(bl>=0)&(br>=0)
    mixed=~(negative|positive)
    edges=negative.astype(float)
    if np.any(mixed):
        edges[mixed]=_edge_time_integral(np.stack((al[mixed],ar[mixed]),axis=-1),
                                        np.stack((bl[mixed],br[mixed]),axis=-1))
    return (edges.sum(axis=-1)+.5*_unsafe_time(a[...,0],b[...,0])+
            .5*_unsafe_time(a[...,-1],b[...,-1]))/a.shape[-1]


def _first_crossing(a, b, threshold, depth=0):
    # Componentwise minimum gives a rigorous upper bound on failed length.
    if float(spatial_failure_fraction(np.minimum(a, b))) < threshold:
        return None
    if float(spatial_failure_fraction(a)) >= threshold:
        return 0.
    if depth >= 30:
        return 1. if float(spatial_failure_fraction(b)) >= threshold else None
    middle = (a+b)/2
    left = _first_crossing(a, middle, threshold, depth+1)
    if left is not None:
        return left/2
    right = _first_crossing(middle, b, threshold, depth+1)
    return None if right is None else .5+right/2


def reconstructed_risk_metrics(times, margins, fraction_threshold):
    """Jump-aware exact exposure and earliest within-step threshold crossing."""
    times, margins = np.asarray(times, float), np.asarray(margins, float)
    dt = np.diff(times)
    if np.any(dt < 0) or not 0 < fraction_threshold <= 1:
        raise ValueError("ordered times and 0 < fraction_threshold <= 1 required")
    f = spatial_failure_fraction(margins)
    first = float(times[0]) if f[0] >= fraction_threshold else None
    if first is None:
        bounds = spatial_failure_fraction(np.minimum(margins[:-1], margins[1:]))
        for i in np.flatnonzero(bounds >= fraction_threshold):
            if dt[i] == 0:
                if f[i+1] >= fraction_threshold:
                    first = float(times[i+1]); break
                continue
            alpha = _first_crossing(margins[i], margins[i+1], fraction_threshold)
            if alpha is not None:
                first = float(times[i]+dt[i]*alpha); break
    positive = dt > 0
    integral = float(np.sum(dt[positive] * integrated_spatial_fraction(
        margins[:-1][positive], margins[1:][positive])))
    return ({"value": first, "censored": first is None},
            float(times[-1]-times[0]-integral), integral)


def km_quantile(times, censored, probability):
    times = np.asarray(times, dtype=float)
    censored = np.asarray(censored, dtype=bool)
    if times.size == 0:
        return None
    unique, inverse, counts = np.unique(times, return_inverse=True, return_counts=True)
    failures = np.bincount(inverse, weights=~censored, minlength=len(unique))
    at_risk = np.cumsum(counts[::-1])[::-1]
    survival = np.cumprod(1.0 - failures / at_risk)
    hit = np.flatnonzero(1.0 - survival >= probability - 1e-12)
    return float(unique[hit[0]]) if hit.size else None


def recovery_statistics(samples):
    durations = [sample["duration"] for sample in samples]
    censored = [sample["censored"] for sample in samples]
    median = km_quantile(durations, censored, .5)
    return {"value": median, "censored": bool(median is None),
            "all_censored": bool(all(censored)), "censored_count": sum(censored),
            "n": len(samples), "n_recovered": len(samples) - sum(censored),
            "status": "no_storm_induced_failures" if not samples else "estimated",
            "p10": km_quantile(durations, censored, .1),
            "p50": median, "p90": km_quantile(durations, censored, .9)}


def recovery_samples(times, risk, transitions, event_times, t_end, mask, placement_times=()):
    times = np.asarray(times, dtype=float)
    risk = np.asarray(risk, dtype=bool)
    mask = np.asarray(mask, dtype=bool)
    samples = []
    for event_index, (event_time, before, after) in enumerate(transitions):
        newly_failed = ~np.asarray(before) & np.asarray(after) & mask
        later = [float(item) for item in event_times if item > event_time + 1e-9]
        next_event = min(later) if later else None
        later_placements = [float(item) for item in placement_times if item >= event_time-1e-9]
        next_placement = min(later_placements) if later_placements else None
        stop = min(next_event if next_event is not None else t_end,
                   next_placement if next_placement is not None else t_end, t_end)
        candidate = np.flatnonzero((times > event_time + 1e-9) & (times <= stop + 1e-9))
        # At a following event, the first duplicate timestamp is the continuous
        # pre-jump state. Exclude its post-jump state to prevent attributing a
        # coincident nourishment or later storm to this recovery interval.
        if next_event is not None or next_placement is not None:
            at_stop = np.flatnonzero(np.abs(times - stop) <= 1e-9)
            if at_stop.size:
                candidate = candidate[candidate <= at_stop[0]]
        for cell in np.flatnonzero(newly_failed):
            hit = candidate[~risk[candidate, cell]]
            observed = bool(hit.size)
            end = float(times[hit[0]]) if observed else float(stop)
            samples.append({"event_index": event_index, "event_time": float(event_time),
                            "cell": int(cell), "duration": max(0., end - event_time),
                            "censored": not observed,
                            "censor_reason": None if observed else
                            ("nourishment" if next_placement is not None and abs(stop-next_placement)<1e-9
                             else "next_storm" if next_event is not None and abs(stop-next_event)<1e-9 else "horizon")})
    return samples
