# REPLY_TO_WRITER_2026-11-14 — 回答论文手的四问 + v4 两处必改

> 对象：`2701(3).pdf`（v4，**25 页**）。
> 本文件回答你在群里提的 5 件事（沙量分项、借沙上限出处、分位数、0.8 可用率、S3 耗尽），并指出 v4 的 2 处必须修。

---

## 1. 守恒口径：**与你改后的式 (18) 完全一致**

**代码实现**：`src/sim/accounting.py:20–24`

```python
def residual(placed, flux_out, offshore_loss, chronic_loss,
             current_total, initial_total, deficit, initial_deficit):
    delta_total = current_total - initial_total
    return placed - flux_out - offshore_loss - chronic_loss - delta_total + deficit - initial_deficit
```

即恒等式为

$$\text{placed}=\Delta(V_{\rm book}+O)+\underbrace{(F_L+F_R)}_{\text{净边界输出}}+\lambda O\ \text{累计}+L_c\ \text{累计}-\Delta R_c$$

- **控制域**：`V_domain`、`O_domain` 是 **9 km 全域**（`V_domain` 已扣 $V_{\rm ref}$ 基线）；中央 5 km 用 `*_central` 列；
- **种子**：确定性跑 `seed=42`；MC 每个 `runs.csv` 行一个种子；
- **文件**：`results/release_20261113_r2/<RUN>/ledger.csv`，列名为
  `placed_cum, V_domain, O_domain, flux_outer_left_cum, flux_outer_right_cum, offshore_loss_cum, chronic_loss_cum, R_c_cum, residual, residual_rel`；
- **注意**：`flux_out = flux_outer_left_cum + flux_outer_right_cum`（**相加**，右边界本身是负值），不是"右减左"。我按错误的减法试过一次，残差 6 %——正确相加后 **残差 ≈ 0（7e−15）**。

### 可直接进论文的分解表（S1/S2/S3，`once`，seed 42，15 yr，单位 m³）

| 项 | S1 平静 | S2 速遇风暴 | S3 重复风暴 |
|---|---:|---:|---:|
| **投放 placed** | 2 450 000 | 2 450 000 | 2 450 000 |
| $\Delta(V_{\rm book}+O)$ 存量变化 | **+488 666** | **−976 697** | **−1 635 645** |
| 净边界输出 | 26 688 | 22 314 | 16 701 |
| 永久离岸损失 $\lambda O$ | 144 197 | 458 712 | 555 855 |
| 慢性沉汇 $L_c$ | 1 790 449 | 2 945 672 | 3 624 474 |
| $-\Delta R_c$ | 0 | 0 | −111 385 |
| **残差** | −0.0 | −0.0 | −0.0 |

**可以写进论文的一句强结论**：

> "In S2 and S3 the corridor **still loses** 0.98 and 1.64 M m³ of active sand over the fifteen years despite the 2.45 M m³ placement: the chronic sink (2.95 and 3.62 M m³) exceeds the placed volume, so nourishment delays rather than reverses narrowing. Permanent offshore loss accounts for only 0.15–0.56 M m³, i.e. 6–23 % of the placed volume."

（S1 里存量确实增加了 0.49 M m³，所以"补沙没用"是不成立的——**三情景对比才是论点**。）

---

## 2. 2.45 M m³ 借沙上限：**已核实到页**

**来源**（我已下载原文并逐页检索）：

> Coastal Science & Engineering. *Shoreline Erosion Assessment & Plan for Beach Restoration — Rodanthe & Buxton (NC)*. Report **[2403-PHASE1-FR]**, November 2013.
> **Executive Summary, p. ix**（PDF 第 11 页），小节 *"Sediment Quality and Potential Borrow Areas"*。

**原文**：

> "The areas defined by 8 cores at Rodanthe are 120–165 acres with potential sand reserves totaling **3.2 million cubic yards in the upper 7 ft of substrate**. … The area defined by 5 cores off Buxton is 320 acres with potential sand resources totaling 3.6 million cubic yards in the upper 7 ft of substrate."

**换算**：3.2 × 10⁶ cy × 0.7646 m³/cy = **2.447 × 10⁶ m³ ≈ 2.45 M m³**。

### ⚠ 必须改的一处引用
v4 的 **[5] 是 2023 年的 Needs Assessment（Summary Report 2577）**，**它不支持 2.45 M 这个数**。请把沙源上限指向 **2013 那份报告**（[2403-PHASE1-FR], p. ix），2023 那份可以保留用于别的引用。
数据主表原先写的"p.~10"是近似值；**实际是 p. ix**。

---

## 3. 保护时长分位数：部分现成，其余 1 分钟可算

| 需要什么 | 在哪 | 状态 |
|---|---|---|
| $T^b_{\rm first,fail}$ 中位（KM 删失） | `mc_comparison.csv: T_first_b_KM_p50` | ✅ 现成 |
| $T^w_{\rm safe,cum}$ / $T^b_{\rm safe,cum}$ 的 **P10/P50/P90** | `MC_<情景>_<策略>/runs.csv` 的列直接分位 | ✅ 现成可算（未预计算） |

**我已算好 `once` 策略的**：

| 情景 | $T^w_{\rm safe,cum}$ P10 / P50 / P90（yr） |
|---|---|
| S1 | 13.56 / 14.30 / 14.33 |
| S3 | 6.15 / 8.21 / 9.81 |

> 若要全部 12 组（3 情景 × 4 策略），让编程手跑 3 行 pandas 即可，**不需要重跑模型**。

## 4. 0.8 可用率结果：**存在**

`results/release_20261113_r2/DIAG_availability08_repeat/`
（确定性单跑，`repeat` 策略，`resolved_config.yaml` 里 `a_borrow: 0.8`；含 `results.json`、`ledger.csv`、`events.csv`、`meta.json`）

## 5. S3 末期耗尽统计：**存在**

`results/release_20261113_r2/MC_S3_once/runs.csv` 的 `exhausted_frac` 列（1000 行）：

- **P50 = 0.425**，P90 = 0.660，**mean = 0.444**（S1 的 mean = 0.000）

---

## 6. v4 的两处必改（

| # | 问题 | 改法 |
|---|---|---|
| **A（必须）** | **页眉总页数还是 23**：p24 写 `Page 24 of 23`、p25 写 `Page 25 of 23` | 全篇改成 **`of 25`**（或按官方政策把 AI 报告移出 25 页后写 `of 24`，但**推荐 25**，与"整份材料 ≤25 页"的更严口径一致） |
| **B（建议）** | 表 3 的 `OBS` 行没有引用标记（$\rho_{\rm obs}$、$c_1$） | 表下加一行小注：*"OBS entries: ρ_obs from [1,5]; c_1 from [5]; USGS transect rates in the Q3 holdout from [2]."* |

> **页数余量警告**：现在是 **25/25**，零余量。加 B 的一行如果溢出到 26 页，就从 §1 引言删一句冗余的话——**不要动数字与限制说明**。

## 7. 已复核通过的（v4）

| 项 | 结果 |
|---|---|
| 守恒式符号 | ✅ 已改成 $+\int[R_c(t)-R_c(0)]$，与 `accounting.py` 一致 |
| AI 行内披露 | ✅ §1 末尾已有 "During preparation, OpenAI Codex assisted with…"，`[6][7]` 在参考文献 |
| 参考文献质量 | ✅ [1] Flynn 完整、[2] Hapke & Henderson OFR 2015-1002 带 DOI |
| 字号 | ✅ 正文 12.0 pt（46 106/48 000+ 字符） |
| 页数 | ✅ 25 ≤ 25（但见 §6 的零余量警告） |
