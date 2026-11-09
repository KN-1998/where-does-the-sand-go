# where-does-the-sand-go — U 盘交接包

> 备份时间：2026-11-09（Round 5 资料库扩充后刷新）
> 基准仓库：https://github.com/KN-1998/where-does-the-sand-go
> 本地工作副本：`D:\where-does-the-sand-go`
> 当前提交：见 `git/COMMIT.txt`（本次备份的 HEAD；Round 5 完成）

---

## 1. 这个包里有什么

```
where-does-the-sand-go_handoff/
├─ README_交接说明.md          ← 本文件
├─ docs/                        ← 工作副本的完整文档（不含 .git）
│   ├─ 00_README_索引.md        ← 先看这个
│   ├─ modeling/                ← MODEL_SPEC / NONDIM / DECISIONS / params / 审查
│   ├─ handoff/                 ← CODER_SPEC（给编程手）/ WRITER_NOTES（给论文手）
│   ├─ ledger/claims.csv        ← 90 条数字台账（66 OBS / 16 ASSUME / 8 MODEL）
│   ├─ 资料/                    ← 数据主表、7 份摘录、USGS 岸线说明
│   │   └─ 06_原始摘录/         ← _pdf（5 份全文）、_txt（提取文本）、_gis（USGS 岸线）
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

## 3. 当前状态（截至 2026-11-09）

| 项 | 状态 |
|---|---|
| 题目拆解 | ✅ `modeling/CHECKLIST.md` |
| 主模型 | ✅ v0.3 双状态（V 活跃剖面 + O 近岸沙坝），D1 已签 |
| 决策 | ✅ D1–D7 已签；**D8 等 D7 的 $c_0^*$** |
| 参数 | ✅ `modeling/params.yaml`（YAML 可解析，全部带单位/区间/来源） |
| 台账 | ✅ **90 行**（66 OBS / 8 MODEL / 16 ASSUME） |
| 解析基准 | ✅ 原型 `modeling/sanity/erf_prototype.py`，$T_p=6.15/7.33/7.36$ yr |
| 独立验证集 | ✅ USGS 14 条岸线（1978–2002）已存入 `docs/资料/06_原始摘录/_gis/` |
| 求解器 | ⛔ 未实现（编程手任务） |
| 论文 | ⛔ 未开始（论文手可先写 §1–§3） |

## 4. 必须建模手拍板的事（按急迫度）

| # | 事 | 影响 | agent 的建议 |
|---|---|---|---|
| **Q-33** | D7 预算约束不绑定：$C_{\max}=120$M、$V_{\max}=2.5$M、$c_0=8$M 时 $N=1,3$ 都买满，$c_0^*$ 无定义 | **阻塞 E4/Q5** | 改 $C_{\max}=60$M（标 ASSUME），敏感性 40–120M |
| **Q-38** | $c_0$ 证据区间是 0.5–4M（2026 Buxton/Avon 反推），8M 偏高 | E4 的 $c_0$ 扫描 | 扫描范围改 $[0,10]$M，8M 作上界 |
| **Q-39** | `slr_base` 4.55 → NOAA 现行 **4.88**（1978–2023） | 基线/情景起点 | 改 4.88，4.55 作敏感性 |
| **Q-34** | S2 的 `forced_dy=25` 是潜在还是实际后退 | S2 情景强度 | 论文写明"25 是 potential"，或对该事件关闭饱和 |
| **Q-35** | $H=10$ vs Buxton 9.3 | 所有绝对米数 | **证据已加强（Nags Head 反推 9.5），建议结项：保留 10** |
| **Q-36** | CERC 更正后 $D=3\times10^5$ 在下沿，$T_p$ 偏乐观 8–12% | 绝对值 | 保留 3e5 主算，论文并列 4.1e5 / 8e5 |
| **Q-37** | $\rho_e$ 与显式风暴可能双计数（约 +0.35 m/yr） | 基线速率 | 口径 (i) 并在 Q3 做 L0 核对 |

## 5. 编程手从哪开始

1. 读 `docs/handoff/CODER_SPEC.md`（实现契约、接口、验收测试）。
2. 按 **C-D4**：先 `zeroflux` 跑 T1（收支闭合）与 T3（零源项），再切 `open` 复验 T1。
3. 风暴按 §2.4b 的**对数正态 $\Delta y_{\rm pot}$**，不要用 `0.5H` 截断。
4. **E4 等 Q-33**；E0–E3、E5–E7 与 T1–T8 不受影响；T9 用 USGS 岸线做独立验证。

## 6. 论文手从哪开始

1. 读 `docs/handoff/WRITER_NOTES.md`：论证线、公式、图表规格、参数表。
2. 先写 §1 引言、§2 假设、§3 模型（不依赖结果）；结果章节用 `\todo{}` 占位。
3. 每个数字必须能在 `docs/ledger/claims.csv` 溯源；标签（OBS/MODEL/ASSUME）不能删。
4. 三句可直接用的话见 `docs/资料/00_数据主表.md` §J。

## 7. 核对与完整性

- 文档/参数/台账一致性已过：YAML 可解析、台账 10 列、全仓无控制字符、Markdown 表格无截断。
- 原型可复算：`python docs/modeling/sanity/erf_prototype.py`（<2 s）。
- 若 U 盘文件与 `docs/` 不一致，以 git bundle 恢复出的 HEAD（见 `git/COMMIT.txt`）为准。
