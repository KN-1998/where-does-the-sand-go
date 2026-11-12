# 给建模手的反馈（R1，2026-11-13）

> 编程手 → 建模手。对应 `handoff/CODER_SPEC.md` v0.6 与 `modeling/MODEL_SPEC.md` v0.6。
> 本文件只讲三件事：**合同哪些照做了、哪些需要你裁决、哪些结果与文档预期不一致**。
> 结果总表：[`results/SUMMARY.md`](../results/SUMMARY.md)；存疑/重跑清单：[`RE_RUN_AND_OPEN_ISSUES.md`](RE_RUN_AND_OPEN_ISSUES.md)。

---

## 0. 结论先行

- **N1–N6 全部达成**：17 项验收全绿（4 s），67 项合同自检通过，2268 项结果审计 0 失败。
- **E0–E7 + L0 全部出数**，106 个 run；F1–F8 已出图；从干净环境约 8.5 分钟可重跑。
- **没有“因为算错而必须立刻重跑”的点**；但有 **9 条 `[自决]` 需要你回填**，其中 3 条会改论文措辞
  （L0 偏差、E3 方向、热点峰值），1 条会改所有数字的定义（$f_c$ 聚合）。

---

## 1. 合同符合性（逐节）

| 合同条款 | 状态 | 说明 |
|---|---|---|
| §2.0 初始场 / 网格 / S3 时变律 | ✅ 照做 | $V_0\equiv V_{\text{ref}}$、$w_0(x)$ 热点、S3 的 $\lambda_s,\Delta y_{\text{ref}},\rho_e(t),D(t)$ 全部实现；**唯一偏差**：`w.min()=16.00143` 而非 16（360 格无格心在 x=0），见 `[自决] 1` |
| §2.1–2.3 方程、守恒 FV、O 子步 | ✅ 照做 | 迎风+中心扩散、BE、$O^{n+1}=(O^n+S)e^{-a\Delta t}$、$R_n=\frac{k}{a}(O^n-O^{n+1}+S)$；禁止的三种 $kO$ 写法均未使用 |
| §2.4 时间推进 / 事件截步 | ✅ 照做 | 事件在步边界、浮点比较 $10^{-9}$、事件只注入一次、t=0 投放先于抽样 |
| §2.4b 风暴抽样与注入 | ✅ 照做 | 齐次/非齐次泊松（S3 用 thinning）、对数正态 $\sigma_{\ln}=0.6927$ 固定、窄滩因子先因子后上限、S2 强制事件 $t=2.25$ 且按“实际后退”反解、事件表按 scenario+seed 共享、高斯足迹按峰值归一 |
| §2.4c $V$ 下限 / $R_c$ / 限制器 | ⚠ 部分偏差 | $R_c$=当前亏空、$y$ 不裁剪、$D_{\max}$ 诊断均照做；**限制器**实现为 $V_{\min}$ 处“全有/全无屏障”，不是“按比例缩放”，见 `[自决] 3` |
| §2.4d 足迹归一化 | ✅ 照做 | 峰值=1；`events.csv` 记中心后退、$x_k,\sigma_e$、中央/全域注入体积 |
| §2.5 补沙 / 成本 / 沙源 | ✅ 照做 | 重叠长度加权（断言 $10^{-12}$）、四种 $c_1^{\text{eff}}$ 组合（27/30/11/14）、`V_j<1e5` 记 `skipped_reason` |
| §2.5c 命名（placement vs strategy） | ✅ 照做 | `uniform/hotspot/multi` 与 `once/repeat/targeted/adaptive` 分离；E1 理想 $t=0$、E4 计 1.75 yr 时滞 |
| §2.6 三套边界 | ✅ 照做 | open（ghost=内点）、zeroflux（总通量 0）、dirichlet（ghost=$2y_b-y_0$）；体积通量 $H F\Delta t$ 只乘一次 |
| §3.5 全局口径 | ✅ 照做 | 内部绝对 $V$、台账增量、指标中央 5 km、流出为正、投放吸附到步边界、两类 RNG 流（实际用了 4 条） |
| §4 输出 schema | ✅ 照做 | `results.json` 固定键；`fields.npz` 补上了 `exhausted[nt,nx]`（本轮修复）；`ledger.csv` 含 `R_c_cum`/`D_max_cum`/`Q_limited_cum`；`events.csv` 字段齐 |
| §5 T1–T13 | ✅ 全过（另加 T12b） | 见 §2 |
| §6 解析基准（A/B/C） | ✅ 对上 | 6.16 / 7.34 / 7.38 vs 6.15 / 7.33 / 7.36 |
| §7 E0–E7 | ✅ 全跑 | E5 含 Sobol（N=96，有噪声）；E7 为**关闭风暴**的确定性相图 |
| §9 交付物 | ✅ | 测试日志、结果树、总表、F1–F8、`REPRODUCE.md`、已知问题 |

