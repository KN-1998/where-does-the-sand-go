# WRITER_NOTES_R2 — 论文写作包（2026-11-13 22:10）

> **给论文手**：这份文件把 R2 的可写内容按"每问一段"压好了。
> 你不需要读代码、不需要读 `src/`，按 §2 的五行结构填每一问即可。
> 数字一律来自 `本轮检查与结果.md` 与 `results/release_20261113_r2/`（附件包，正在本地核对）。
> **R1 的数字不得与 R2 混用**（R2 修了"全段失守被算成 0"等 bug，R1 结论可弃）。
>
> 状态：R2 的 17 张图 + 英文图注在 `PAPER_FIGURE_CAPTIONS_R2.md`。

---

## 0. 执行令（现在就动笔）

| 时刻 | 交付 |
|---|---|
| 今天 (11/13) 24:00 前 | `report/main.tex` 骨架 + §1 引言 + §2 假设 + 符号表 |
| 11/14 06:00 前 | §3 模型（方程从 `MODEL_SPEC` §2–§3 抄）+ 参数表 |
| **11/14 12:30** | **全文 V1（≤25 页）** ← N7 硬 DDL |
| 11/14 18:30 | 交我核对数字 |
| 11/15 04:30 | V2 + 摘要 + 技术信 |
| 11/15 12:00 | 终稿（留 6 h 缓冲） |

**不要等附件包**：§1–§3 不依赖任何数值。§4 的数字本文件已给。

---

## 1. 主线（摘要骨架，一段话）

> We model a 5-km barrier-island corridor at Rodanthe, NC, with a one-line, two-state sediment budget:
> active beach volume $V$ and a nearshore storm reservoir $O$, forced by a shared stochastic storm table,
> calibrated against state shoreline-change rates, and interrogated with 18 Monte-Carlo experiments (18 000 runs).
> The model closes its sediment ledger to $2.1\times10^{-8}$ relative error and reproduces the analytic
> diffusion benchmarks to 0.1–0.3 %. Its central finding is negative and useful: **a nourishment budget that
> is capped by locally available sand, not by money, barely changes the ranking of strategies** — sand runs out
> before money does, and the two risk metrics (beach width vs. building clearance) rank the same strategies
> in opposite orders.

---

## 2. 五问：每问五条（照填）

### Q1 — Describe the beach before intervention

| 项 | 内容 |
|---|---|
| **结论句** | "The un-intervened corridor is already below the management width over **30.4 %** of its length at $t=0$, and retreat is driven by a chronic rate of **1.7 m/yr** (DEQ segment mean) modulated by a hotspot factor of 2.2." |
| **用哪张图** | **F1**（$w(x,t)$，S2, once, seed 42）+ **F9**（初始覆盖可行性） |
| **用什么数** | $f_w(0)=0.3036$；$w_0$ 16–25 m（均值 21.84）；$\rho_e=1.7$ m/yr；热点峰值 3.74 m/yr；$H=10$ m |
| **不能写** | ❌ "the corridor is eroding at 3.8 m/yr"（那是**热点单点**，不是走廊均值）；❌ 把 $y$、$w$、$V$ 混用 |
| **一句话机理** | 长期趋势进慢性沉汇，风暴进事件脉冲 + 沙库 $O$，两者在结构上分开（题面 D-1） |

### Q2 — Follow the sand

| 项 | 内容 |
|---|---|
| **结论句（已按 R2 实测更正）** | "At the available local volume (2.45 M m³, about **12×** the instantaneous coverage threshold), **uniform placement dominates**: median 15-year width exposure is **3.0 m·yr** versus 18.6 (multi-segment) and 38.6 (hotspot). Spreading keeps the whole corridor above the 20 m management width, whereas concentrating leaves the remaining 4 km below it." |
| **用哪张图** | **F2**（三种布置的 $w$ 剖面）+ **F9**（$\mathcal V_{\rm thr}$ 判据）+ **F12**（沙量分解） |
| **用什么数** | S1、同方量 2.45 M m³、1000 次 MC 的 $E_w$ 中位：**uniform 3.05 / multi 18.64 / hotspot 38.59**；seed 42 确定性：0 / 18.6 / 38.6，$w_{\rm end,min}$ 21.3 / 21.7 / 22.2 m；$\mathcal V_{\rm thr}=H L (w_{\rm mgmt}-w_{\min})=2.0\times10^{5}$ m³，$\mathcal V/\mathcal V_{\rm thr}\approx12$；质量残差 $\le2.6\times10^{-15}$ |
| **不能写** | ❌ "热点集中更优"（R2 实测相反；R1 的旧结论已作废）；❌ 把 $\mathcal V_{\rm thr}$ 说成"长期保护门槛"——它只保证**投放瞬间**全段达标；❌ 说"宽滩必然持久" |
| **一句话机理** | 当 $\mathcal V\gg\mathcal V_{\rm thr}$ 时，匀铺把整段抬到阈值以上，集中投放把沙堆在已达标处而在其余岸段留下欠账；**只有当 $\mathcal V<\mathcal V_{\rm thr}$ 时，集中才是唯一能救热点的办法**（这是 Q2 的判别条件） |

