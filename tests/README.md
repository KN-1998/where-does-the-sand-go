# R2 验收入口（2026-11-13）

当前共55项 unittest，覆盖守恒、解析收敛、开边界、非零初态台账、耗尽后补沙、全部事件中间状态、删失、风暴/补沙归因、无未来信息的集合预报、正收益才批准、许可/施工时滞、监测复核、多段工程固定成本、MC快照与时空分位，以及Sobol矩阵参数顺序和纯交互函数。另运行参考离散脚本和67项合同检查。结果日志在最新结果目录中。

```powershell
python -X utf8 -m unittest discover -s tests -v
python -X utf8 modeling/sanity/discrete_contract.py
python -X utf8 tools/verify_contract.py
```

上游code-r1的17项pytest已单独运行通过；`tools/review_upstream.py`另外复现了现有测试漏掉的预报零累计和事件提前摊入风险。测试通过不能代替独立现场验证。

下方是原阶段门禁的历史说明；R2程序及结果口径以本段、REPRODUCE.md和REVIEW_UPSTREAM_R2.md为准。

---

# Production validation (2026-11-13)

Run `python -X utf8 -m unittest discover -s tests -v` from the repository root.
The suite currently contains 41 tests with failure exit codes and no network
dependency. Logs for the release are under `results/release_20261113/validation/`.

| File | Coverage |
|---|---|
| test_mass.py | T1/T3/T6/T7/T10/T11/T12/T13; exhaustion, recovery, boundaries, delayed adaptive action |
| test_erf.py | Spatial diffusion limit with dt proportional to dx² (separate spatial diagnostic) |
| test_validation.py | T2 BE time-first-order, T4 50/25 m in S1–S3 plus paired inventory, T5 analytical centre protection, T7 Gaussian outflow, genuine limiter activation, sand/cost caps, safe-time identity, no-action adaptive equivalence |
| test_metrics.py | Jump-aware exposure, interpolated crossing, cellwise historical deficit, central-only recovery and next-storm censoring, raw Kaplan–Meier samples |
| test_reproducibility.py | T8 byte-identical JSON/NPZ, resolved CLI snapshots and shared events |
| test_io.py | Configuration inheritance and cycle detection |

T9 is a diagnostic, not a pass/fail test: `src/exp/history.py` selects the
historical northing window before examining rates and writes its observations,
selection rule and DBF hash. Historical periods overlap; no independent
validation claim is made.

The production risk-length integral uses linear reconstruction between cell
centres and constant end half-cells, linear time states, and three-point Gauss
quadrature. Duplicate event timestamps preserve instantaneous jumps. This
removes the staircase's one-cell timing bias without changing the 50% failure
criterion. Initial discrete fractions are retained separately for the contract
check. `T_safe_cum + E/5000 = horizon` is explicitly tested.

Passing numerical gates establishes implementation consistency; it does not
calibrate the synthetic shoreline, building setbacks or storm priors.