> 其他小偏差：合同 §3 的示例 `--strategy A` 是旧命名；按 §2.5c 主算用 `once/repeat/...`，
> `--strategy A` 会报错（这是有意为之，不是 bug）。`--mc` 参数在本实现里叫 `--n`。

---

## 2. 验收与审计（可复核）

| 层 | 命令 | 结果 |
|---|---|---|
| 参考原型 | `python modeling/sanity/discrete_contract.py` | ALL PASS |
| 验收测试 | `python -m pytest tests -v -s` | **17 passed**（4 s） |
| 合同自检 | `python tools/verify_contract.py` | **67/67** |
| 结果审计 | `python -m exp.audit` | **2268 checks / 0 failed** |
| 一键门禁 | `python -m exp.check_all` | ALL PASS |

审计覆盖：`results.json` schema/删失语义、`ledger.csv` 逐行闭合重算、`D_max≥R_c`、
`fields.npz` 键/形状/`exhausted`、MC 行数与分位单调、E1 沙去向三项求和、E4 c0 网格、E7 192 格、
F1–F8 PNG 完整性。明细：[`results/validation/AUDIT.json`](../results/validation/AUDIT.json)。

---

## 3. 需要你裁决的 9 条 `[自决]`

> 每条包含：问题 → 我的选择 → 证据 → 若否决的影响。**除第 4 条外都已在 `PROGRESS.md` 提问表登记。**

### 3.1 `w0_min` 自检与 360 格网格不相容（等级 C）
- 问题：合同 §2.0 要求 `abs(w.min()-16)<1e-9`，但同时要求 360 格、中央恰 200 格。
  360 个格心在 $\pm12.5,\pm37.5,\dots$，**没有 x=0**，故 $w_{\min}=16.00143$。
- 选择：保留 360 格（中央 200 格的硬约束优先）；自检放宽到 $2\times10^{-3}$。
- 影响：$f_w(0)=0.30359$（解析 1518/5000=0.3036），无数值问题。
- 若否决：改奇数格会破坏“中央 200 格”，需改合同并**全套重跑**（≈9 min）。

### 3.2 $f_c(t)$ 用分段线性重构（等级 B）
- 问题：逐格计数让阈值穿越有“1 格=1%”的量化，$dx=50$ vs 25 的 $T_{\text{first,fail}}$ 差 2.7% > T4 的 2%。
- 选择：对 `risk` 指示函数在格心间做分段线性积分（同一连续定义）；逐点 `risk_w/risk_b` 仍是布尔。
- 证据：$f_w(0)=0.3036$（合同解析值）；T12 的 ±0.005 同时容纳 0.3000 和 0.3036；T4 从 2.7% 降到 0.07%。
- 若否决：改回逐格计数 → $E_w,E_b$、四个时长全部变化，**全套重跑**（≈8.5 min）。

### 3.3 通量限制器 = $V_{\min}$ 处全有/全无屏障（等级 B）
- 问题：合同要求“按比例缩放该单元的**对岸**通量，未搬走的部分不记账”。隐式 BE 中做到
  “比例缩放 + 严格守恒 + 与相邻单元一致”需要非线性 active-set/变分解，复杂度高。
- 选择：在步前把“已耗尽（$V\le V_{\min}$）”单元的**流出面**置零（同一面两侧一致，守恒不变）；
  被挡住的潜在输沙记 `Q_limited_cum` 诊断。**只挡流出，允许流入**。
- 证据：$Q_{\text{limited}}$ 可达 $10^6$–$10^7$ m³（热点耗尽区），但 T1 闭合不受影响；
  `Q_limited` 已进 `results.json.mass`，论文可披露。
- 若否决：需要重写输运算子并**全套重跑**；建议至少在 Limitations 写一句“耗尽区沿岸输沙被屏障化”。

### 3.4 自适应 $\Delta E_b$ 并列时回退选址（等级 C）
- 问题：5 年预报窗口在 S1/S2 内常常**没有建筑风险**（$T_{\text{first,fail}}^b\approx14$ yr），
  所有候选位置的 $\Delta E_b=0$，`argmax` 会给出任意位置。
