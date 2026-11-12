# REPRODUCE.md — 从干净环境到全部结果与图

> 本文件是编程手交付的复现说明（`CODER_SPEC` §9 第 5 项）。
> 所有命令均在仓库根目录 `D:\数学建模acm` 执行；Windows PowerShell 语法。
> 结果总表见 [`results/SUMMARY.md`](results/SUMMARY.md)，验收日志见
> [`results/validation/pytest.log`](results/validation/pytest.log)。

---

## 0. 环境

| 项 | 值 |
|---|---|
| OS | Windows 10/11 |
| Python | **3.13.9**（Anaconda，`D:\anaconda\python.exe`） |
| 依赖 | numpy 2.3.5 / scipy 1.16.3 / pandas 2.3.3 / matplotlib 3.10.6 / PyYAML 6.0.3 / pytest 8.4.2 |
| 编译工具 | 不需要（纯 NumPy/SciPy） |
| 外部数据 | 不需要（`资料/` 的 PDF/GIS 不参与求解器） |

```powershell
# 若用别的 Python，先确认依赖：
python -c "import numpy, scipy, matplotlib, yaml; print('deps ok')"

# 安装本仓库为可编辑包（让 python -m exp.* / viz.* 可用）
python -m pip install -e . --no-build-isolation --no-deps
python -m pip install -r requirements.txt   # 需要联网时
```

> 本仓库的 `pyproject.toml` 把 `src/{sim,exp,viz}` 装成顶级包，所以文档里的
> `python -m exp.run_one` 与 `python -m viz.plots` 可以直接运行。
> `pytest` 通过 `pyproject.toml` 的 `pythonpath = ["src"]` 找到同一份代码。

## 1. 30 秒自检（参考实现）

```powershell
python modeling/sanity/discrete_contract.py    # 末行 ALL PASS，退出码 0
```

## 2. 验收测试（T1–T13，16 项，约 4 s）

```powershell
python -m pytest tests -v -s
# 期望：16 passed
# 日志已存：results/validation/pytest.log
```

单项：`python -m pytest tests/test_mass.py -v -s` 等；文件与判据见 `tests/README.md`。

## 3. 第一个 E0 产物（约 1 s）

```powershell
python -m exp.run_one --config configs/base.yaml --strategy none --out results/E0_local
```

产出 `results/E0_local/{results.json,fields.npz,ledger.csv,events.csv,meta.json}`。
判据：`results.json` 的 `mass.residual_rel_max < 1e-6`。（当前实测 2.2e-8。）

## 4. 全部实验 E0–E7（约 5–6 分钟，8 核）

```powershell
# E0 基线（3 情景 × 1000 MC + 3 个确定性场）
python -m exp.experiments --only E0 --jobs 8 --n-mc 1000

# E1 三布置（1e6 m³，理想 t=0，配对基线）
python -m exp.experiments --only E1 --jobs 8

# E2 三情景 MC（once，1000 次，配对留存率）
python -m exp.experiments --only E2 --jobs 8 --n-mc 1000

# E3 风暴时机 / E4 策略 / E5 OAT+Sobol / E6 边界 / E7 相图
python -m exp.experiments --only E3,E4 --jobs 8
python -m exp.experiments --only E5 --jobs 8 --sobol
python -m exp.experiments --only E6,E7 --jobs 8
```

| 实验 | 实测耗时（8 workers） | 主要产物 |
|---|---|---|
| E0 | 124 s | `results/E0/{S1,S2,S3}_{deterministic,mc}/` |
| E1 | 5 s | `results/E1/{uniform,hotspot,multi}/` |
| E2 | 203 s | `results/E2/{S1,S2,S3}_mc/` |
| E3 | 2 s | `results/E3/{early,spread,late}/` |
| E4 | 33 s | `results/E4/{local_all_in,external_all_in,local_marginal_plus_fixed}/` + `c0_scan_S2/` |
| E5 | 52 s（含 Sobol N=96） | `results/E5/{param}_{low,high}/` + `sobol/` |
| E6 | 3 s | `results/E6/bc_*`、`domain_*` |
| E7 | 44 s | `results/E7/phase.csv` |

