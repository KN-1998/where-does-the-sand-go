# 给主编程手的交接说明（R1，2026-11-13）

> 编程手 → 主编程手。目标：**你在 30 分钟内能接手、复核、扩展，不踩我踩过的坑**。
> 合同文档：[`handoff/CODER_SPEC.md`](../handoff/CODER_SPEC.md)；复现：[`REPRODUCE.md`](../REPRODUCE.md)；
> 结果总表：[`results/SUMMARY.md`](../results/SUMMARY.md)；存疑/重跑：[`feedback/RE_RUN_AND_OPEN_ISSUES.md`](RE_RUN_AND_OPEN_ISSUES.md)。

---

## 0. 一句话状态

代码在 `code` 分支（`main` 未动，按约定由建模手合并）；17 项验收 + 67 项合同自检 + 2268 项结果审计全过；
L0/E0–E7 全部可复现（约 8.5 分钟），F1–F8 已出图。**没有已知的数值 bug；有 9 条口径 `[自决]` 待建模手签字。**

```powershell
python -m exp.check_all     # 一条命令验收全部（原型 + 测试 + 合同 + 审计）
```

---

## 1. 仓库状态与分支

| 项 | 值 |
|---|---|
| 当前分支 | `code`（不要在 `main` 上提交；`main` 由建模手合并） |
| 基线 | `main` = `bce02d5`（START_HERE / base.yaml 那一轮） |
| 只读区 | `modeling/`、`handoff/`、`ledger/`、`资料/`、`problem/`、`data/raw/` **零改动**（`git diff main -- modeling handoff ledger 资料 problem data/raw` 为空） |
| 提交粒度 | 求解器 → 实验/图 → 报工 → 修复/L0 → 文档/审计；提交信息统一 `[code] ...` |
| 版本标记 | 交接时打 `code-r1`（见文末） |
| 忽略策略 | `ledger.csv`/`events.csv`/`fields.npz`/`mc_results.csv` 不入库（共约 45 MB），但留在磁盘；`results.json`/`meta.json`/`summary.*` 入库 |

---

## 2. 架构与调用链

```
python -m exp.run_one ──┐
python -m exp.mc ───────┼─► exp.common（配对/留存/汇总）
python -m exp.experiments（L0,E0–E7）─┘
                              │
                              ▼
                    sim.model.run_model(params, scenario, run, events)
                              │  Simulator.__init__：网格、w0、rho_base、V_min、Budget、Metrics
                              ▼
                    Simulator.run_loop（事件驱动主循环）
                      ├─ strat.initial() → 投放计划
                      ├─ t=0 投放 → 记录 → t=0 事件（若有）
                      ├─ while t<T:
                      │    _advance(h)          # BE：O 子步 + 隐式输运 + 源项 + 屏障
                      │    _apply_event()       # 风暴跳变（y-=dy, O+=H dy）
                      │    strat.on_time(t)     # 触发/预报/补沙调度
                      │    _apply_due_placements(t)
                      │    metrics.observe / ledger._record
                      └─ finalize → SimResult
                              │
                              ▼
                    sim.io.write_results（results.json/fields.npz/ledger.csv/events.csv/meta.json）
```

### 模块职责

| 文件 | 职责 | 关键对象 |
|---|---|---|
| `src/sim/params.py` | 读 `params.yaml`、扁平化、override、情景时变律、配置合并 | `Params`、`Scenario`、`RunConfig` |
| `src/sim/grid.py` | 网格、三对角、守恒 FV 输运算子、三种 BC、屏障 | `Grid`、`Transport`、`solve_tridiag`/`thomas` |
| `src/sim/units.py` | **唯一**的 $y\leftrightarrow V\leftrightarrow w$ 换算 | `V_abs_of_y`、`deficit`、`w_eff_of_y` |
| `src/sim/model.py` | 主循环、O 子步、风暴/补沙跳变、台账、自适应预报 | `Simulator`、`SimResult` |
| `src/sim/storms.py` | 泊松/对数正态/强制事件/事件表/监测 RNG | `StormEvent`、`EventTable` |
| `src/sim/placements.py` | 预算/沙源约束、四种策略、触发与冷却 | `Budget`、`OnceStrategy`、`AdaptiveStrategy` |
| `src/sim/metrics.py` | 风险映射、$f_c$ 聚合、四个时长、恢复期/删失 | `Metrics` |
| `src/sim/accounting.py` | 台账列与闭合恒等式 | `Ledger`、`closure` |
| `src/sim/sums.py` | Kahan 补偿求和 | `Kahan` |
| `src/sim/io.py` | 输出五件套、确定性 npz、schema | `write_results`、`build_results` |
| `src/exp/*` | 单跑/MC/实验/审计/门禁 | `run_one`、`mc`、`experiments`、`audit`、`check_all` |
| `src/viz/plots.py` | F1–F8 | `fig_f1` … `fig_f8` |