### Q3 — Connect the model to evidence

| 项 | 内容 |
|---|---|
| **结论句** | "Parameters are bounded from public sources, but **a fixed-rate-field holdout fails badly**: trained on 1978–1989 (mean 0.270 m/yr) it predicts 1989–2002 at 4.579 m/yr against an observed 4.579, RMSE 4.785 m/yr, $R^2=-4.30$. We therefore report the model as a conditional scenario tool, **not** a validated forecaster." |
| **用哪张图** | **F10**（101 条 transect + 留出失败）+ **F5**（OAT）+ **F11**（Sobol） |
| **用什么数** | 留出：train 0.270 / holdout 4.579 / RMSE 4.785 / $R^2=-4.295$；Sobol 稳定项：economy 8/8、storm 5/6、transport 6/6（一阶）；质量残差 $2.107\times10^{-8}$；观测 transect（1978–2002）均值 −3.43、(−4.58)（1989–2002），$n=101$ |
| **不能写** | ❌ "validated against observations"；❌ "$R^2$ 高说明模型可信"；❌ 把 Sobol 不稳的项写成精确方差份额；❌ 两个时段"完全独立"（它们共用 1989 岸线） |
| **一句话机理** | 参数可辨识性：$D$ vs $\lambda$（形状 vs 总量）、$D$ vs $u$（一阶矩 vs 二阶矩）可分；$\lambda_s$ 与 $\Delta y$ 只进乘积 |

### Q4 — Challenge the shoreline with future conditions

| 项 | 内容 |
|---|---|
| **结论句** | "Under the three stress packages the corridor retreats at **1.51 / 2.63 / 3.11 m/yr** (S1/S2/S3), i.e. **11 % / 12 % / 22 % below the nominal targets** — a scenario target is not a realised rate. Storm **timing** moves risk between quantiles without changing the total event count." |
| **用哪张图** | **F3**（三策略暴露）+ **F4**（风暴不确定性带）+ **F8**（时机三组）+ **F13**（时空分位面） |
| **用什么数** | 实现速率 1.511 / 2.628 / 3.108；S2 固定事件在 $t=2.25$ yr（$=\tau_{\rm permit}+\tau_{\rm build}+0.5$）；MC 1000 次/情景 |
| **不能写** | ❌ "SLR causes X m of retreat"（S3 的海平面与侵蚀端点是**并列假设**，没有换算）；❌ "early storms maximise risk"（R2 实测不支持）；❌ 把 2042 年末值当稳态 |
| **一句话机理** | 时机改变的是**风险分布**，不是总量（这正是题面考点） |

### Q5 — Recommend a strategy that can adapt

| 项 | 内容 |
|---|---|
| **结论句（按配对 MC 更正）** | "Sand, not money, is the binding constraint: all fixed-calendar strategies place the same **2.45 M m³** and spend the same **66.15 M USD**. Against the one-off benchmark, **no alternative is better on beach-width exposure in any scenario**, and only *repeat* under S3 improves the building-clearance metric (paired difference **−2 693 m·yr**, 95 % MC CI [−2 813, −2 573]). Cheaper adaptive policies save 6–16 M USD but increase exposure." |
| **用哪张图** | **F3**（暴露条形）+ **F14**（耐用性相图）+ **F15**（自适应设置）+ **F16**（施工/监测）+ **F17**（风暴足迹） |
| **用什么数** | 配对差（策略 − once，正=更差）：S1 repeat $E_b{+}5.5,[2.0,9.0]$、$E_w{+}2\,269$；S2 repeat $E_b{+}445$、$E_w{+}27\,129$，adaptive $E_b{+}3\,249$（省 5.9 M）；S3 repeat $E_b\mathbf{-2\,693}$、$E_w{+}17\,339$，adaptive $E_b{+}6\,976$（省 16.4 M）；`policy_pairwise.csv` |
| **不能写** | ❌ "adaptive 更好"（中位与配对都不支持）；❌ "存在唯一最优策略"（S3 两指标相反）；❌ "$c_0^*$ 有交叉点"（未检出）；❌ "retreat 最优"（只有评估标志） |
| **一句话机理** | 供需约束先绑定 → 策略只能用同一批沙；差别全在**时机与空间分配**，而两个风险指标对这两件事的偏好相反 |

