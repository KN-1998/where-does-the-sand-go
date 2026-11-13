# CHANGE_REQUEST_PAPER_R1 — 给论文手的修改单（2026-11-14 00:40）

> 对象：`2701.pdf`（21 页）。
> 本文件**只列要改的地方**，每条给"原文 → 改为（可直接粘贴的英文）"。理由与证据见 `handoff/PAPER_REVIEW_R1.md`。
> **前两条是 P0**：不改会让论文描述的模型与代码不是同一个模型。建议 2 小时内改完。

---

## P0-1 §3 假设 A6 + §4.3 + 参数表：侵蚀率口径写反

**现状**（p.4 A6 / p.6 式 9 / p.7 正文）：论文说主算用去双计数的 $\rho^{\text{bg}}=1.178$，把观测值 1.7 当敏感性。
**实际**（`modeling/params.yaml`、`src/sim/model.py`、发布包 `resolved_config.yaml`）：主算用 **$\rho^{\text{obs}}=1.7$**，显式风暴叠在上面；1.178 只作敏感性。这是建模手 D11 的**口径 (i)**。

### 改 1：A6（p.4）

> **原**：*"No double counting. Because the observed long-term erosion rate already contains an average storm contribution, the main simulation uses a de-duplicated background rate. The unadjusted observed rate is retained as a sensitivity case."*

> **改为**：
> "A6. Chronic rate and storm separation. The observed long-term erosion rate already contains an average storm contribution, so adding explicit storms on top of it double-counts that contribution. The main simulation nevertheless **retains the observed rate** ($\rho^{\text{obs}}=1.7$ m/yr) as the chronic sink and adds storms explicitly, which makes the modelled retreat deliberately conservative (an analytic upper bound of about +23 %). A de-duplicated background rate ($\rho^{\text{bg}}=1.178$ m/yr) is carried as a **sensitivity case**. The realised bias is checked in Q3 and is only +1.6 %."

### 改 2：§4.3（p.6–7，式 9 之后）

> **原**：*"Using the frozen parameter-registry values gives $\rho^{\text{storm}}=0.522$ m/yr and $\rho^{\text{bg}}=1.178$ m/yr from an observed segment-average rate of 1.7 m/yr. These numbers do not forecast any particular year. They define a background sink whose combination with simulated storms must be checked against the observed long-term range."*

> **改为**：
> "Equation (9) defines the two calibres. **The main simulation (calibre i) uses $L_c=H\rho^{\text{obs}}$**, i.e. the observed 1.7 m/yr, and adds storms explicitly; this is a deliberate upward bias whose analytic upper bound is $\rho^{\text{storm}}/\bar\rho_e=0.522/2.31\approx+23\%$. **Calibre ii** ($L_c=H\rho^{\text{bg}}$, 1.178 m/yr) removes the storm contribution and is reported as a sensitivity case.
> The realised bias is much smaller than the bound: with the narrow-beach cap and dry-beach exhaustion, the simulated storm contribution over 15 years is about 0.14 m/yr, i.e. **+1.6 %** relative to the corridor mean, and the realised retreat in the three scenarios is 11–22 % **below** the configured nominal rates. Neither $\rho^{\text{obs}}$ nor $\rho^{\text{bg}}$ forecasts any particular year."

### 改 3：参数表（p.4–5）

| 参数 | 原标签 | 改为 |
|---|---|---|
| $\rho_e=1.7$ | `OBS` | `OBS`，并加 `main` |
| $\rho^{\text{bg}}=1.178$ | `MODEL` | `MODEL`，并加 `sensitivity` |

---

## P0-2 表 1 + §4.4 末段：$R_c$ 写成单调、不可恢复

**现状**（p.5 表 1；p.7 末段）：*"monotone landward-loss counter $R_c$ … past deficit in $R_c$ is not erased."*
**实际**：$R_c$ 是**当前亏空**，补沙后必须下降（`tests/test_mass.py:53` 有断言）；单调的是诊断量 $D_{\max}$。

### 改 4：表 1 的 $R_c$ 行（p.5）

> **原**：*"$R_c$ — Unresolved landward sediment-deficit counter after dry-beach exhaustion — m³/m"*

