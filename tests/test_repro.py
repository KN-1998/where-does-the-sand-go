# -*- coding: utf-8 -*-
"""T8: same seed -> byte-identical results.json and identical fields.npz md5."""
import hashlib

from sim.io import write_results

from .helpers import cfg, simulate


def _digest(path) -> str:
    return hashlib.md5(path.read_bytes()).hexdigest()


def test_t8_reproducible(tmp_path):
    from sim.params import Scenario, load_params
    params = load_params()
    scen = Scenario("S2", params)
    run = cfg(scenario="S2", strategy="once", t_end=3.0,
              forced_events=list(scen.forced_events))
    digests = []
    for i in range(2):
        res = simulate(params, scen, run)
        out = tmp_path / f"run{i}"
        write_results(out, res, write_fields=True)
        digests.append((_digest(out / "results.json"), _digest(out / "fields.npz")))
    print(f"T8: results.json {digests[0][0]} vs {digests[1][0]}; "
          f"fields.npz {digests[0][1]} vs {digests[1][1]}")
    assert digests[0][0] == digests[1][0], "results.json is not byte-identical"
    assert digests[0][1] == digests[1][1], "fields.npz md5 differs"