---

## 3. 必须保持的不变量（改代码前先读）

| # | 不变量 | 在哪里保证 | 破坏后的症状 |
|---|---|---|---|
| 1 | $V$ 与 $O$ 互斥；$V=V_{\text{ref}}+Hy$；台账用**增量** | `units.py`、`_record` | T1 差一个 $V_{\text{ref}}L$ 常数；T11 判错 |
| 2 | $y$ **不裁剪**；下限只加在 $V$ 上；$R_c=[V_{\min}-V_{\text{abs}}]^+$ 可恢复；单调量是 $D_{\max}$ | `_advance` 不裁 $y$；`deficit`；`D_max` | 补沙后残差 $10^6$ 量级；T13 失败 |
| 3 | 连续步不含风暴 $S$；事件是跳变；顺序：投放→抽样→截步→连续步→跳变→同刻投放 | `run_loop`、`_apply_event` | T6 漂移、T10 重复注入 |
| 4 | $O$ 用精确解；恢复量 $R_n=\frac{k}{a}(O^n-O^{n+1}+S)$ 以 $R_n/(H\Delta t)$ 进 $y$ 源项 | `_advance` | 质量缓慢漂移（T1 1e-3 量级） |
| 5 | 输运必须守恒：面通量对两侧符号相反；边界体积 = $H F\Delta t$ | `Transport.assemble/face_fluxes` | T7 符号反、T1 不闭合 |
| 6 | 事件表按 `scenario+seed` 预生成并在基线/布置/策略间**重放** | `build_event_table`、`run_pair`/`exp.*` | 配对差里混入不同风暴 |
| 7 | 两条独立 RNG 流（实际 4 条：到达/强度/位置/监测） | `storms._streams` | 加一次事件改变后续所有强度 |
| 8 | 投放按重叠长度加权；总量断言 $10^{-12}$；时刻吸附到首个 $\ge t_s$ 的步边界 | `_distribute`、`_apply_due_placements` | T1 1–2% 误差；换 $dt$ 结果变 |
| 9 | 成本/沙源：$c_1^{\text{eff}}\in\{27,30,11,14\}$；`V_j` 顺序取 min；$V_j<1e5$ 不得静默投放 | `Budget.feasible` | 外调价算成 30、$c_0^*$ 假交叉 |
| 10 | 指标只在中央 5 km；闭合用全域 9 km | `Metrics`、`_record` | 指标被缓冲区污染 |
| 11 | `results.json` 不含时间戳/运行时间 ⇒ 同 seed 逐字节相同 | `build_results`（runtime 只在 `meta.json`） | T8 失败 |
| 12 | `fields.npz` 用固定 zip 时间戳；`exhausted` 是布尔掩膜 | `io.save_npz`、`_record` | T8 md5 不同；后处理引用 $V$ 前漏掩膜 |

> 另：所有台账累计量用 `Kahan`（`src/sim/sums.py`）。**不要**改回 `+=`，否则 15 年闭合从 $10^{-13}$ 退化到 $10^{-7}$。

---

## 4. 扩展指南

### 4.1 新增一个策略
1. 在 `placements.py` 继承 `Strategy`（或 `_TriggeredStrategy`），实现 `initial(model)` 与/或 `on_time(t, model)`。
2. 用 `model.add_placement(PlannedPlacement(...))` 排队；`budgeted=True` 时由 `Budget.feasible` 截断。
3. 在 `make_strategy` 注册名字；`RunConfig.strategy` 直接用该名字。
4. 在 `exp/experiments.py` 的 E4 列表里加名字；重跑 E4（≈1 min）。
5. 若要进论文图，改 `viz/plots.py` 的 F8 样式字典。

### 4.2 新增一个实验
1. 在 `exp/experiments.py` 写 `exp_En(jobs, force)`：用 `_mk_run`/`_table`/`_paired`/`_save_run`/`_write_summary`。
2. 在 `main()` 的 `--only` 分支注册；默认列表同步。
3. 结果目录 `results/En/`，`summary.json` + `summary.md`；把数字写进 `results/SUMMARY.md`。
4. 如果要入图，在 `viz/plots.py` 加函数与 `FIGURES_MAP`。

