# Current conditional computation release: R2

Use only this release for the current programming handoff. Older releases are
retained for traceability. Reproduction commands are in the root REPRODUCE.md;
the root 本轮检查与结果.md is the final review once audits are complete.

- summary.csv: 18 primary deterministic comparisons, seed 42; the remaining
  diagnostics bring the complete deterministic collection to 47 runs.
- mc_comparison.csv: 18 groups × 1000 storm realizations; paired means,
  marginal quantiles, realized sand, construction and monitoring costs.
- MC_*/summary.json: raw scalar runs, censoring, time-space width quantiles,
  retention and signed sand-volume attribution; parameters fixed.
- OAT_S2_once/: 17 parameters, 52 values, 20 common seeds per value.
- timing/: same six storm marks in early, spread and late configurations.
- GLOBAL_*/: three parameter groups, N=512, two independent scrambles;
  sensitivity_convergence.csv diagnoses first/total/second-order stability.
- supplements/: joint assumed parameters and storms (3000), durability map
  (4096), and matched monitoring/forecast settings (500); scalar summaries
  explicitly distinguish marginal distributions from paired effects.
- footprint/: 1200 runs comparing regional and peak-normalized Gaussian
  storms. Same marks do not imply equal integrated storm energy.
- history/: historical distribution and reduced rate-field temporal holdout.
- figures/: 17 MATLAB PNG/PDF pairs with English captions at the root. The
  three heatmap PDFs use 300 dpi image export to avoid vector shading seams;
  the other fourteen retain vector text and lines.
- audit.json, completeness.json, visual_QA.json and validation_status.json:
  separate implementation, completeness, visual and scientific status.

Numerical PASS is not independent field validation. The reduced historical
rate-field holdout fails; the full beach/reservoir model has no independent
post-nourishment validation here. Initial beach/building geometry, monitoring
capability, survey costs and parameter distributions include assumptions.
Building-clearance exposure is a proxy, not a collapse probability. No failure
by the end of the observation window means censoring, not infinite protection.
Signed intervention-minus-baseline sand accounting is not tagged-grain tracking.