---

## 3. 关键数字表（可直接进 Table 2/3）

| 量 | 值 | 标签 |
|---|---|---|
| $\rho_e$（段平均） | 1.7 m/yr | OBS |
| 热点放大 $a_h$ | 1.2（峰值 3.74） | MODEL |
| $H=h_*+B$ | 10 m | MODEL |
| $D$ | $3.0\times10^{5}$ m²/yr | MODEL（并列 $8\times10^{5}$ 敏感性） |
| $\lambda_s$ / $\Delta y_{\rm ref}$ | 0.4 /yr；8 m（中位，$\sigma_{\ln}=0.693$） | ASSUME |
| $k$ / $\lambda$ | 0.667 / 0.1 yr⁻¹ | ASSUME |
| $w_{\rm mgmt}$ | 20 m | ASSUME |
| 本地沙上限 | $2.45\times10^{6}$ m³ | ASSUME（潜在储量） |
| 预算上限 | $1.2\times10^{8}$ USD | ASSUME（情景） |
| 质量闭合残差 | $2.107\times10^{-8}$ | MODEL（数值检） |
| 初始失败长度比 | 0.3036 | MODEL |
| 留出 $R^2$ | −4.295 | MODEL（**失败**，要写） |

---

## 4. 五条 distinctions 的落点（封稿前逐条核）

| 题面要求 | 写在哪 | 用哪句话 |
|---|---|---|
| 长期速率 ≠ 风暴预报 | §3.5 + Q3 留出失败 | "the holdout fails; the rate field is a boundary condition, not a forecast" |
| $y$ / $w$ / $V$ 不可互换 | §2 换算 + 全表单位 | 显式 $H=h_*+B$；两指标并列 |
| 风暴后可能恢复 | §3.4 + F6/F8 | $O$ 状态 + $k$；T6 验证 0.8696 |
| 区域 SLR ≠ 局地后退 | Q4 情景说明 | "sea-level and chronic-retreat endpoints are separate assumptions; no local conversion" |
| 情景 ≠ 干预已发生 | 每图标签 | MODEL / MODEL-SCENARIO / OBS / ASSUME |

---

## 5. 数据来源与已核对项（2026-11-13 22:20 更新）

审查包 `review_handoff_20261113_r2.zip` 已下载并 **SHA256 校验通过**（`9ab3aea0…35252f`），解压在 `dist/r2/review/`。

已从包内 CSV 核对并写入本文：

| 项 | 来源文件 | 状态 |
|---|---|---|
| Q2 三布置暴露（3.05 / 18.64 / 38.59） | `mc_comparison.csv` + `summary.csv` | ✅ 已写入 §2 Q2 |
| Q5 配对差（含 CI） | `policy_pairwise.csv` | ✅ 已写入 §2 Q5 |
| 三情景实现速率 1.511 / 2.628 / 3.108 | `erosion_target_diagnostic.csv` | ✅ 已写入 §2 Q4 |
| 全场质量残差（MC 最大 2.107e-08） | `audit.json` | ✅ 已写入 §3 |

> **口径提醒**：`once` 与三布置（uniform/hotspot/multi）不是同一类实验——**布置是理想 $t=0$ 投放、不计许可与施工时滞**，`once` 要等 1.75 yr。所以除了"哪种布置好"，还要看到"**时滞本身就让 $E_w$ 从 3.0 涨到 3 335**"（seed 42）。
> 论文里这两组数要分开写，不能混成一张"策略对比"表。


## 6. 禁止表述（汇总，红队会抓）

- ❌ "model validated / calibrated against observations"
- ❌ "collapse probability" or "number of buildings lost"（$r$ 是**代理**指标）
- ❌ "relocation is optimal"
- ❌ "sea-level rise causes X m of retreat"
- ❌ "adaptive management outperforms fixed schedules"（要看指标与情景）
- ❌ "global optimum" / "the best strategy"
- ❌ 把 R1 与 R2 的数字混在一张表里