- 选择：并列（$\max\le10^{-12}$）时回退到“风险加权亏空最大”的位置，并记 `benefit_fallback=true`。
- 若否决：改回严格 argmax 会得到 -1500 m 等任意选址；E4 adaptive 需重跑（≈2 min）。

### 3.5 风暴组 OAT/Sobol 固定 `rho_e_scale`（等级 B）
- 问题：情景缩放 $\text{scale}=(\text{target}-\rho^{\text{storm}})/2.31$ 会把 $\lambda_s,\Delta y$ 的变化
  **补偿**掉（风暴变弱 → 慢性侵蚀自动变强），OAT 测到的是“风暴/慢性分配”，不是风暴本身。
- 选择：风暴组（$\lambda_s,\Delta y_{\text{ref}},k,\lambda$）的 OAT/Sobol 固定 S2 的 scale=1.068。
- 若否决：E5 的风暴组与 Sobol 第 2 组需重跑（≈2 min），`F6` 的符号解释会反过来。

### 3.6 T13“相对残差”取终值/投放量（等级 C）
- 问题：`residual_rel` 的分母是 `max(1,|placed_cum|)`；投放前的行分母=1，绝对残差 $10^{-8}$ 会被读成 $10^{-8}$“相对”。
  若对全表取最大，T13 的 $<10^{-10}$ 永远过不了。
- 选择：T13 用**终值行**、分母=投放量（实测 $1.4\times10^{-14}$）；T1 仍看全表最大值（$1.9\times10^{-7}<10^{-6}$）。
- 若否决：只影响测试口径，不需要重跑动力学。

### 3.7 E3 方向与文档预期不同（等级 B）
- 见 §4.2。不调参去凑预期；若坚持“early 最大”，需改 E3 设计并重跑（3 s）。

### 3.8 T9 缺 GIS 原始文件（等级 B）
- 处理：写 [`results/validation/T9_report.md`](../results/validation/T9_report.md)，含可引用 OBS 值
  （Rodanthe LRR78_2002 −3.43、LRR89_2002 −4.58）与重算步骤；**不伪造**。
- 需要：补 `_gis/hatteras_transects/Hatteras_Transects.dbf`，或确认放弃 T9。

### 3.9 L0 双计数偏差只有 +1.6%/+3.5%（等级 B）
- 见 §4.1。这是**本轮最重要的口径发现**，直接影响论文“保守偏差”的表述。

---

## 4. 结果与文档预期不一致的 4 处（如实报告，未调参）

### 4.1 L0：+22.5% 不成立，实测 +1.6%/+3.5%
- 口径 (i)：走廊场均值 2.314；**无风暴**模型 2.207；**有风暴** 2.350 ⇒ 风暴实现贡献 **+0.143 m/yr**，
  相对场均值 **+1.6%**。
- 口径 (ii)：场均值 1.791；无风暴 1.665；有风暴 1.854 ⇒ **+3.5%**。
- 原因：$\rho^{\text{storm}}$ 用的是宽滩潜在后退 $\mathbb E[\Delta y]=10.2$ m，
  实际事件被 ①窄滩因子 $f=0.55$–$0.71$、②15 年后半段干滩耗尽（$\Delta y=0$）压低。
- **影响**：D11 的“>30% 才切换口径”规则不触发；但论文不能再用“模型比观测保守 22.5%”。
  热点峰值 3.04 m/yr，落在 DEQ 3.8–4.0 的**下沿**——风险可能被**低估**（方向与旧文档相反）。
- 明细：[`results/L0/summary.json`](../results/L0/summary.json)。

### 4.2 E3：spread 的 $E_w$ 最大，不是 early
- 数字：early 21 902、spread **24 766**、late **20 059** m·yr；
  late 的保护年数最好（10.99 yr）但 2042 年中心滩宽最差（0.7 m）。
- 解释：早期风暴打在补沙后的**宽滩**上，$f<1$ 使实际后退被压低；中期的风暴打在已扩散的滩肩上。
- 结论方向仍成立：“时机改变的是风险分布，不只是总量”；但**不能照抄“early 的 E 最大”**。

### 4.3 热点峰值低于 DEQ 下沿
- 模型热点 3.04 m/yr（L0 口径 i）；DEQ 3.8–4.0。若论文要与 DEQ 对齐，需要上调 $a_h$ 或 $\rho_e$，
  那是**改合同**并全套重跑；当前结果应写成“低于观测上端”，并作为 Limitations。