### 4.3 新增一个指标
1. 在 `Metrics` 里累计（**只在 `observe` 的中央掩膜上**），在 `finalize` 返回。
2. `io.build_results` 的 schema 里加键（论文手按名取值）；删失语义保持 `value=null ⇔ censored=true`。
3. 加测试到 `tests/test_metrics.py`；跑 `exp.audit` 确认新字段有限、非负。

### 4.4 新增一种边界
1. `Transport.assemble` 加分支（左边系数 `beta0/gamma0`、右边 `alpha_n/gamma_n`，行 0 / n-1 各只加一次）。
2. `Transport.face_fluxes` 同步（否则台账与实际通量不一致）。
3. `BCS` 元组、`Grid` 小域逻辑、`exp_E6` 列表、测试 `test_bc.py` 同步。
4. 必须验证：均匀场在 zeroflux 下不变；open 下外流等于已知损失；闭合残差 <1e-6。

### 4.5 改情景/参数
- **只改 `params.yaml` 或 `configs/*.yaml`，不要改代码常量**。
- `Scenario` 的 `rho_scale=(target-rho_storm)/2.31` 是合同口径；风暴组的 OAT 固定 scale 是
  `[自决]`，改之前先看 `feedback/TO_MODELER.md` §3.5。

---

## 5. 测试与门禁

| 层 | 命令 | 覆盖 | 运行时间 |
|---|---|---|---|
| 参考原型 | `python modeling/sanity/discrete_contract.py` | 最小离散链（T3/T11/T13/T1） | <1 s |
| 验收 | `python -m pytest tests -v -s` | T1–T13 + T12b（17 项） | 4 s |
| 合同 | `python tools/verify_contract.py` | 文档/参数一致性（67 项） | <1 s |
| 结果 | `python -m exp.audit` | 106 个 run 的 schema/闭合/字段/图（2268 项） | <1 s |
| 一键 | `python -m exp.check_all` | 以上四层 | ~10 s |

**加测试的规矩**：必须有 assert、必须打印实测值、不得依赖时间戳/网络；判据来自合同，不改判据。

---

## 6. 性能

| 场景 | 实测 | 备注 |
|---|---|---|
| 15 yr 单 run（无场） | ~0.13 s | 750 步 × `solve_banded`(360) |
| E0：3 情景 × 1000 MC | 121 s | 8 workers，`pair=False` |
| E2：3 情景 × 1000 MC（配对） | 203 s | 每实现 2 次模拟（留存率） |
| 全实验 L0+E0–E7（含 Sobol N=96） | 511 s | 8 workers |
| 自适应单 run | ~1.5 s | 每次触发 8 成员 × 6 候选的 5 yr 预报 |
| 全库磁盘 | 47 MB | 其中 45 MB 是台账/场（不入库） |

并行点：`exp.mc` 用 `ProcessPoolExecutor`；E7/E5-OAT 串行（单 run 太短，进程开销不划算）。
若扩到 10⁴ 次 MC：优先按 (scenario, i) 分块、减少每次 `load_params`（当前每次重建 Params，~5 ms）。

---

## 7. 技术债 / 路线图

| 优先级 | 事项 | 影响 | 建议 |
|---|---|---|---|
| **P0** | 限制器是 $V_{\min}$ 处全有/全无屏障 | 耗尽区沿岸输沙偏硬；`Q_limited_cum` 可达 $10^7$ | 若建模手要求“比例缩放”，实现 face-level 缩放 + active-set 迭代（0.5–1 d） |
| **P0** | $f_c$ 用分段线性重构 | 与合同“逐格计数”字面不同 | 等建模手签字；否则回退只需改 `Metrics._measure_fraction` |
| **P1** | 自适应预报是“8 成员 × 6 候选”的贪心 | 不保证全期最优；S1/S2 常看不到 $E_b$ | 可加“预测 $T_{\text{safe,cum}}$ 的代理”或扩大候选；注意成本线性 |
| **P1** | Sobol N=96、参数共线 | $S_1$ 有噪声/超 1 | N≥512；第 3 组改用“策略排序翻转率”而不是 $S_1$ |
| **P1** | T9 未实现（缺数据） | Q3 只有资料库值 | 数据到位后写 `exp/t9_shoreline.py`（DBF 读取或 pyshp） |
| **P2** | $H$ 换算在 `model.py` 的投放/风暴处直接写 $H$ | 与“只在 units.py”严格字面不符 | 抽 `units.dy_from_volume/volume_from_dy` |
| **P2** | `io.py` 无独立单测（依赖 T8 间接覆盖） | schema 回归风险 | 加 `tests/test_io.py`（键、形状、删失、幂等） |
| **P2** | E0 的 `--force` 会连 MC 一起重跑 | 只想刷新场文件时浪费 2 min | 给 `exp_E0` 加 `--field-only` 开关 |
| **P2** | run 内无断点续跑 | 超长 run 中断要重来 | 每 N 步存 state（`y/O/RNG/时间`），校验 hash |
| **P3** | 实验串行 | E7 192 run 用不满多核 | 用 `ProcessPoolExecutor` 包 `exp_E7` 的单 run |
| **P3** | `make_strategy(placements=[])` 语义靠 `is not None` | 传 `None` 会回退到 run.strategy | 已有注释；新增调用点务必传 `[]` 而不是 `None` |

