# where-does-the-sand-go — U 盘交接包

> 备份时间：2026-11-10（Round 8 第三轮审查整改后刷新）
> 基准仓库：https://github.com/KN-1998/where-does-the-sand-go
> 本地工作副本：`D:\where-does-the-sand-go`
> 当前提交：见 `git/COMMIT.txt`（构建时 HEAD）

---

## 1. 这个包里有什么

```
where-does-the-sand-go_handoff/
├─ README_交接说明.md          ← 包入口（repo 的 handoff/README_交接说明.md 副本）
├─ SHA256SUMS.txt              ← 全包逐文件校验
├─ docs/                        ← 工作副本的完整文档（不含 .git）
│   ├─ README.md                ← 先看这个（仓库总入口）
│   ├─ PROGRESS.md              ← 进度
│   ├─ OPEN_QUESTIONS.md        ← 待决问题
│   ├─ modeling/                ← MODEL_SPEC / NONDIM / DECISIONS / params / 模型文档
│   ├─ handoff/                 ← CODER_SPEC（编程手）/ WRITER_NOTES（论文手）
│   ├─ meta/planning/           ← AGENT_BRIEF / MASTER_PLAN / 建议.txt
│   ├─ meta/reviews/            ← REVIEW / REVIEW_RESPONSE
│   ├─ meta/packaging/          ← 本文件
│   ├─ ledger/claims.csv        ← 103 条数字台账（69 OBS / 25 ASSUME / 9 MODEL）
│   ├─ 资料/                    ← 数据主表、摘录、原始 PDF 与 GIS（只读）
│   └─ problem/                 ← 题目 PDF
└─ git/
    ├─ where-does-the-sand-go.bundle   ← 完整 git 历史（含 main）
    └─ COMMIT.txt                      ← 当前提交与分支
```

## 2. 怎么恢复成可用的 git 仓库

```bash
git clone where-does-the-sand-go.bundle where-does-the-sand-go
cd where-does-the-sand-go
git log --oneline -5        # 顶部应是最新的 [data]/[handoff] 提交
git remote add origin https://github.com/KN-1998/where-does-the-sand-go.git
```

> bundle 是**全量**的（`--all`），不依赖 GitHub 也能完整恢复。
> 若只想看文档，直接读 `docs/`，不需要 git。

## 3. 当前状态（截至 2026-11-10）

| 项 | 状态 |
|---|---|
| 题目拆解 | ✅ `modeling/CHECKLIST.md` |
| 主模型 | ✅ v0.5 双状态（V 活跃剖面（不含 O）+ O 近岸沙坝），D1 已签；耗尽态不冻结 |
| 决策 | ✅ D1–D7 已签；D8 待签（主算成本结构 $c_0=0$，不再依赖 $c_0^*$） |
| 参数 | ✅ `modeling/params.yaml`（YAML 可解析，全部带单位/区间/来源） |
| 台账 | ✅ **103 行**（69 OBS / 9 MODEL / 25 ASSUME） |
| 解析基准 | ✅ 原型 `modeling/sanity/erf_prototype.py`，$T_p=6.15/7.33/7.36$ yr |
| 跨资料一致性数据 | ✅ USGS 14 条岸线（1978–2002）已存入 `docs/资料/06_原始摘录/_gis/`（用于一致性检查，**不是独立验证集**） |
| 求解器 | ⛔ 未实现（编程手任务） |
| 论文 | ⛔ 未开始（论文手可先写 §1–§3） |

## 4. 必须建模手拍板的事（按急迫度）

| # | 事 | 影响 | 状态 / 建议 |
|---|---|---|---|
| **Q-33** | D7 三约束：$V_{15}=5.0$M、$V_{\text{event}}=2.9$M、$S_{\text{borrow}}=2.45$M | E4/Q5 | ✅ 已解决：本地沙主算最紧；外调沙 $N=1$ 2.9M、$N\ge2$ 4.0M；不需要改 $C_{\max}$ |
| **Q-40** | 主风险指标：管理滩宽还是建筑净距 | Q1/Q5 全部口径 | 建议并列；Q5 主指标 $E_b+T_{\text{safe,cum}}^b$（**待建模手签字**） |
| **Q-41** | $V_{\max}$ 语义 | E4 | ✅ 已拆为 $V_{15}$ / $V_{\text{event}}$ |
| **Q-42** | 成本模型 | 策略排序 | ✅ 主算 all-in $c_1=27,c_0=0$；替代结构仅敏感性 |
| **Q-43** | 滩宽耗尽 | 风险指标 | ✅ 不冻结：`w_eff=max(w,0)`，连续过程继续 |
| **Q-44** | 本地 transect LRR（−3.43/−4.58）高于 $\rho_c=2.3$ | 全部时长指标 | 主算保留 2.3，敏感性覆盖 3.5–4.6；**待建模手决定** |
| **Q-34** | S2 `forced_dy=25` | S2 强度 | ✅ 已定义：实际后退 25 m（代码反解潜在值） |
| **Q-35** | $H=10$ vs Buxton 9.3 | 绝对米数 | 证据支持保留 10；待签字 |
| **Q-36** | $D=3\times10^5$ 偏乐观 8–12% | 绝对值 | 保留 3e5 主算，论文并列 4.1e5 / 8e5 |
| **Q-37** | $\rho_e$ 与风暴项可能双计数 | 基线速率 | 口径 (i) + Q3 用 L0 核对；未定 |

## 5. 编程手从哪开始

1. 读 `docs/handoff/CODER_SPEC.md`（实现契约、接口、验收测试）。
2. 按 **C-D4**：先 `zeroflux` 跑 T1（收支闭合）与 T3（零源项），再切 `open` 复验 T1。
3. 风暴按 §2.4b 的**对数正态 $\Delta y_{\rm pot}$**，不要用 `0.5H` 截断。
4. **E4 前先签 Q-40/Q-44**（主风险指标、本地速率）；Q-33/Q-41/Q-42 已按最新口径写入。E0–E3、E5–E7 与 T1–T10 不受影响；T9 优先用现成 `Hatteras_Transects.dbf` 的 LRR 字段。

## 6. 论文手从哪开始

1. 读 `docs/handoff/WRITER_NOTES.md`：论证线、公式、图表规格、参数表。
2. 先写 §1 引言、§2 假设、§3 模型（不依赖结果）；结果章节用 `\todo{}` 占位。
3. 每个数字必须能在 `docs/ledger/claims.csv` 溯源；标签（OBS/MODEL/ASSUME）不能删。
4. 三句可直接用的话见 `docs/资料/00_数据主表.md` §J。

## 7. 核对与完整性

- 文档/参数/台账一致性已过：YAML 可解析、台账 10 列、全仓无控制字符、Markdown 表格无截断。
- 原型可复算：`python docs/modeling/sanity/erf_prototype.py`（<2 s）。
- 若 U 盘文件与 `docs/` 不一致，以 git bundle 恢复出的 HEAD（见 `git/COMMIT.txt`）为准。