### 4.4 $c_0$ 无交叉点
- 在 `marginal_plus_fixed` 下，$c_0\in[0,10]$M 不改变 $E_b/E_w$（恒 0 或不变），成本线性上升。
- 原因：本地沙 2.45M 是紧约束，预算 $C_{\max}=120$M 从未绑定。
- 与文档“不要预设必须有翻转点”一致；若论文必须有交叉点，需改 $C_{\max}/S_{\text{borrow}}/c_1$ → E4 重跑。

---

## 5. 数据缺口 / 请求（按优先级）

| # | 需要什么 | 用途 | 没有它的后果 |
|---|---|---|---|
| D1 | `_gis/hatteras_transects/Hatteras_Transects.dbf`（或 shapefile 包） | T9 / Q3 观测对照 | 只能引用资料库预计算值，不能重算分布 |
| D2 | DEQ 图 79/80 的**逐 transect 速率表** | 替换热点参数化 $\rho_e(x)$ | 热点形状仍是 ASSUME（A-03/A-07） |
| D3 | Rodanthe 实测剖面（$h_*$、$B$、$D_{50}$） | 约束 $H$、$D$ | $H=10$ 仍是 MODEL/ASSUME |
| D4 | 逐栋建筑退距 $d_b(x)$ | 建筑净距指标 | $d_b=28$ m 是 ASSUME（20–45） |
| D5 | 2027–2042 的观测岸线时间序列（至少 2–3 期） | 真正的 out-of-sample 验证 | 只能做跨资料一致性检查，不能称“验证” |

---

## 6. 论文可直接用 / 不可用的表述

| ✅ 可以写（标 MODEL/MODEL-SCENARIO） | ❌ 不能写 |
|---|---|
| “显式风暴相对**同一场地无风暴模型**只增加约 +6%；相对场均值 +1.6%” | “模型比观测保守 22.5%” |
| “本地沙源 2.45M m³ 是紧约束，$V_{15}$ 3.5–6.8M 对结果无影响” | “加预算就能延长保护期” |
| “S3 下 `repeat` 的 $E_b$ 最低但 $E_w$ 最差；`targeted` 反之” | “存在唯一最优策略” |
| “hotspot 1 km 的保护岸线·年比 uniform 高 3.8%” | “热点投放显著优于匀铺”（差异很小） |
| “边界/域使 15 年留存变化 −6%～−12%，<30%” | “结论对边界不敏感”（要报区间） |
| “T9 观测 LRR 为 −3.43/−4.58 m/yr（OBS，跨资料检查）” | “模型验证了 DEQ/USGS 速率” |
| “未建模沙丘/越浪/硬工程；$E$ 是岸线长度加权” | “模型预测了 32 栋房屋倒塌” |

---

## 7. 建议的裁决顺序（在论文冻结数字前）

1. **P0（会改所有数字的定义）**：$f_c$ 聚合（3.2）、通量限制器（3.3）——两项各 ≈8.5 min 重跑。
2. **P0（会改论文措辞）**：L0 偏差（4.1）、热点峰值（4.3）——先定“是否改 $\rho_e/a_h$”，再决定是否重跑。
3. **P1（只影响单实验）**：E3 方向（4.2）、自适应回退（3.4）、风暴组缩放（3.5）、targeted 定义。
4. **P2（补数据）**：D1–D5；T9 先补 D1 即可。
5. 每次裁决后执行 `python -m exp.check_all`，并把新的 `AUDIT.json`/`pytest.log` 一起提交。

---

## 8. 数字溯源索引（抽查用）

| 结论 | 来源文件 |
|---|---|
| 17 项验收 | `results/validation/pytest.log` |
| 2268 项审计 | `results/validation/AUDIT.json` |
| E0 基线 | `results/E0/summary.json`、`E0/*_mc/mc_summary.json` |
| E1 三布置/沙去向 | `results/E1/summary.json`、`E1/uniform/destinations.csv` |
| E2 MC | `results/E2/*_mc/mc_summary.json` |
| E3 时机 | `results/E3/summary.json` |
| E4 策略/c0 | `results/E4/summary.json`、`E4/c0_scan_S2/c0_scan.json` |
| E5 敏感性 | `results/E5/summary.json`、`E5/sobol/sobol_summary.json` |
| E6 边界/域 | `results/E6/summary.json` |
| E7 相图 | `results/E7/phase.csv` |
| L0 双计数 | `results/L0/summary.json` |
| 复现命令 | `REPRODUCE.md` |

---

## 9. 复核入口

```powershell
python -m exp.check_all        # 一键：原型 + 17 测试 + 67 合同 + 2268 审计
python -m exp.audit            # 只看结果层
python -m pytest tests -v -s   # 只看验收
```
