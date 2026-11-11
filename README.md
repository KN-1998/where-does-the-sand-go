# 2027 MCM-Style Mock Problem A — *Where Does the Sand Go?*

> 海岸演化与补沙策略（beach nourishment）建模工作区。
> Outer Banks · Rodanthe 附近 5 km 走廊 · 2027–2042。
> **这是独立训练/练习赛题（PDF 标注 TRAINING / PRACTICE），不是已核实的正式 COMAP 题目。**

> **排期 / 节点 DDL / 降级方案：见 [`SCHEDULE.md`](SCHEDULE.md)（2026-11-11 重排）。**

本仓库是一支三人队 + 建模助理 agent 的**协作工作区**，而不是一份成品论文。
它把"模型 → 参数 → 情景 → 策略 → 交接口径"拆成互相锁定的文档与台账，
让建模手、编程手、论文手可以并行推进而不各说各话。

---

## 题目一句话

> 什么时候补沙**真的**保护了一段正在变化的岸线，什么时候海洋只是把问题搬到了别处？

题目末尾的 *Important distinctions* 基本就是评分点：长期趋势 ≠ 风暴预报；岸线位置 ≠ 滩宽 ≠ 沙量；
风暴后存在恢复；区域海平面 ≠ 局地后退；**观测 / 模型 / 假设干预三者必须分开标注**。

---

## 仓库结构

```
.
├── README.md                      ← 本文件（仓库入口）
├── PROGRESS.md                    ← 进度台账（每轮开场必读）
├── OPEN_QUESTIONS.md              ← 待建模手拍板 / 待他人回答的问题
│
├── meta/                          ← 【项目元数据】计划、审查、打包
│   ├── planning/
│   │   ├── AGENT_BRIEF_MODELER.md ← 建模助理行为边界与阶段门禁
│   │   ├── MASTER_PLAN_MCM2027A.md ← 全局统筹：权责、时间线、里程碑
│   │   └── 建议.txt                ← 外部建议（原始输入，不改动）
│   ├── reviews/
│   │   ├── REVIEW.md              ← 红队审查（逐条 Pass/Partial/Fail）
│   │   └── REVIEW_RESPONSE.md     ← 对独立审查报告的逐条处置
│   └── packaging/
│       └── README_交接包.md       ← U 盘/zip 交接包的打包说明
│
├── problem/                       ← 原始题面 PDF（只读）
├── modeling/                      ← 【建模手 + agent】全部建模文档
│   ├── CHECKLIST.md               ← 题面逐句可检查条目（阶段 0 门禁）
│   ├── MODEL_SPEC.md              ← 状态变量 / 控制方程 / 假设 / 边界条件
│   ├── NONDIM.md                  ← 无量纲化 + erf 解析基准 + 保护期公式
│   ├── DECISIONS.md               ← D1–D8 决策日志（选项 / 权衡 / 推荐 / 状态）
│   ├── params.yaml                ← 参数登记（符号 / 单位 / 取值 / 依据 / 是否标定）
│   ├── PARAM_EVIDENCE.md          ← 每个参数的出处与可辨识性评估
│   ├── VALIDATION_PLAN.md         ← 标定 / 验证划分、指标、敏感性与可辨识性
│   ├── SCENARIOS_STRATEGIES.md    ← 情景设计 + 策略设计 + 状态触发规则
│   └── sanity/                    ← 参考原型（≤150 行，仅自检，非成品）
│       ├── erf_prototype.py       ← erf 解对拍、保护期闭式解、投放宽度扫描
│       └── results.txt            ← 上述脚本的可复算输出
│
├── handoff/                       ← 【交接包】给编程手与论文手的契约文档
│   ├── README_交接说明.md          ← 交接包说明：给谁、怎么用、边界在哪
│   ├── CODER_SPEC.md              ← → 编程手（离散 / IO / 验收 / 实验）
│   └── WRITER_NOTES.md            ← → 论文手（论证线 / 公式 / 图表规格）
│
├── 资料/                          ← 【资料库】真实数据 + 原始 PDF + 提取文本（只读）
│   └── 00_数据主表.md             ← 每个数字的出处（先看这个）
├── ledger/claims.csv              ← 声明台账：每个数字的来源类型与出处
├── data/raw/                      ← 原始数据（只读，附 SOURCES.md）
└── data/processed/                ← 清洗后数据
```

