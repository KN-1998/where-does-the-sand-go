# PAPER_REVIEW_R1 — 2701.pdf 建模正确性审查（2026-11-14 00:55）

> 审查对象：`2701.pdf`（21 页，*Where Does the Sand Go? A Sediment-Budget Model for Adaptive Beach Nourishment*）
> 审查范围（按 AGENT BRIEF §6）：**公式、数字、结论与台账一致性**。不改文风。
> 对照基准：`modeling/MODEL_SPEC.md` v0.6、`modeling/DECISIONS.md` D1–D18、R2 结果包（`results/release_20261113_r2/`）、`ledger/claims.csv`。

---

## 0. 结论

**整体质量高**：五问齐全、公式基本正确、数字与 R2 结果包对得上、限制写得诚实（"not a validated forecast"、"not collapse probability" 都主动写明）。
**但有 2 个 P0：论文对模型的描述与代码不一致**——读者按论文复现会得到另一个模型。另有 2 个 P1 建议。

| 级别 | 数量 | 是否阻塞提交 |
|---|---|---|
| **P0** | 2 | **是**。描述与实现不符，属"论文说错了自己的模型" |
| P1 | 2 | 否，但明显削弱 Q2 的论证力 |

---

## 1. P0-1：慢性侵蚀率的口径写反了

### 论文怎么说
- **§3 假设 A6**（p.4）：*"the main simulation uses a de-duplicated background rate. The unadjusted observed rate is retained as a sensitivity case."*
- **§4.3 式 (9)**（p.6）：$\rho^{\text{bg}}=\rho^{\text{obs}}-\rho^{\text{storm}}$，$L_c=H\rho^{\text{bg}}$。
- **§4.3 正文**（p.7）：*"Using the frozen parameter-registry values gives $\rho^{\text{storm}}=0.522$ m/yr and $\rho^{\text{bg}}=1.178$ m/yr … **They define a background sink**"*
- **参数表**：$\rho_e=1.178$ 标 `MODEL`，$\rho^{\text{obs}}=1.7$ 标 `OBS`（并列，但主次颠倒）。

### 代码/参数实际是什么
```
modeling/params.yaml:  rho_e = 1.7   （note: "D11 口径 i：保留观测值，不扣风暴"）
                       rho_storm = 0.522（note: "仅诊断/核对，不扣除"）
                       rho_bg_sens = 1.178（note: "口径 (ii)，仅敏感性"）
src/sim/model.py:      rho_base = value(params,"transport","rho_e") * (1 + a_h*exp(...))
                       scale = (target - rho_storm) / rho_e_corridor_mean
```
即：**主算用 $\rho^{\text{obs}}=1.7$，显式风暴叠在上面，接受双计数；1.178 只作敏感性。**

### 为什么会这样
建模手 **D11 裁决为口径 (i)**：保留观测值、承认偏高、由 L0 核对。论文写成了口径 (ii)。

### 证据：论文自己也按 (i) 在算
§7 写 *"realized mean dry-beach retreat is 1.511, 2.628, 3.108 m/yr … about 11%, 12%, 22% below the corresponding **configured targets of 1.7, 3.0, 4.0**"*。
这些目标只能用 $\bar\rho_e=2.31$（源自 1.7）缩放得到；若主算真是 1.178，S1 的实现值会是 ~1.0 而不是 1.511。

### 建议改法（三处）
1. **A6**：
   > "The main simulation **retains the observed long-term rate** ($\rho^{\text{obs}}=1.7$ m/yr) and adds explicit storms on top of it, accepting a deliberate upward bias in the chronic sink; a de-duplicated background rate ($\rho^{\text{bg}}=1.178$) is carried as a **sensitivity case**."
2. **§4.3**：把式 (9) 保留为**定义**，但正文改成"两种口径"：
   - 口径 (i)（主算）：$L_c=H\rho^{\text{obs}}$；
   - 口径 (ii)（敏感性）：$L_c=H\rho^{\text{bg}}$。
   并给出**上界与实际**：解析上界 $+22.9\%$，R1 的 L0 实测 **$+1.6\%$**；R2 的实现速率比名义目标低 11–22%（耗尽饱和）。**不要**再写"they define a background sink"。
3. **参数表**：$\rho_e=1.7$ 标 `OBS / main`；$\rho^{\text{bg}}=1.178$ 标 `MODEL / sensitivity`。

> 若不改：审稿人一算 $L_c$ 就会发现论文的 17.0 与 11.78 对不上（差 31%），且与 §7 自相矛盾。

---

## 2. P0-2：$R_c$ 的语义写反了

