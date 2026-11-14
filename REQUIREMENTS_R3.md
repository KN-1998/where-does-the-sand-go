# REQUIREMENTS_R3 — 编程手补跑要求（2026-11-14 11:40）

> 下发：编程手（主）。抄送：论文手（§4 是他要配合的两处）。
> **优先级：任务 A（15 min）> 任务 B（30 min）> 其余可选。**
> 剩余 30 h。这两项做完，论文就可以冻结。

---

## 0. 为什么要有这份文件

论文 v2 §4.3 写了一句：

> *"the simulated storm contribution over 15 years is about **0.14 m/yr**, or **1.6 %** relative to the corridor mean"*

这两个数来自 **R1 的 `results/L0/summary.json`**（`realised_storm_contribution = 0.1436`、`bias_vs_field = 0.0159`），**不在 R2 发布包里**。
而论文 §6.2.4 声明"所有数值来自 `results/release_20261113_r2`，不与 R1 混用"——**自相矛盾，审稿人会抓**。

两条出路：**要么在 R2 下把它重算出来（任务 B），要么让论文删掉这两个精确值（§4 的回退文案）**。我们优先做前者。

---

## 1. 任务 A（必须，15 min）：轻量结果入库 + 修门禁路径

### 现象
干净 clone 上运行 `python tools/check_release.py` 直接失败：

```
FileNotFoundError: results\release_20261113\batch_design.json
```

两个问题：
1. `results/release_20261113_r2/` **不在 git 里**（只在 Release 附件）；
2. `check_release.py` 里写死的目录名是 `release_20261113`，与实际的 `release_20261113_r2` **不一致**。

### 要求
1. 从 `review_handoff_20261113_r2.zip` 中把 `results/release_20261113_r2/` 的**轻量部分**提交进仓库：
   - **要**：所有 `*.csv`、`*.json`、`*.md`、`*.log`；`figures/*.png|pdf`；
   - **不要**：`fields.npz`、`fields.mat`、`*.bin`、任何 >2 MB 的二进制。
2. 修 `tools/check_release.py` 的目录名（`release_20261113` → `release_20261113_r2`），或改为从 `CODE_VERSION.json` 读。
3. 修完必须能在干净 clone 上跑通：
   ```powershell
   python tools/check_release.py
   ```
   退出码 0。

### 验收
我在干净 clone 上跑同一条命令，退出码 0，且 `git ls-files results/release_20261113_r2 | wc -l` > 50。

---

## 2. 任务 B（必须，30 min）：在 R2 下补跑「口径核对」

### 目标
拿到 R2 版本的三个数，替换论文 §4.3 的 0.14 m/yr / 1.6%：
1. **无风暴**的走廊平均后退（m/yr）；
2. **有风暴**的走廊平均后退（m/yr）；
3. 两者之差，以及相对走廊场均值 2.3136 m/yr 的相对偏差。

### 陷阱一：`configs/no_storm.yaml` 不能直接用
它的注释写着 *"disable event shocks while **retaining the scenario's computed chronic component (target rate minus expected storm contribution)**"* —— 它会**补偿**慢性速率，使"风暴贡献"恒为 0。
任务 B 要的是**除风暴过程外完全相同的两跑**，不是速率匹配的对照。

### 陷阱二：任何带 `scenario:` 的配置都会做缩放
`model.py` 里 `scale = (target − ρ_storm) / ρ_e_corridor_mean`，S1 的 scale=0.649、S2=1.068。若 A 组不缩放、B 组用 S1，两跑就不可比。

### 正确做法：新增一个「诊断场景 L0」

**要的物理过程**（实现方式你定，这里只说要求）：

| 要求 | 说明 |
|---|---|
| 平稳泊松 | $\lambda_s=0.4$ yr⁻¹，**不随时间变化** |
| 无强制事件 | **不能**用 S2（它在 $t=2.25$ 有强制 25 m 事件），也不能用 S3（时变） |
| 对数正态 | 中位 8 m、$\sigma_{\ln}=0.6927$、P95=25 m |
| $\rho_e$ 不缩放 | 场 $=1.7\,[1+1.2\exp(-x^2/2\sigma_w^2)]$，走廊均值 2.3136 |
| 开关 | 只靠 `storm_enabled` 切换 A/B |

**推荐实现**（改动最小，两处）：
1. `modeling/params.yaml` 的 `scenarios:` 下新增
   ```yaml
   L0_diag: {lambda_s: 0.4, dy_ref: 8.0, rho_e: 2.3136}   # 诊断：平稳风暴，不缩放
   ```
2. `src/sim/model.py`：
   ```python
   # ① ρ_e 场：L0_diag 直接返回未缩放的 base 场
   if self.scenario == "L0_diag":
       return self.rho_base
   # ② 事件：让 L0_diag 走 S1 的平稳泊松分支（无强制事件）
   #    generate_events 里把 "L0_diag" 并入 {"S1","S2"} 的那个分支即可
   ```

> 若你更愿意用 `scale_override=1.0` 之类的参数，也可以——只要满足上表五条，且 A/B 的 `resolved_config.yaml` 除 `storm_enabled` 外**逐字相同**。

### 实验定义（照抄）

