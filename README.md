# 2027 MCM/ICM · Problem A — *Where Does the Sand Go?*

> 海岸演化与补沙策略（beach nourishment）建模工作区。
> Outer Banks · Rodanthe 附近 5 km 走廊 · 2027–2042。

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
├── 00_README_索引.md               ← 工作区目录索引与铁律
├── AGENT_BRIEF_MODELER.md         ← 建模助理的行为边界与阶段门禁
├── MASTER_PLAN_MCM2027A.md        ← 全局统筹：权责、时间线、里程碑、风险
├── 建议.txt                        ← 外部建议（原始输入，不改动）
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
├── 资料/                          ← 【资料库】真实数据 + 原始 PDF + 提取文本
│   └── 00_数据主表.md             ← 每个数字的出处（先看这个）
├── handoff/                       ← 【交接包】给编程手与论文手的契约文档
├── ledger/claims.csv              ← 声明台账：每个数字的来源类型与出处
├── data/raw/                      ← 原始数据（只读，附 SOURCES.md）
└── data/processed/                ← 清洗后数据
```

需要编程手交付的 `src/`、`tests/`、`experiments/`、`figures/`，以及论文手的 `report/`、`letter/`，
按 `MASTER_PLAN_MCM2027A.md` 第 2 节的约定在对应阶段新建。

---

## 三条铁律

1. **数字进论文前必须先进 `ledger/claims.csv`。** 没有台账的数字 = 编的。
2. **每条数据标来源类型**：`OBS`（观测，附 URL 与访问日期）/ `MODEL`（模型导出）/ `ASSUME`（假设，必须写理由与范围）。
3. **量纲纪律**：岸线位置 `y` [m]、滩宽 `w` [m]、沙量 `V` [m³/m] 不可互换；
   换算必须显式写出 `H = h_* + B` 这个中间量（取 `H = 10 m` 时，岸线每前进 1 m ⟺ 每米岸线 10 m³ 沙）。

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

## 当前状态（2026-11-09）

- 阶段 0–4 文档已出：`CHECKLIST.md`、`MODEL_SPEC.md`、`NONDIM.md`、`DECISIONS.md`、`params.yaml`、
  `PARAM_EVIDENCE.md`、`VALIDATION_PLAN.md`、`SCENARIOS_STRATEGIES.md`、`REVIEW.md`
- **交接包已完成**：`handoff/CODER_SPEC.md`（→ 编程手）、`handoff/WRITER_NOTES.md`（→ 论文手）、
  `handoff/README_交接说明.md`（交接包说明）
- `DECISIONS.md` 中 **D1–D7 已签**（2026-11-09）；**D8 依赖 D7 的 $c_0^*$，尚未签**；未定项按"推荐项"推进并标注依赖（见 `OPEN_QUESTIONS.md`）
- ✅ 已通过：erf 解析基准与原型一致；沙量恒等式与质量守恒（原型实测 1e-8）；匀铺可行性判据有闭式解
- ⛔ 未通过：M2（求解器尚未实现，收支闭合与收敛测试未跑）；台账 **74 行（51 OBS / 7 MODEL / 16 ASSUME）**，其中 2 条 `need-manual-check`、20 条仅搜索摘要待开原文
- 红队第 1 轮（口径已修）：**3 Pass（文档层）/ 12 Partial / 0 Fail** —— **"Pass"必须由数值结果支撑，现在拿不到**（见 `modeling/REVIEW.md`）
- Round 3 审计（2026-11-09）：修复 `params.yaml` YAML 解析失败、$w_{crit}$ 与 $d_b$ 不一致、$w_0$ 场、风暴上限、`open` 边界等；**新发现 D7 预算约束不绑定**（见 `OPEN_QUESTIONS.md` Q-33），E4 前必须裁决

---

## 协作约定

- **分支**：`modeling` / `code` / `paper` 各一条，建模手负责合并到 `main`
- **提交信息**：`[角色] 做了什么`，例如 `[code] 通过沙量收支测试`
- **只读区**：`problem/`、`data/raw/` 不修改；原始输入文件保持原样
- 大体积原始数据（岸线、潮位、波浪浮标）建议走 Git LFS 或在 `data/raw/SOURCES.md` 里记录下载方式，不要直接塞进 git

---

## 授权与用途

练习赛工作区，内容仅供队内协作。原始题面归 MCM/COMAP 所有；
文中引用的公开数据与文献版权归各自发布方，见 `ledger/claims.csv` 中的 `source_url`。
