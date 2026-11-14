# FIX_v7 — v6 复核与剩余四处（2026-11-14 22:55）

> 对象：`2701(5).pdf`（v6，**25 页**）。
> 先说结论：**页数、页眉、参考文献、配对均值四处已修好；但专家二的两条最重要意见没落进去。**

---

## 1. v6 已修好的（逐项核过）

| 项 | 状态 | 证据 |
|---|---|---|
| 页数 | ✅ **25 页** | 全员 `of 25` |
| 页眉 | ✅ `Page N of 25`，`Training Team`（培训期免控制号，符合老师通知） | 每页一致 |
| 参考文献 | ✅ **5 → 14 条** | [6] Dean 1991、[7] Larson & Kraus 1989、[8] Ashton & Murray 2006、[9] Frazer et al. 2009、[10][11][12] 项目/新闻 |
| §8 口径 | ✅ 配对均值 + 95% CI（−2,693 [−2,813, −2,573]） | 与 `policy_pairwise.csv` 一致 |
| ρstorm 措辞 | ✅ 新增"有限时域下 $O$ 存沙 ⇒ 不是终值后退上界" | 比 v5 准确 |
| 正文 12 pt | ✅ 50 444 字符主字号 12.0 | — |

**我顺手核了新增文献的真伪**（这是最容易出事的环节）：
- [10] Coastal Review 那篇 **真实存在**（2018-06-22，URL 可访问）；
- [11] WRAL 那篇 **真实存在**（2025-10，3D mapping Buxton）；
- [9] Frazer 2009 **真实**，而且 AGU 还发过一份 *Correction*（10.1029/2009GL041993）——建议在 [9] 后加 "(see correction, doi:10.1029/2009GL041993)"；
- [12] Outer Banks Voice 2026-05-15 那篇**未能独立确认**，且**PDF 里的 URL 被截断**（停在 `...-for-bux`）。

---

## 2. 【P0-a】L0 循环论证：**还没改**（专家二的第一条）

v6 §4.3 仍然只写：

> "…total with-storm retreat exceeds that field mean by only 2.01%."

这正是专家指出的问题：**2.3136 就是我们自己注入的 $\rho_{\text{base}}$ 场的走廊平均**，所以"只高 2.01%"是恒等式的算术结果。

**在 "…by only 2.01%." 之后紧接着插入**（英文，可直接粘）：

> "This comparison is a **consistency check on the implementation, not an independent validation**: the 2.3136 m/yr reference is the mean of the rate field that is *injected* as model input, so agreement follows once the ledger closes. It confirms that the solver transports the storm contribution as specified; it cannot confirm that the injected field or the storm parameters match Rodanthe."

**同时检查摘要/结论**：若出现 "near-unbiased / close to unbiased / essentially unbiased"，改成 "matches the injected field mean to within the arithmetic contribution of the explicit storms"。

---

## 3. 【P0-b】预算边界：**还没改**（专家二的第 4 条）

v6 全文搜不到 `local-supply` / `external sand` / `budget binds`。专家的话很准：本地沙 2.45 M × 27 = 66.15 M < 120 M，**"预算不绑定"是设置必然，不是发现**。

**在 Q5 约束段（§8.1 或政策表之后）插入**：

> "The binding constraint is configuration-dependent, and the Monte Carlo comparison is restricted to **local supply**. With local sand the supply cap binds first: 2.45 M m³ at 27 USD/m³ = 66.15 M USD, well below the 120 M USD programme ceiling. With external sand at 30 USD/m³ the **budget** binds first, at $120/30 = 4.0$ M m³; the deterministic diagnostics `DIAG_external_all_in_repeat` (4.0 M m³) and `DIAG_local_all_in_once` (2.45 M m³) bracket these two regimes. A paired Monte Carlo comparison in the money-binding regime is not part of this study."

> 这句话既回答了专家的"结构性不绑定"，又用**已有数据**把外调情景变成"已覆盖"，不需要补跑。

## 4. 【P1-c】表 3 的 OBS 行仍无来源注

表下加一行：

> "OBS entries: $\rho_{\rm obs}$ from [1, 5]; $c_1$ is the planning-level all-in unit cost (27 USD/m³) for recent Dare County projects, consistent with [5]; the USGS transect rates used in the Q3 holdout are from [2]."

## 5. 【P1-d】参考文献 [12] 的 URL 被截断

PDF 里停在 `.../2026/05/15/dare-county-announces-start-dates-for-bux`，后面直接接 [13]。
二选一：
- 用 `\usepackage{xurl}` + `\url{}` 让它自动换行（推荐）；
- 或**确认这篇文章确实存在**再保留；**若无法确认，就删掉 [12]**，把 2026 Buxton/Avon 的开工时间改引 Dare County 官方项目页（`darenc.gov/government/beach-nourishment`）——官方页一定在。

> ⚠ 编造文献是 AI 政策点名的风险项。**[10][11] 已核实为真，[12] 尚未确认**，请在 1 小时内确认或替换。

## 6. 改完的终检（我做，20 分钟）

| # | 判据 |
|---|---|
| 1 | 页数 = 25 |
| 2 | 每页 `Page N of 25` |
| 3 | 出现 "consistency check on the implementation" |
| 4 | 出现 "restricted to local supply" 且含 4.0 M 的算术 |
| 5 | 表 3 有 OBS 注 |
| 6 | [12] 的 URL 完整或已替换 |
| 7 | Table 4 的 60 个数、摘要 8 个数未动 |
| 8 | 12 pt 主字号 |

## 7. 时间

现在 **22:55**，内部硬停 **11/15 18:00**（还有 19 h），系统截止 **11/16 00:00**（25 h）。
这四处都是**纯文本插入**，预计 20 分钟。改完我立刻终检并更新审阅包。
