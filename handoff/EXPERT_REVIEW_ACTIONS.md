# EXPERT_REVIEW_ACTIONS — 专家意见处置（2026-11-14 22:40）

> 来源：`各专家的审阅.doc`（两位独立审阅，已转 PDF 提取全文）。
> 结论：**两位都给了正面总评，没有发现编造或"论文≠代码"的硬伤**；必须处理的集中在**交付合规**与**三处口径/措辞**。
> 剩余 **25 h**（内部硬停 11/15 18:00）。

---

## 0. 一页总表

| # | 事项 | 谁 | 工时 | 优先级 |
|---|---|---|---|---|
| 1 | v6 回到 25 页（删目录） | 论文手 | 10 min | **P0** |
| 2 | 页眉改 `of 25`；AI 报告页单列；队号替换 `Training Team` | 论文手 | 10 min | **P0** |
| 3 | L0 口径改成"一致性检查"，删掉"接近无偏"式措辞 | 论文手 | 10 min | **P0** |
| 4 | "预算从未绑定"收窄，并补一句外部沙源边界 | 论文手 | 10 min | **P0** |
| 5 | §8 统一"配对均值 + 95% CI" | 论文手 | 5 min | **P0** |
| 6 | 参考文献补到 8–10 条 | 论文手 | 15 min | P1 |
| 7 | S1 同成本同方量、E_w 重尾机制、audit 口径、D=8e5 结果 | 论文手 | 15 min | P1 |
| 8 | 打包 bug（03_contract / 08_ledger 是文件不是目录） | 我 | ✅ 已修 | — |
| 9 | v6 出来后重跑 DATA_AUDIT（对 v5/v6 而非 v1） | 我 | 30 min | P0 |
| 10 | 可选：feasible-first 100 配对 / 真实 transect 场敏感性 / 外部沙源 MC | 编程手 | 1–2 h | P2 |

---

## 1. P0-1 v6 回到 25 页

两位都指出 26 页是**硬性违规**。方案见 `FIX_v6.md`：**直接删目录**（题目并未要求，`contents` 在题面出现 0 次）；若坚持保留则压成一级标题且不另起页。
AI 报告标题改 `\section*{}` 移出目录。

## 2. P0-2 页眉

现在全篇 `Page X of 26` + 占位符 `Training Team`。

- 前 25 页：`Page X of 25`；
- 第 26 页（AI 报告）：可保留连续编号，但**分母用 25 会矛盾**——建议该页页眉写 `Report on Use of AI Tools (not counted in the 25-page limit)`；
- **队号**：题目规定培训期不需控制号。若本次已有队号则替换；没有就保留 `Training Team`，并在答辩/说明中口头确认。

## 3. P0-3 【专家二最重要的一条】L0 口径不能当验证

专家指出：caliber 诊断里"实测场均值 2.3136"**就是我们自己注入的 $\rho_0$ 场的走廊平均**，所以"偏差仅 +2.0%"是恒等式的算术结果，证明的是"代码没错"，**不是"模型能预测岸线"**。

**必须在 §6.2 加一句**（原文照抄）：

> "The L0 magnitude check compares the simulated retreat with the mean of the rate field that was **injected** as input; it is a consistency check on the implementation, not an independent validation."

同时检查**摘要与结论**里有没有"close to unbiased / near-unbiased"这类会给评委造成"已验证"错觉的措辞——有就删，改成 "the calibration target is matched to within the arithmetic contribution of the explicit storms"。

## 4. P0-4 "预算从未绑定"是设置的必然，不是发现

专家算得很准：本地沙 2.45 M × 27 = 66.15 M < 120 M，所以**所有 MC 里预算结构性不绑定**。

**但我查了外部沙源的诊断跑**，这一块**不是空白**：

| 配置 | 投放 | 说明 |
|---|---|---|
| `DIAG_local_all_in_once` | 2 450 000 | 沙源绑定（27 USD/m³） |
| `DIAG_external_all_in_once` | 2 900 000 | 外调 30 USD/m³，未触预算 |
| **`DIAG_external_all_in_repeat`** | **4 000 000** | **120 M / 30 = 4.0 M —— 预算在这里绑定了** |

**建议改法**（比补 MC 便宜得多，且已有数据）：
在 Q5 加一句并引用这三个 run：
> "The binding constraint is configuration-dependent: with local sand the supply cap binds (2.45 M m³, 66.15 M USD), whereas with external sand at 30 USD/m³ the budget binds at 4.0 M m³ (= 120 M USD). Our Monte Carlo comparison is therefore restricted to **local-supply** configurations; the external case is reported as deterministic diagnostics."

这样既诚实、又主动把边界说清，还顺手把外调情景变成"已覆盖"。

## 5. P0-5 §8 中位 vs 均值

未关闭。统一为**配对均值 + 95% CI**（`policy_pairwise.csv` 已有：S3 repeat $\Delta E_b=-2{,}693$ [−2,813, −2,573]；$\Delta E_w=+17{,}339$）。

## 6. P1 四条低成本加强

| 项 | 改法 |
|---|---|
| 参考文献 5 → 8–10 | Dean (1991)；Larson & Kraus (1989) 或 Kriebel & Dean (1993)；Ashton & Murray (2006)；Komar (1998)；USACE *Coastal Engineering Manual* (2002) |
| S1 同成本 | 加一句："In S1 all fixed-calendar policies place the same volume at the same cost, so the comparison is purely about exposure." |
| E_w 重尾 | 用我们已有的发现："uniform 的中位最低但 P90 最高（3,125 m·yr），因为整段同时抬升意味着极端风暴下整段同时失守；热点集中保留了未动用的岸段作为缓冲。" |
| audit 口径 | 加一句脚注："1.93e−8 为确定性跑的最大残差，2.11e−8 为 18 000 次 MC 的最大值。" |
| D=8e5 | 确认 §6 报出 $D=8\times10^5$ 的短 $T_p$ 结果（SPEC 要求报告上界情形） |

## 7. 我对专家"待确认"的回答

| 专家问 | 答 |
|---|---|
| P0-1/P0-2 是否已进 v5？ | **是**。v5 里 A6 已写"1.7 是输入场均值、生产跑按情景缩放"；表 1 是 "Current unresolved … recoverable"；§4.4 有 "Only the descriptive diagnostic Dmax … is monotone"；式 (18) 是 $+\int[R_c(t)-R_c(0)]$。**六项逐字核过。** |
| feasible-first 100 配对做了吗？ | **没做**。目前只有单案例诊断（`policy_rule_diagnostic.json`）。已在可选清单 #10。 |
| 真实 transect 场敏感性？ | **没做**。USGS 数据已补回（E14 已复现），但没跑 S2 的 transect 场。已在 #10。 |
| 外部沙源 MC？ | 只有确定性诊断（见 §4 表），没有 MC。 |

## 8. 打包修复（专家一发现，我的错）

`03_contract`、`08_ledger` 原本被写成了**无扩展名的单个文件**，其中 `08_ledger` 还把 `claims.csv` 覆盖丢了。已修：

```
03_contract/CODER_SPEC.md
08_ledger/claims.csv  +  08_ledger/00_数据主表.md
```

并给 `MANIFEST.md` 加了跨平台说明（`batch_design.json` 内部是 Windows 反斜杠，属生成端产物，不影响数值）。新包：**148 文件 / 3.69 MB**。
