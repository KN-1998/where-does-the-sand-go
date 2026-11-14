# RECONCILE_2026-11-14 — 与编程侧回执的对账

> 来源：`论文现成数据与出处交接包_20261114.zip` + `给论文手和建模手的回执.md`（18.99 MB，编程侧）。
> 我做了三件事：**验数据**、**认错**、**改文档**。

---

## 1. 数据核对：全部对上（我从仓库原始 JSON 复算）

从 `results/release_20261113_r2/S1_uniform/results.json → sand_attribution` 直接读出的七项：

| 分项 | 值（m³） | 与回执 |
|---|---:|---|
| `beach_original_footprint` | 1 274 971.064 | — |
| `beach_buffers` | 955 664.762 | — |
| `nearshore_reservoir` | 169.235 | — |
| **库存小计** | **2 230 805.061** | ✅ 一致 |
| `boundary_net_outflow` | 33 999.382 | ✅ 一致 |
| `permanent_offshore_loss` | 56 484.235 | ✅ 一致 |
| `avoided_current_deficit` | 128 711.322 | ✅ 一致 |
| **合计** | **2 450 000.000** | ✅ 闭合 |
| `closure_m3` | −3.26e−09 | ✅ 机器精度 |

**七项相加 = 2 450 000.000000**，与投放量逐位相同。回执给的"四项闭合表"也成立（库存合并为一项）。
`method` 字段写明 "paired intervention minus baseline; counterfactual effects, not tagged grains" —— 与回执的警告一致。

---

## 2. 我错的两处（已认，已改）

### 2.1 ❌ 我说"repeat 的滩宽暴露最差" —— **错**

S3 的 $E_w$ 中位（越小越好）：

| 策略 | $E_w$ |
|---|---:|
| once | 33 948（最好） |
| adaptive | 49 882 |
| **repeat** | **52 219（第 3）** |
| targeted | 60 780 |
| none | 70 144（最差） |

**repeat 不是最差，targeted 才是。** 论文原句是"relative to once-only placement"，是**相对比较**；我在 `CONTENT_REVIEW_v5.md` 里写成了绝对最差，属于我读错。

> 正确的说法：*"repeat 与 once 在两个目标上的相对排序冲突"*，不能扩成"repeat 在所有策略里滩宽最差"。

### 2.2 ❌ 我建议的"$V_{\rm thr}$ 贡献句" —— **过度解读**

我曾在 `CONTENT_REVIEW_v5.md` §2.3 建议写 "nourishment is worth repeating only while the placed volume stays above $V_{\rm thr}$"。
回执指出：$\mathcal V_{\rm thr}=HL(w_{\rm mgmt}-w_{\min})$ 只回答"**均匀铺沙能否让全走廊立刻达标**"这个几何问题，**没有**证明重复补沙是否值得、更没证明最优性。

**接受。** 该句不得采用。正确的用法只有一句："当 $\mathcal V<\mathcal V_{\rm thr}$ 时，单次匀铺无法让全段同时达标，因而必须集中投放"——这是几何判断，不是经济判断。

---

## 3. 我建议里另外两处需要修正

### 3.1 表 3 的 OBS 来源注（我给的映射错了）

我建议 "ρ_obs from [1,5]; c_1 from [5]" —— **不成立**：
- [1] 是 Flynn 2023（S-Curves 岸线），不是 DEQ 段平均速率；
- [5] 是 CSE **2023** Needs Assessment，而 1.7 与 2.45 M 的原始依据在 CSE **2013**（另一份报告）；
- $c_1=27$ USD/m³ 目前标 `ASSUME` 是**谨慎且正确**的，不该为了"填引用"硬改成 OBS。

**正确写法**（三种来源各归各）：
> "OBS entries: $\rho_{\rm obs}$ is the NC DEQ segment-average rate [DEQ 2011]; the 2.45 M m³ design cap is converted from the potential offshore reserves reported by CSE (2013, p. ix; body p. 92) [CSE2013]; $c_1=27$ USD/m³ is an `ASSUME` planning value for recent Dare County projects and is not an observed unit price."

### 3.2 AI 报告里的 "powered by GPT-5" —— 不可证

回执指出：现有记录无法证明"本任务使用 GPT-5 这个具体型号"。
**接受**：改成 "OpenAI Codex"，型号留给真实使用记录；同时删掉 AI 报告里"借用沙原始出处未解决"的过时例子（现在已经解决了）。

---

## 4. 借沙出处的正式题录（采用回执版本）

> Coastal Science & Engineering, with CZR Incorporated. *Feasibility Report: Shoreline Erosion Assessment and Plan for Beach Restoration, Rodanthe and Buxton Areas, Dare County, North Carolina*. Prepared for Dare County Board of Commissioners. Report **2403-PHASE1-FR**, November 2013.

**页码双重可核**（我已用包内原文 PDF 复验）：
- **印刷 p. ix（PDF 第 11 页）**：审阅者易查的执行摘要；
- **印刷 p. 92（PDF 第 114 页）**：正文原句 *"areas comprise 120–320 acres with potential sand reserves of 3.2 million cubic yards off…"*。

换算：3.2 × 10⁶ cy × 0.764554858 = **2 446 575.55 m³ ≈ 2.45 M m³**（设计值）。

⚠ 两条必须保留的限制（回执强调，我同意）：
1. 这是**潜在储量**，报告本身要求进一步钻孔取样才能满足许可 —— **不是已许可、可交付的供沙**；
2. **0.8 可用率是另行设定的假设情景**，不是观测。

---

## 5. 现有统计的正确引用位置（回执给了，我记下）

| 量 | 文件 | 口径 |
|---|---|---|
| 保护时长分位 | `MC_<情景>_<策略>/summary.json` 的 `kaplan_meier.b/w` 与 `quantiles.T_safe_cum_b/w` | 首失从 2027 起算；KM 分位空值=15 年内不可识别，**不能填 15** |
| 0.8 可用率 | `DIAG_availability08_repeat/results.json` | **单条确定性诊断**（S2/repeat/seed42，投放 1.96 M，成本 52.92 M，$E_b=997.0$、$E_w=59\,783.7$），**没有 0.8 的 MC 与全策略排名** |
| S3 末期耗尽 | `MC_S3_*/runs.csv: exhausted_frac` | 100 / 32.8 / 0 / 96.8 / 61.9 %，与论文一致 |

---

## 6. 版本对不上的地方（需要确认）

回执说"对象为当前 `2701(6).pdf`"，并说**参考文献实际已有 7 条**。
但我手上最新的是 `2701(5).pdf`（**25 页、14 条文献**）。两者不是同一个文件。

**请把 `2701(6).pdf` 发我**，否则我无法判断：
- 它是否已经删掉目录（25 页）？
- 文献是 7 条还是 14 条（若是 7 条，说明退回到了更早的版本）？
- 回执列的"p.13 The The 重复"等**必改项**是否已在 (6) 里修掉？

---

## 7. 我接下来做的

1. 在 `CONTENT_REVIEW_v5.md` 追加**修订声明**（撤回"滩宽最差"与"$V_{\rm thr}$ 贡献句"两条建议）；
2. 在 `FIX_v7.md` 修正表 3 的引用映射（改成 §3.1 的三源写法）；
3. 拿到 `2701(6).pdf` 后跑终检（页数/页眉/两句关键词/表 3 注/URL/60 个数/字号）。
