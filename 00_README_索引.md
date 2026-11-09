# 2027 MCM Problem A · 建模组工作区索引

> 本目录 = 建模手 + 建模助理 agent 的全部建模材料。
> 原始输入已归档：题面 PDF 移入 `problem/`，其余保留在根目录并统一为下划线命名；**不要修改它们的内容**。
> 仓库入口见 `README.md`；目录之外的空白占位由 `data/`、`handoff/` 承担。

## 目录结构

```
D:\数学建模acm\
├── README.md                    ← 仓库入口（GitHub 首页）
├── 00_README_索引.md            ← 你正在读的文件
├── .gitignore / .gitattributes  ← 仓库卫生（缓存、LaTeX 中间产物、换行符）
│
├── problem/
│   └── 2027_MCM_A_...pdf        ← 原始题面（只读输入）
├── AGENT_BRIEF_MODELER.md       ← 原始 brief（只读输入）
├── 建议.txt                      ← 原始建议（只读输入）
├── MASTER_PLAN_MCM2027A.md      ← 原始总控（只读输入）
│
├── modeling/                    ← 【建模手+agent】全部建模文档
│   ├── CHECKLIST.md             ← 题面逐句可检查条目（阶段 0 门禁）
│   ├── MODEL_SPEC.md            ← 状态变量 / 控制方程 / 假设 / 边界与初值
│   ├── NONDIM.md                ← 无量纲化 + 解析基准（erf 解、保护期公式）
│   ├── DECISIONS.md             ← D1–D8 决策日志（选项 / 权衡 / 推荐 / 状态）
│   ├── params.yaml              ← 参数登记（符号 / 单位 / 取值 / 依据 / 是否标定）
│   ├── PARAM_EVIDENCE.md        ← 每个参数的出处与可辨识性评估
│   ├── VALIDATION_PLAN.md       ← 标定/验证划分、指标、敏感性方案
│   ├── SCENARIOS_STRATEGIES.md  ← 情景设计 + 策略设计 + 触发规则
│   ├── REVIEW.md                ← 红队审查（15 条逐条 Pass/Fail + 证据）〔待补〕
│   └── sanity/                  ← 参考原型（≤150 行/个，仅用于自检，非成品）
│
├── handoff/                     ← 【★ 交接文档，独立成包】〔待补〕
│   ├── README_交接说明.md        ← 交接包说明：给谁、怎么用、边界在哪
│   ├── CODER_SPEC.md            ← → 编程手（方程离散 / IO 接口 / 验收测试 / 实验清单）
│   └── WRITER_NOTES.md          ← → 论文手（论证线 / 公式 / 图表规格 / 评分点映射）
│
├── ledger/
│   └── claims.csv               ← 声明台账：每个数字的来源类型（OBS/MODEL/ASSUME）
│
└── data/
    ├── raw/                     ← 原始数据（只读，不改动）
    └── processed/               ← 清洗后数据（编程手维护，附 SOURCES.md）

根目录另需（尚未创建）：PROGRESS.md（进度台账，每轮开场必读）、OPEN_QUESTIONS.md（待拍板问题）。
```


## 铁律（打印出来贴在屏幕上）

1. **数字进论文前必须先在 `ledger/claims.csv` 里**。没有台账的数字 = 编的。
2. **`ASSUME` 必须写理由和范围**，不许只写"假设"两个字。
3. **观测 / 模型 / 假设干预**三类必须在每张图、每张表上分开标注。
4. **y（岸线位置）、w（滩宽）、V（沙量）不可互换**，换算必须写出 `h_* + B` 这个中间量。
5. 门禁不过不进下一阶段（M2 求解器未验收，不跑 Q2 之后的实验）。

## 当前状态

截至 2026-11-09：阶段 0–3 文档已出（`CHECKLIST.md` / `MODEL_SPEC.md` / `NONDIM.md` /
`params.yaml` / `PARAM_EVIDENCE.md` / `VALIDATION_PLAN.md` / `SCENARIOS_STRATEGIES.md`），
`erf_prototype.py` 与 `sanity/results.txt` 可复算通过。

待办：`DECISIONS.md` 中 D1–D8 待建模手拍板；`handoff/`（CODER_SPEC / WRITER_NOTES）与
`REVIEW.md` 待补；`PROGRESS.md`、`OPEN_QUESTIONS.md` 尚未创建。进度以 `README.md` 的"当前状态"节为准。