| 项 | 值 |
|---|---|
| scenario | `L0_diag` |
| 边界 / 网格 / 时长 | `open`；9 km 域、360 格、dx=25；15 yr |
| 补沙 | 无（`--strategy none`） |
| A 组 | `storm_enabled: false` |
| B 组 | `storm_enabled: true` |
| 样本 | 确定性 `seed=42` 各 1 次；MC 各 ≥200（能 1000 更好） |

### 命令

```powershell
python -m exp.run_one --config configs/caliber_A.yaml --strategy none --seed 42 --out results/caliber_R2/A_det
python -m exp.run_one --config configs/caliber_B.yaml --strategy none --seed 42 --out results/caliber_R2/B_det
python -m exp.mc     --config configs/caliber_A.yaml --strategy none --n 1000 --seed 42 --out results/caliber_R2/A_mc
python -m exp.mc     --config configs/caliber_B.yaml --strategy none --n 1000 --seed 42 --out results/caliber_R2/B_mc
```

```yaml
# configs/caliber_A.yaml            # configs/caliber_B.yaml 与之逐字相同，只改最后一行
inherit: configs/base.yaml
scenario: L0_diag
bc: open
t_end: 15.0
storm_enabled: false                # B 组为 true
```


### 输出（字段固定，我会按字段核）

`results/caliber_R2/summary.json`：

```json
{
  "git_commit": "...", "source_sha256": "5ff6da62...",
  "field_mean_rho": 2.3136,
  "A_nostorm": {"n": 1000, "retreat_mean": 0.000, "MCSE": 0.000, "CI95": [0.0, 0.0]},
  "B_storm":   {"n": 1000, "retreat_mean": 0.000, "MCSE": 0.000, "CI95": [0.0, 0.0]},
  "realised_storm_contribution": 0.000,
  "bias_vs_field": 0.000,
  "residual_rel_max": 0.000e0
}
```

外加 `results/caliber_R2/README.md`：一行说清 A/B 唯一差别、为何不用 `no_storm.yaml`。

### 验收（我逐条核）

1. 两组 `residual_rel_max < 1e-6`；
2. `A.retreat_mean` 明显低于 `B.retreat_mean`（否则说明补偿逻辑没关掉 → 任务失败）；
3. 贡献与偏差由**同一批 MC 的配对差**算出，不是两个独立均值相减；
4. `source_sha256` 与 `CODE_VERSION.json` 一致；
5. `A_det` 与 `B_det` 的 `resolved_config.yaml` 只差 `storm_enabled`（我会 diff 这两个文件）。

### 如果跑不通
**不要硬凑数。** 回一句"任务 B 不可用 + 原因"，论文按 §4 的回退文案删掉精确值，10 分钟改完。

---


## 3. 可选（有时间才做，按此顺序）

| # | 事项 | 工时 | 交付 |
|---|---|---|---|
| C | 三布置（uniform/multi/hotspot）的 $E_w$ **P10/P90**，供论文加误差条 | 10 min | `results/release_20261113_r2/layout_quantiles.csv` |
| D | 替代规则对照：先过滤 $T_{10}\ge3$ 再排序，100 配对种子 | ≤30 min | 附录一条 sensitivity |
| E | `python tools/verify_handoff.py dist/...zip` 复核冻结源码 SHA256 | 5 min | 一行回执 |

---

## 4. 论文手需要配合的两处

### P2 文案（二选一，取决于任务 B 的结果）

**若任务 B 成功**（拿到 R2 的 `realised_storm_contribution` 与 `bias_vs_field`）：
> 把 §4.3 的 *"about 0.14 m/yr, or 1.6 % relative to the corridor mean"* 换成 R2 的新值，并加一句 *"computed from the paired no-storm / with-storm ensemble in `results/caliber_R2/`"*。

**若任务 B 不可用**（回退，立即改）：
> 把该句改成：
> *"The realised bias is much smaller than this bound because the narrow-beach cap and dry-beach exhaustion suppress later events, so the explicit storm contribution is a modest fraction of the chronic sink throughout most of the fifteen-year horizon."*
> ——**删掉 0.14 与 1.6 % 两个精确值**，其余不动。

### P3 表号

§5.1 的布置对比表没有表号，其余三张都是 "Table N:"。二选一：
- **推荐**：把三个数写成正文行内三联数（"3.05 / 18.64 / 38.59 m·yr"），删掉那张无号表 —— 最省事，且不影响论证；
- 或补 "Table 3" 并把后续表顺延为 4、5（同时改正文引用）。

---

## 5. 交付方式与截止

| 任务 | 截止 | 回执 |
|---|---|---|
| A | **11/14 14:00** | 一条命令 + 退出码 |
| B | **11/14 15:00** | `results/caliber_R2/summary.json` + 一行结论 |
| C/D/E | 11/14 18:00（可选） | 文件路径 |

回执统一写进 `PROGRESS.md` 的 `## 编程手提问` 段，格式：
```
14:05 | 任务 A 完成：check_release 退出码 0，release_20261113_r2 已入库 312 文件 | —
15:02 | 任务 B 完成：A=2.207、B=2.350、贡献=0.1436、偏差=+1.6% | 见 summary.json
```

我收到后 30 分钟内复核并更新 `STATUS_BOARD.md`。