### 论文怎么说
- **表 1**（p.5）：*"$R_c$ — Unresolved landward sediment-deficit counter after dry-beach exhaustion"*
- **§4.4**（p.7）：*"the unresolved deficit is recorded in a **monotone** landward-loss counter $R_c$ … Later nourishment may restore positive beach width, but **past deficit in $R_c$ is not erased**."*

### 代码实际是什么
`tests/test_mass.py:53`：
```python
self.assertLess(result.ledger[-1]["R_c_cum"], result.ledger[250]["R_c_cum"])
```
即**补沙后 $R_c$ 必须下降**。$R_c$ 是**当前亏空**（可恢复）；单调的是另一个诊断量 `D_max`（"cellwise peaks"，见 `test_metrics.py:46`）。

### 背景
2026-11-11 的复核发现"侵蚀 5 年再补回 5 年"时，**峰值版 $R_c$ 会让账本不闭合**（残差 $3.6\times10^{6}$ m³）；D15 已修订为当前亏空，并新增 T13 守住该性质。

### 建议改法
- 表 1：*"$R_c$ — **current** unresolved sediment deficit after dry-beach exhaustion (recoverable); a separate monotone diagnostic $D_{\max}$ records the historical peak"*
- §4.4 末段：
  > "$R_c$ is the **current** deficit $[V_{\min}-V_{\text{abs}}]^{+}$; it **falls again** when nourishment or onshore recovery lifts the profile, which is what keeps the ledger closed (T13). The monotone quantity is the diagnostic $D_{\max}=\max_t R_c$, which is not used in the conservation identity."

---

## 3. P1-1：Q2 缺定量对比（浪费了 R2 的现成数据）

§5.1 只有 Figure 2 的剖面与定性描述（"hotspot creates the largest local crest … differences reduced by year 15"），**没有任何暴露量数字**，因此无法回答题面"比较至少两种布置"的强度。

**R2 已有现成结果**（`mc_comparison.csv`，S1，同 2.45 M m³，1000 次 MC）：
$$\bar E_w = 3.05\ (\text{uniform}) < 18.64\ (\text{multi}) < 38.59\ (\text{hotspot})\ \text{m·yr}.$$

**建议**：在 §5.1 末加一句 + 一个小表，并给判别条件：
> "At $\mathcal V/\mathcal V_{\rm thr}\approx12$, **uniform placement dominates**: spreading keeps the whole corridor above the 20 m threshold ($E_w=3.0$), whereas a 1-km hotspot leaves the remaining 4 km below it ($E_w=38.6$). Concentration only becomes necessary when $\mathcal V<\mathcal V_{\rm thr}=H L(w_{\rm mgmt}-w_{\min})=2\times10^{5}$ m³, i.e. when the budget cannot lift every section at once."

> 这条同时把 §5.3 的 $\mathcal V_{\rm thr}$ 与 Q2 的结论接上，让"宽滩不持久"的判别**可计算**而不是只靠图。

## 4. P1-2：Q5 的"中位差"与"配对均值差"混用

§8 写 *"repeated placement improves median $E_b$ by 2,935 m·yr … worsens median $E_w$ by 18,271"*；而 `policy_pairwise.csv` 给的是**配对均值**差（S3 repeat: $-2\,693$ / $+17\,339$，95% CI 不含 0）。

两个口径都对，但**必须说明是哪一个**，否则读者复算对不上。

**建议**：统一用配对均值 + CI（统计上更干净），或显式写 *"median of paired differences"*。

---

## 5. 已核对通过的部分（可放心保留）

| 项 | 结论 |
|---|---|
| 式 (2) $V=V_0+Hy$、式 (7) 岸线方程 | ✅ 与 `MODEL_SPEC` 一致 |
| 式 (6) $Q=Q_0-DH y_x$ 与 $V_{0,x}$ 的提醒 | ✅ 正确且难得 |
| 式 (8) CERC 与 $3.156\times10^{7}$ 秒→年换算 | ✅ 正确 |
| 式 (10)(11) 风暴足迹与"先因子后上限" | ✅ 正确 |
| 式 (18) 守恒式（$-\int R_c$ 为减项） | ✅ 与 D15 一致 |
| 式 (19)(20) erf 解与 $T_{1/2}=0.2748\ell^2/D$ | ✅ 与原型一致 |
| 质量残差 $2.107\times10^{-8}$ | ✅ 与 R2 `audit.json` 一致 |
| 留出 $R^2=-4.30$、RMSE 4.785、0.270 vs 4.579 | ✅ 与 `本轮检查与结果.md` 一致 |
| "not a validated forecast / not collapse probability / adaptive not automatically optimal / does not establish optimum" | ✅ 主动限定，符合红线 |
| 18 000 次 MC | ✅ 与 R2 一致 |