> 文中路径除特别说明外均**相对仓库根目录**。`资料/`、`problem/`、`data/raw/` 是只读区，整理时不得改动。

需要编程手交付的 `src/`、`tests/`、`experiments/`、`figures/`，以及论文手的 `report/`、`letter/`，
按 `meta/planning/MASTER_PLAN_MCM2027A.md` 第 2 节的约定在对应阶段新建。

---

## 克隆后你拿不到什么（**先看这条**）

公开仓库**不含**以下被 `.gitignore` 排除的大体积资产，`git clone` 后对应目录是空的：

| 路径 | 内容 | 体积 |
|---|---|---|
| `资料/06_原始摘录/_pdf/` | 6 份政府/学术 PDF 全文（DEQ 2011/2019、USGS PP1827、USGS OFR 2015-1154、NCBIWA 等） | ~123 MB |
| `资料/06_原始摘录/_txt/` | 上述 PDF 的文本提取（可 grep） | ~0.4 MB |
| `资料/06_原始摘录/_gis/` | USGS OFR 2015-1002 的 14 条历史岸线 shapefile | ~1.4 MB |

**结论不依赖这些文件本体**：所有引用过的数字都已在 `资料/00_数据主表.md` 与 `ledger/claims.csv` 里带 URL/页码记录，照表可复核；需要原件时按 `资料/06_原始摘录/README.md` 的复现命令重新下载。

---

## 四条铁律

1. **数字进论文前必须先进 `ledger/claims.csv`。** 没有台账的数字 = 编的。
2. **每条数据标来源类型**：`OBS`（观测，附 URL 与访问日期）/ `MODEL`（模型导出）/ `ASSUME`（假设，必须写理由与范围）。
3. **量纲纪律**：岸线位置 `y` [m]、滩宽 `w` [m]、沙量 `V` [m³/m] 不可互换；
   换算必须显式写出 `H = h_* + B` 这个中间量（取 `H = 10 m` 时，岸线每前进 1 m ⟺ 每米岸线 10 m³ 沙）。
4. **门禁不过不进下一阶段**：M2（求解器收支闭合与收敛测试）未通过前，不跑 Q2 之后的实验、不写结果结论。

---

## 快速开始

参考原型只依赖 NumPy：

```bash
cd modeling/sanity
python erf_prototype.py > results.txt     # 约 1 秒
```

它做四件事：校验 erf 解析解推导、对拍保护期闭式解与数值解、给编程手一组对照数值、
扫描投放宽度 `ℓ` 观察沙量效率。**成品求解器不在这里**，由编程手按交接口径实现。

---

## 已能用的三个结论（解析/设计层面，非完整模型结果）

1. **补沙寿命 $\propto \ell^2/D$**：$T_{1/2}=0.2748\,\ell^2/D$；1 km 投放、$D=3\times10^5$ m²/yr 时约 0.92 yr。
2. **匀铺可行性阈值** $\mathcal{V}_{\text{thr}}=HL\,(w_{\text{mgmt}}-w_{\min})$；低于它，匀铺不能使全段立即达标（不代表定点方案一定可行，更不是"唯一"）。
3. **即使没有单次固定成本，时机仍改变风险**；不预设"一次大补"或"多次小补"恒优，报告扫描区间的实际排序（见 `modeling/DECISIONS.md` D7）。

---

## 当前状态（2026-11-10）

- 阶段 0–4 文档已出：`CHECKLIST.md`、`MODEL_SPEC.md`、`NONDIM.md`、`DECISIONS.md`、`params.yaml`、
  `PARAM_EVIDENCE.md`、`VALIDATION_PLAN.md`、`SCENARIOS_STRATEGIES.md`、`meta/reviews/REVIEW.md`
- **交接包已完成**：`handoff/CODER_SPEC.md`（→ 编程手）、`handoff/WRITER_NOTES.md`（→ 论文手）、
  `handoff/README_交接说明.md`（交接包说明）