---

## 8. 八个最容易踩的坑（都是我踩过的）

1. **参数键名**：`d_bldg`（不是 `d_b`）、`m_safe`（不是 `m_s`）、`H_dep`；`params["x"]` 找不到会直接抛错。
2. **`Scenario` 与 `params` 的耦合**：`Scenario` 从 `params.scenarios` 读 $\lambda_s,\Delta y$；`clone_with`
   只对 `lambda_s`/`dy_ref` 回写情景块，**`rho_e` 故意不回写**（块里的 `rho_e` 是“目标均值”，不是背景速率）。
3. **`make_strategy(placements=[])`**：`[]` 表示“脚本化、无动作”（预报用）；传 `None` 会回退到 `run.strategy`，
   自适应会递归。已用 `is not None` 修过。
4. **非零初始场**：测试/诊断要用 `Simulator(y0=..., O0=...)`，不能 `sim.y = ...`（否则台账的 `V0/O0` 基线是 0，闭合差一个常数）。
5. **`fields.npz` 是 float32**：测试/审计要用 `SimResult.y_end/O_end`（float64）；用场文件重算收支会差 $10^{-7}$。
6. **`t=0` 顺序**：投放先、事件后；`run_loop` 在首步前处理 t=0 事件。改顺序会破坏 T10 的“只注入一次”。
7. **Kahan**：累计量是对象（`.add/.value`），不是 float；`+=` 会静默变成重绑定。
8. **确定性输出**：`results.json` 里不能有 runtime/时间戳；`np.savez` 会写 zip 时间戳，必须用 `io.save_npz`。

---

## 9. 接手 30 分钟检查清单

1. `python -m exp.check_all` → ALL PASS。
2. 读 `src/sim/model.py` 的 `Simulator.run_loop` 与 `_advance`（约 120 行），对照 §3 的 12 条不变量。
3. 抽一个 run：`python -m exp.run_one --config configs/S2.yaml --out results/_check --baseline`，
   手算最后一行台账：`placed - (V+O+flux+outside+offshore+chronic)` 应等于 `residual`（$10^{-7}$ 内）。
4. 看 `results/SUMMARY.md` §1.5 与 `feedback/RE_RUN_AND_OPEN_ISSUES.md`，知道哪些数字会被裁决影响。
5. 再决定是否动 P0/P1 技术债；动任何口径都要按 `RE_RUN_AND_OPEN_ISSUES.md` §5 的纪律重跑。

---

## 10. 常用命令

```powershell
# 环境
python -m pip install -e . --no-build-isolation --no-deps

# 单跑 / 配对
python -m exp.run_one --config configs/S2.yaml --out results/one --baseline

# MC
python -m exp.mc --config configs/S2.yaml --strategy once --n 1000 --jobs 8 --pair --out results/MC_test

# 实验
python -m exp.experiments --only L0,E0 --jobs 8 --n-mc 1000
python -m exp.experiments --only E5 --jobs 8 --sobol

# 图
python -m viz.plots --which F1,F4

# 审计 / 门禁
python -m exp.audit
python -m exp.check_all
```

---

## 11. 附录：文件清单

```
src/sim/   params grid units model storms placements metrics accounting sums io
src/exp/   run_one mc experiments common audit check_all
src/viz/   plots
tests/     test_mass test_erf test_refine test_storm test_floor test_metrics
           test_bc test_repro helpers
configs/   base S1 S2 S3
results/   L0 E0 E1 E2 E3 E4 E5 E6 E7 E0_local validation README SUMMARY
figures/   F1–F8 + MANIFEST
feedback/  TO_MODELER TO_CHIEF_CODER RE_RUN_AND_OPEN_ISSUES README
```

提交顺序（`git log --oneline main..code`）：求解器 → 实验/图 → 报工 → 修复/L0 → 目录说明 → 审计/门禁/反馈。
交接后建议打标签：`git tag -a code-r1 -m "coder handoff R1"`，由建模手合并 `code → main`。
