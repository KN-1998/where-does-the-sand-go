# COMPLIANCE_CHECK — 2027 MCM 提交规范核对（2026-11-14 17:35）

> 依据：队伍转发的 6 条要求 + 官方 `Contest_AI_Policy.pdf`（v102025，我已下载到 `dist/ai_policy.pdf` 并逐条读）。
> 对象：`2701(2).pdf`（v3，23 页）。**方法：逐页量字号、逐条找引用、逐页取页眉。**

---

## 0. 结论

| # | 要求 | 现状 | 判决 |
|---|---|---|---|
| 1 | 25 页含全部内容 | **23 页**（摘要 p1 + 正文 + 参考文献 + 技术信 p22 + AI 报告 p23） | ✅ |
| 2 | AI 使用规范 | 末尾有 `Report on Use of AI`，写明工具、用途、边界、责任 | ✅ 但**正文缺行内引用**（见 §2） |
| 3 | 外部来源须脚注/尾注/文内注释 + 参考文献 | 7 条参考文献，正文均有引用 | 🟡 **表 3 的 OBS 行未挂引用**（见 §3） |
| 4 | PDF、英文、**字号 ≥12 pt**、≤25 页 | 正文 **12.0 pt**（占 42 500/45 292 字符） | ✅ |
| 5 | 报告内说明 AI（哪个模型、何用途）+ 行内引用 + 参考文献 + 附《AI 使用报告》 | 附录完整；[6][7] 在参考文献里 | 🟡 **正文未提到 AI**（见 §2） |
| 6 | 每页页眉含队号与页码 | 每页均有 `Training Team` + `Page N of 23` | ✅（培训期免队号） |

**总判：可以交，但有 2 处必须在冻结前补（都是文本层面的小改）。**

---

## 1. 字号实测（要求 4）

| 字号 | 字符数 | 是什么 |
|---|---|---|
| **12.0 pt** | 42 500 | **正文**（99 %+） |
| 14.3 / 17.2 pt | 944 | 标题 |
| **8.0 pt** | 483 | **数学下标/上标**（如 $w_b$、$\rho_{\rm obs}$、$10^{-8}$） |
| 4.3–6.0 pt | 803 | **图内的坐标刻度**（MATLAB 导出的位图，非排版文字） |

- 正文 12 pt ✅；
- 上下标 8 pt 是 TeX 的正常缩放（任何论文都如此），**不构成违规**；
- 图内刻度是位图，不受"字号"约束（但建议 ≥8 pt 以免打印不清）。

> 若担心自动检查：把正文基准调到 **12.5 pt**，页数会增约 0.5 页（23 → 24），仍在 25 内。**非必要**。

## 2. 【必改】正文缺 AI 使用的行内引用（要求 2 + 5）

**现状**：`[6]`、`[7]` 只出现在**参考文献**（p21）与**附录**（p23），**正文 22 页里一次都没有**。
**官方原文**：*"Clearly indicate the use of AI tools … **in their report** … Please use **inline citations** and the reference section."*

**改法**：在 §1 引言末尾（或 §10 结论之后）加一段，约 3 行：

> "All numerical results in this report were produced by team-written code included in the submission archive. A generative AI assistant (OpenAI Codex; see the appended *Report on Use of AI Tools*) [6, 7] was used only for language editing, repository consistency checks, and figure formatting. It did not select the model, write the solver, choose scenarios, or generate any numerical result, literature citation, or field observation."

> 注意：官方明确 **Report on Use of AI Tools 不计入 25 页**。我们把它放在第 23 页（计入 23 页内）也合规——**但更稳妥的做法是把它移到 25 页之外**：正文 22 页 + 附录 1 页，页眉页码仍连续。

## 3. 【建议改】表 3 的 OBS 行补来源（要求 3）

表 3 里 `ρobs 1.7`、`c1 27 USD/m³` 标了 `OBS`，但行内没有 `[n]`。要求 3 是"任何外部信息来源都要用脚注/尾注/文内注释记录"。

**改法**：表下加一行小注：

> "OBS entries: $\rho_{\rm obs}$ from [1, 5]; $c_1$ from [5]; the USGS transect rates used in the Q3 holdout are from [2]."

（表格注用 9–10 pt 即可，通常不受正文 12 pt 约束；若要绝对安全，用 12 pt。）

## 4. 页眉核对（要求 6）

实测每页顶部：

```
Training Team
Page 6 of 23
```

- 格式："团队标识 + 页码/总页数" ✅；
- 培训期不写控制编号 ✅（队伍已明确）；
- **正式赛**时把 `Training Team` 换成 `Team # <控制号>` 即可，页码分母随之变成实际总页数。

## 5. 25 页的边界（要求 1 与官方政策的细微差别）

| 文件 | 说法 |
|---|---|
| 队伍转发第 1 条 | 25 页适用于**整个提交材料**（含附录、代码） |
| 官方 AI 政策 | *"Report on Use of AI Tools … has no page limit and will **not** be counted as part of the 25-page solution"* |

**处理**：按更严的那个来 —— 目前 23 页（含 AI 报告）同时满足两者 ✅。**不要**因为"AI 报告不计页"就往正文加内容。

## 6. 现在要做的三件事（按优先级）

| # | 事 | 谁 | 工时 |
|---|---|---|---|
| 1 | 正文加 AI 行内引用段（§2 的英文，可直接粘） | 论文手 | 5 min |
| 2 | 表 3 下加来源小注 | 论文手 | 3 min |
| 3 | （可选）把 AI 报告移出 25 页、页码仍连续 | 论文手 | 10 min |

改完导出 v4，我再跑一遍本文件（字号/页眉/引用/页数四项自动量）。

---

## 7. 附：本核对是怎么做的（可复现）

```python
# 字号分布
for pg in doc:
    for b in pg.get_text("dict")["blocks"]:
        for l in b.get("lines", []):
            for s in l["spans"]:
                counter[round(s["size"],1)] += len(s["text"].strip())
# 页眉
doc[i].get_text().split("\n")[:2]
# 引用覆盖
{ n: len(re.findall(r"\[%d\]"%n, body)) for n in range(1,8) }
```