- `DECISIONS.md` 中 **D1–D18 全部已定**（D1–D8 于 2026-11-09/10；D9–D14 由建模手 2026-11-10 落笔；D15–D18 为执行口径，2026-11-11）；**D8 按 A5 改写后不再依赖 $c_0^*$**（主算 `all_in` 下无 $c_0^*$）；未定项按"推荐项"推进并标注依赖（见 `OPEN_QUESTIONS.md`）
- ✅ 已通过：erf 解析基准与原型一致；守恒有限体积的质量守恒到机器精度（1e-16）；匀铺可行性判据有闭式解
- ⛔ 未通过：M2（求解器尚未实现，收支闭合与收敛测试未跑）；台账 **103 行（69 OBS / 9 MODEL / 25 ASSUME）**，其中 2 条 `need-manual-check`、20 条仅搜索摘要、1 条二手转引（S4）
- 红队第 1 轮（口径已修）：**3 Pass（文档层）/ 12 Partial / 0 Fail** —— **"Pass"必须由数值结果支撑，现在拿不到**（见 `meta/reviews/REVIEW.md`）
- Round 3 审计（2026-11-09）：修复 `params.yaml` YAML 解析失败、$w_{crit}$ 与 $d_b$ 不一致、$w_0$ 场、风暴上限、`open` 边界等
- **Round 6（2026-11-09，响应独立审查）**：修正风险几何、负滩宽、原型避免风险、V/O 定义、5/9 km 账本、ghost、$V_{\max}$ 语义；Q-33 已定位为 $V_{\max}=2.5$M（5 年量）误标 15 年，改为 5.0M 后预算自然绑定；新增 Q-40–Q-44。详见 `meta/reviews/REVIEW_RESPONSE.md`
- **Round 7（2026-11-10，第二轮独立审查）**：MODEL_SPEC 定为唯一合同；`Δy≤w_eff`；$V_{15}/V_{event}/S_{borrow}$ 三约束；all-in 成本主算；风暴足迹 `phi_k`；`events.csv` 字段
- **Round 8（2026-11-10，第三轮独立审查）**：耗尽态改为**不冻结**；`risk_w/risk_b` 分开；补沙源/时滞/运输参数；成本模型开关；事件推进伪代码 + T10；$V=V_0+Hy$、$Q=\tilde Q_0-DV_x$；SLR 标为情景端点；台账 103 行

---

## 下一步

1. 建模手签 **Q-40（主风险口径）/ Q-44（本地 LRR）/ D8（触发规则）**；其余见 `OPEN_QUESTIONS.md`。
2. 编程手按 `handoff/CODER_SPEC.md` 实现求解器：先 BE + 零通量 + T1/T3，再加风暴/沙库/开边界，最后过 T1–T10。
3. 论文手按 `handoff/WRITER_NOTES.md` 搭骨架；**完整模型跑通前只写方法与假设，不写结果结论**。

进度以 `PROGRESS.md` 为准。

---

## 协作约定

- **分支**：`modeling` / `code` / `paper` 各一条，建模手负责合并到 `main`
- **提交信息**：`[角色] 做了什么`，例如 `[code] 通过沙量收支测试`
- **只读区**：`problem/`、`data/raw/` 不修改；原始输入文件保持原样
- 大体积原始数据（岸线、潮位、波浪浮标）建议走 Git LFS 或在 `data/raw/SOURCES.md` 里记录下载方式，不要直接塞进 git

---

## 授权与用途

这是一个**独立数学建模训练/练习赛**工作区：题面正文标注 `TRAINING` / `PRACTICE`，PDF 标题为 *2027 MCM-Style Mock Problem A*，作者字段为 *Independent Mathematical Modeling Training Materials*。**不要把它写成已核实的正式 COMAP 题目，也不要声称题面归 MCM/COMAP 所有**。仓库现为公开仓库，内容可用于学习与讨论；文中引用的公开数据与文献版权归各自发布方，见 `ledger/claims.csv` 中的 `source_url`。
