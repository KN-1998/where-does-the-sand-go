# Reproduce the programming handoff

Run from the repository root. The reviewed package is
`results/release_20261113/`. Earlier `results/current/` and
`results/final_20261112/` contain superseded calculations and must not supply
paper numbers. Do not build the delivery from `git archive HEAD`: the new
implementation has not been committed and would be omitted.

Install Python requirements with `python -m pip install -r requirements.txt`.
The solver uses NumPy, SciPy and PyYAML; MATLAB plotting uses base MATLAB.
The verified MATLAB executable is
`D:\Program Files\MATLAB\R2025a\bin\matlab.exe` (also available as `matlab`).

## Numerical gates

```powershell
python -X utf8 -m unittest discover -s tests -v
python -X utf8 modeling/sanity/discrete_contract.py
python -X utf8 tools/verify_contract.py
python -m compileall -q src tests
git diff --check
```

There are 41 production tests, a separate reference discretization gate and
67 contract checks. These test implementation consistency, not empirical
prediction skill. Release logs and dependency versions are in `validation/`.

## Entire experiment package

```powershell
python -u -X utf8 -m src.exp.batch --root results/release_20261113 `
  --stage all --n 1000 --oat-n 20 --global-power 6 --workers 6
matlab -batch "addpath('matlab'); plot_results('results/release_20261113');"
python -X utf8 -m src.exp.batch --root results/release_20261113 --stage audit
```

Use `--workers 2` for lower memory/CPU use. Use a fresh output root for changed
designs; the runner intentionally does not delete old files. `--stage
deterministic` and `--stage ensembles` can rebuild each part independently.
The batch regenerates intermediate configs with current absolute inheritance
paths, so use the batch command after extracting the package to a new location.

The design contains:

- 47 deterministic runs: S1–S3 baseline and once/repeat/fixed-hotspot/adaptive,
  S1 equal-volume layouts, boundary controls, chronic-loss alternatives,
  local/external sand, alternate costs and fixed-cost scans.
- 18 Monte Carlo groups, each 1,000 shared-seed storm realizations: 15
  scenario-policy groups and three S1 initial placement layouts.
- OAT: 17 parameters, 52 values, 20 common storm seeds per value (1,040 runs).
- Storm timing: 1,000 paired sets of six identical potential-retreat marks,
  placed early/spread/late (3,000 runs). No extra S2 forced event in this test.
- Exploratory Sobol first/total/second-order indices in transport, storm and
  economic groups: base N=64 with two common storm seeds. The economic group
  evaluates local/external sand and three policies. Small-design estimates
  are not a converged global ranking.
- Historical diagnostic: 101 fixed-window USGS transects from the local
  handoff, selection rule and source SHA-256; not independent validation.
- An analytical volume-versus-initial-width feasibility map.

`batch_design.json` stores the requested sampling design. `audit.json` checks
code consistency, full/central conservation, resource constraints, metric
identities and shared storm events. `manifest.json` fingerprints all result
files, including the MATLAB figures after the final audit.

## One simulation

```powershell
python -X utf8 -m src.exp.run_one --config configs/S2.yaml --scenario S2 `
  --strategy once --bc open --t-end 15 --paired-retention `
  --out results/example_S2_once
```

Each run saves resolved parameters, source/config hashes, `fields.npz`,
`ledger.csv`, `events.csv`, `recovery.csv`, `results.json` and `meta.json`.
The batch also exports `fields.mat`. Runtime belongs only to `meta.json`;
deterministic JSON/NPZ outputs pass byte-identical reproducibility tests.
Conservation acceptance is relative residual <1e-6 for the full 9 km and
central 5 km separately.

## MATLAB figures and interpretation

`matlab/plot_results.m` exports 12 PNG/vector-PDF pairs to `figures/`: width
heat map, layout profiles, strategy exposures, Monte Carlo bands, OAT,
trajectories, sand accounting, storm timing, initial feasibility, historical
rates, exploratory global sensitivity and paired sand attribution.
Irregular event times are resampled right-continuously only for heat-map
display. Plotted width is nonnegative; raw negative width remains available
for exhaustion accounting. OAT averages matched seeds before comparing
parameter response ranges. No Statistics Toolbox is required.

MC intervals propagate storms with fixed parameters. Recovery KM observations
are raw event-cell pairs and dependent within runs. Missing/recovery-censored
times remain null with flags. No failure before year 15 means right censoring,
not infinite protection. `T_safe_cum` is average safe-length time, not the
time for which fewer than 50% of cells fail.

The adaptive controller is an explicitly labelled **rate-proxy heuristic**;
it does not implement the specified five-year ensemble/cost optimizer.
Neither the synthetic shoreline/buildings nor the parameter posterior have
independent field validation. `PROGRAMMER_DECISIONS.md` records implemented
choices, approximations and missing evidence. Results must remain labelled
conditional MODEL scenarios; do not describe them as calibrated forecasts or
optimal relocation decisions.


## Delivery checks and optional parallel accelerators

```powershell
python -X utf8 tools/build_report_tables.py --root results/release_20261113
python -X utf8 tools/check_release.py --root results/release_20261113
python -X utf8 -m src.exp.batch --root results/release_20261113 --stage audit
python -X utf8 tools/package_handoff.py --results results/release_20261113
```

The release used `tools/parallel_global.py` and `tools/parallel_timing.py` to
finish expensive supplemental jobs, then stopped redundant serial copies.
Reference comparisons in `validation/parallel_check/` show byte-identical
CSV outputs for the small validation designs. The serial batch remains a
complete reproduction command. Constructor overrides for MC are recorded in
`MC_*/effective_controls.json`; the original inherited config defaults remain
in summary.json for provenance. All delivered science outputs use the same
source fingerprint. PNG/PDF layout checks are recorded in validation/.

The ZIP intentionally omits .git. In an extracted ZIP, skip only the Git-specific `git diff --check`; numerical tests and source/result audits remain available. CODE_VERSION.json preserves the original checkout reference and current source fingerprint.


The full ZIP includes both NPZ and MATLAB field matrices (~579 MB). For sending
review material to teammates, `--lite --out dist/review_handoff_20261113.zip`
retains source, scalar results, ledgers, events and figures while omitting the
large matrices and the full result manifest. The lightweight ZIP has its own
PACKAGE_MANIFEST.json; rebuild deterministic runs before rerunning MATLAB.