> **改为**：
> "$R_c$ — **current** unresolved sediment deficit after dry-beach exhaustion (recoverable; falls again when the profile is replenished) — m³/m"
> 并在表下加一行脚注：
> "A separate diagnostic $D_{\max}=\max_t R_c$ records the historical peak deficit; it does not enter the conservation identity."

### 改 5：§4.4 末段（p.7）

> **原**：*"If the lower bound is reached and continuous sinks would remove additional material, the unresolved deficit is recorded in a monotone landward-loss counter $R_c$ instead of producing a negative physical inventory. Later nourishment may restore positive beach width, but past deficit in $R_c$ is not erased."*

> **改为**：
> "If the lower bound is reached and continuous sinks would remove additional material, the deficit is recorded in $R_c=[V_{\min}-V_{\text{abs}}]^{+}$ instead of producing a negative physical inventory. **$R_c$ is a current, recoverable deficit**: nourishment or onshore recovery lifts $V_{\text{abs}}$ and $R_c$ falls, which is exactly what keeps the ledger closed (the identity in §5.2 carries $-\int R_c$). The monotone quantity is the diagnostic $D_{\max}=\max_t R_c$, which is reported for description only and is not used in any conservation check."

---

## P1-1 §5.1：Q2 补三个数（性价比最高）

**现状**：只有 Figure 2 的剖面，没有暴露量数字，无法量化"至少两种布置"的比较。

**在 §5.1 末尾加一句 + 一个小表**（数据来自 `mc_comparison.csv`，S1，同一 2.45 M m³，1000 次 MC）：

> "Equal volume does not imply equal exposure. Over 1000 storm realisations the median fifteen-year beach-width exposure is **3.0 m·yr for uniform placement, 18.6 for the multi-segment layout, and 38.6 for the 1-km hotspot** (Table X). The ordering follows the coverage criterion: with $\mathcal V/\mathcal V_{\rm thr}\approx12$, uniform placement lifts every section above the 20 m management width, whereas a 1-km placement leaves the remaining four kilometres below it. Concentration only becomes necessary when $\mathcal V<\mathcal V_{\rm thr}=HL(w_{\rm mgmt}-w_{\min})=2\times10^{5}$ m³, i.e. when the budget cannot raise every section at once."

| Layout | $\ell$ | median $E_w$ (m·yr) |
|---|---|---|
| Uniform | 5 km | **3.0** |
| Multi-segment (5 × 0.5 km) | 2.5 km | 18.6 |
| Hotspot | 1 km | 38.6 |

> 这样 §5.3 的 $\mathcal V_{\rm thr}$ 就与 Q2 的结论接上了，"wide beach need not persist" 变成**可计算的判别条件**。

## P1-2 §8：注明是"配对均值"还是"配对中位"

§8 写 *"improves median $E_b$ by 2,935 m·yr … worsens median $E_w$ by 18,271"*，而 `policy_pairwise.csv` 给的是**配对均值 + 95% CI**（S3 repeat：$\Delta E_b=-2\,693$，CI $[-2\,813,-2\,573]$；$\Delta E_w=+17\,339$）。

**二选一**：
- 用均值：*"paired mean differences: $\Delta E_b=-2\,693$ m·yr (95 % CI $[-2\,813,-2\,573]$), $\Delta E_w=+17\,339$ m·yr"*；
- 或保留中位但写明：*"median of paired differences"*。

---

## 不要改的（这些已经对）

- 式 (2)(6)(7)(8)(10)(11)(18)(19)(20)；
- 残差 $2.107\times10^{-8}$、留出 $R^2=-4.30$、0.270 vs 4.579、18 000 次 MC；
- 所有 "not a validated forecast / not collapse probability / adaptive not automatically optimal" 的限定句——写得很好，保留。

---

## 改完怎么回

在 `PROGRESS.md` 或 `handoff/` 下留一行：`论文 R1 修改：P0-1/P0-2/P1-1/P1-2 已改，2701_v2.pdf`。
我会按 `handoff/PAPER_REVIEW_R1.md` 的清单逐条复核（只核数字与模型，不核文风）。