> 单次实验可加 `--force` 强制重跑；默认复用已存在的 `results.json`（可断点续跑）。
> 单独跑一次：`python -m exp.run_one --config configs/S2.yaml --out results/one --baseline`。

## 5. 图 F1–F8（约 10 s）

```powershell
python -m viz.plots                  # 全部
python -m viz.plots --which F1,F4    # 子集
```

输出在 `figures/`，300 dpi PNG；每张图的坐标轴、单位与数据类型标签都已写在图内。

## 6. 复现性约定（为什么两次跑结果一致）

| 项 | 约定 |
|---|---|
| 随机种子 | MC 第 $i$ 次：`seed_i = (seed*1000003 + i) % 2**32`，写进 `meta.json` |
| 风暴事件表 | 按 `scenario+seed` **预生成一次**，基线/布置/策略全部重放同一张表（配对比较） |
| 三条独立 RNG 流 | 到达 / 强度 / 足迹中心 + 监测噪声，互不共用 |
| 补沙时刻 | 吸附到第一个 $\ge t_s$ 的步边界，实际时刻记入 `results.json.placements[].t` |
| `results.json` | 不含运行时间/时间戳，同 seed 逐字节相同（T8） |
| `fields.npz` | 自写固定时间戳的 zip，md5 同 seed 相同（T8） |

## 7. 代码地图

```text
src/sim/
  params.py      params.yaml 读取 / 情景时变律 / 配置合并
  grid.py        网格、隐式输运算子（守恒 FV + BE + 迎风）、三对角
  units.py       y ↔ V ↔ w 的唯一换算处（只此一处）
  model.py       事件驱动主循环、O 子步、风暴/补沙跳变、台账、自适应预报
  storms.py      泊松到达 / 对数正态强度 / 事件表 / 监测 RNG
  placements.py  布置族、策略（once/repeat/targeted/adaptive）、预算与沙源
  metrics.py     风险映射、空间聚合、四个时长指标、KM 删失
  accounting.py  台账列定义与闭合恒等式
  sums.py        Kahan 补偿求和（15 年闭合到 1e-13）
  io.py          results.json / fields.npz / ledger.csv / events.csv / meta.json
src/exp/
  run_one.py     单次运行 CLI
  mc.py          蒙特卡洛（多进程）+ KM 汇总 + 重算摘要
  experiments.py E0–E7 驱动
  common.py      配对运行 / 留存率 / 汇总工具
src/viz/
  plots.py       F1–F8
tests/           T1–T13（16 项）
configs/         base.yaml（5 yr E0_local）、S1/S2/S3.yaml（15 yr）
results/         每实验目录 + SUMMARY.md + validation/
figures/         F1–F8 PNG
```

## 8. 已知偏差与限制（不与合同冲突，但论文必须写）

1. **T9 历史岸线诊断未重算**：本地缺 `资料/06_原始摘录/_gis/`（被 `.gitignore` 排除）。
   现有观测参考值与模型基线对照见 `results/validation/T9_report.md`。
2. **指标空间聚合用分段线性重构**：`f_w(0)=0.3036`（合同给的逐格计数是 0.3000，两者都在
   T12 的 ±0.005 内）。这样阈值穿越时间不受“一格=1%”的量化影响（T4 由 2.7% 降到 0.07%）。
3. **通量限制器是 $V_{\min}$ 处的全有/全无屏障**（合同写“按比例缩放”）：
   被挡住的通量记 `Q_limited_cum` 诊断；不改守恒，但热点耗尽区的沿岸输沙会偏硬。
4. **Sobol 只作补充排序**：N=96 的 Saltelli 估计仍有噪声，且第 3 组参数共线。
5. **自适应策略的 5 年预报在平静情景看不到建筑风险**（$E_b$ 全为 0）：并列时回退到
   风险加权亏空位置。该选择记在 `strategy_log` 的 `benefit_fallback`。
6. **$w_{0,\min}$ 的自检**：合同写 `|w.min()-16|<1e-9`，但 360 格网格没有格心落在 x=0，
   实际 16.00143；中央恰 200 格的约束优先，保留 360 格。
7. **E3 的方向与文档预期不同**（spread 的 $E_w$ 最大），如实报告在 `results/SUMMARY.md` §5。