---

## 6. 还没核的（需要原文/附录）

- 参考文献是否都有对应条目（本审查只管数字与模型）；
- 技术信（1 页）不在这份 PDF 里——按题面必须单独 1 页；
- 页数：21 页 + 1 页摘要（在正文内）+ 1 页信函 = 22 ≤ 25 ✅。

---

## 7. 修改优先级（建议 2 小时内改完前两条）

1. **P0-1**（§3 A6 / §4.3 / 参数表）——不改会让"论文 ≠ 代码"，最致命；
2. **P0-2**（表 1 / §4.4 末段）——不改与 T13 断言直接冲突；
3. P1-1（Q2 加三个数）——**性价比最高**，一行数 + 一句判别条件；
4. P1-2（口径标注）——半句话。

---

## 8. v2 复核（2026-11-14 11:30，`2701(1).pdf`，22 页）

### 8.1 四处修改：全部到位

| 项 | 判定 | 证据（v2 原文） |
|---|---|---|
| **P0-1** 口径 | ✅ 改对 | A6："The main simulation nevertheless retains the observed rate (ρobs = 1.7 m/yr) … A de-duplicated rate (ρbg = 1.178 m/yr) is retained as a sensitivity case"；§4.3："convention (i) … 1.7 … upper bound ≈23% … convention (ii) … 1.178 … sensitivity only"；表 2："ρobs 1.7 — **Main production rate**"、"ρbg 1.178 — **Sensitivity rate**" |
| **P0-2** $R_c$ | ✅ 改对 | 表 1："Current unresolved sediment deficit … **recoverable** when the profile is replenished"＋"A separate diagnostic Dmax = max_t Rc"；§4.4："Only the descriptive diagnostic Dmax … is monotone; it is absent from the ledger"；全文 "not erased" 出现 0 次 |
| **P1-1** Q2 三数 | ✅ 改对 | §5.1："median 15-year beach-width exposure is 3.05 … 18.64 … 38.59"，$\mathcal V/\mathcal V_{
m thr}pprox12$，$\mathcal V_{
| **P1-1** Q2 三数 | ✅ 改对 | §5.1：median 15-year beach-width exposure 为 3.05 / 18.64 / 38.59；给出 V/V_thr ≈ 12 与 V_thr = 2.0e5 m³，并注明「tests instantaneous coverage; it does not by itself identify an optimal layout」 |
| **P1-2** 口径标注 | ✅ 改对 | §8："paired mean difference $\Delta E_b=-2{,}693$ m·yr (95% MC interval $[-2{,}813,-2{,}573]$) but $\Delta E_w=+17{,}339$" — 与 `policy_pairwise.csv` 逐字一致 |

### 8.2 未被误改（回归检查）

- **Table 4 的 60 个数全部保持**（10 行 × 6 列逐项比对）；
- 摘要 8 个关键数（2.11e−8、66.15、60.21、1,418、1,958、4,892、33,948、52,219）全部保持；
- 表 1–4、图 1–6 编号连续、正文均有引用；
- 22 页 ≤ 25；摘要页与技术信仍在。

### 8.3 新发现 2 处（不阻塞）

**[P2] §4.3 的 "0.14 m/yr / 1.6%" 来源是 R1，不是 R2。**
v2 §4.3 写："the simulated storm contribution over 15 years is about 0.14 m/yr, or 1.6% relative to the corridor mean"。
但 R2 发布包里**没有口径核对实验**（无 L0 / caliber 目录，`erosion_target_diagnostic.csv` 只有三情景的实现速率）。该数字来自 R1 的 `results/L0/summary.json`（`realised_storm_contribution=0.1436`，`bias_vs_field=0.0159`）。
而 §6.2.4 明确写："All reported production values … come from results/release_20261113_r2 … R1 outputs are not combined with the R2 results." → **自相矛盾**。

两条修法（二选一，约 10 分钟）：
1. **让编程手在 R2 下补跑口径核对**（无补沙、风暴开/关各一次，15 yr），得到 R2 版本的贡献值，替换 0.14/1.6%；
2. 或删掉精确值，只保留："the realised bias is much smaller than the analytic bound because the narrow-beach cap and dry-beach exhaustion suppress later events"（不引数字）。

**[P3] §5.1 新增的布置对比表没有表号。** 其余三张表都有 "Table N:" 标题；这张以 "Layout | Placement length | Median Ew" 直接起行。补齐为 "Table 3" 并把后续表顺延，或写成正文行内三联数（更省事）。

### 8.4 判决

**通过**。P2/P3 建议在冻结前顺手改掉；不构成阻塞。
