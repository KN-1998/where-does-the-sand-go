# results/ — 结果目录说明

> 由 `python -m exp.experiments --only L0,E0,...,E7` 生成；总表见 [`SUMMARY.md`](SUMMARY.md)，
> 复现命令见 [`../REPRODUCE.md`](../REPRODUCE.md)。

## 目录

| 目录 | 内容 | 关键文件 |
|---|---|---|
| `L0/` | D11 双计数核对（口径 i/ii，各 300 次 MC） | `summary.json`、`caliber_{i,ii}_mc/mc_summary.json` |
| `E0/` | 三情景无补沙基线（确定性 + 1000 MC） | `summary.json`、`{S1,S2,S3}_deterministic/results.json`、`*_mc/mc_summary.json` |
| `E1/` | 三布置对照（1e6 m³，配对基线） | `uniform/`（含 `fields.npz`、`destinations.csv`）、`hotspot/`、`multi/` |
| `E2/` | 三情景 × `once` × 1000 MC（配对留存率） | `{S1,S2,S3}_mc/mc_summary.json` |
| `E3/` | 风暴时机 early/spread/late | `{early,spread,late}/results.json` |
| `E4/` | 策略 × 情景 × 供沙/成本组合 + c0 扫描 | `{local_all_in,external_all_in,local_marginal_plus_fixed}/`、`c0_scan_S2/c0_scan.json` |
| `E5/` | OAT 14 参数 + Sobol（N=96） | `summary.json`、`sobol/sobol_summary.json` |
| `E6/` | 边界条件 + 域大小 | `bc_{open,zeroflux,dirichlet}/`、`domain_{4500,7000}/` |
| `E7/` | V × w_min 相图（uniform/hotspot） | `phase.csv` |
| `E0_local/` | `configs/base.yaml` 的 5 年首跑（START_HERE 验收） | `results.json` 等四件套 |
| `validation/` | 验收日志与 T9 状态 | `pytest.log`、`T9_report.md` |

## 每个 run 目录的必备文件

`results.json`（固定 schema，论文按名取值）、`fields.npz`（`y/O/w/exhausted/x/t`；`exhausted`
为 `V<=V_min` 的布尔掩膜，其余 float32 仅展示用）、`ledger.csv`（逐时间步沙量台账，T1 的载体）、
`events.csv`（每次风暴）、`meta.json`（代码/参数 md5、git sha、seed、运行耗时、网格）。

## 版本控制说明

- **提交**：`results.json`、`meta.json`、`summary.json`、`summary.md`、`mc_summary.json`、
  `phase.csv`、`c0_scan.json`、`destinations.csv`、验收日志；
- **不提交**（但留在磁盘，可复现）：`ledger.csv`、`events.csv`、`fields.npz`、`mc_results.csv`。
  理由：单次运行的台账/场文件共约 45 MB，且可由 `REPRODUCE.md` 的命令重新生成。
  建模手要逐行核对 T1 时，直接读本地 `ledger.csv` 即可。

## 口径提醒

- `V_domain` / `V_central` 是**相对初始状态的增量**（生产运行初始为 0）；
- `R_c_cum` 是**当前亏空的空间积分**（可随补沙下降），单调诊断量是 `D_max_cum`；
- `residual_rel` 分母为 `max(1, |placed_cum|)`，所以投放前的时间步上它等于绝对残差（<1e-7 m³）；
- `T_first_fail_*` 是**长度加权失败比例首次 ≥0.5** 的时间，不是 `min_x`；删失时 `value=null`。
