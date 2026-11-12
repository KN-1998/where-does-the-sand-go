# 结果审计报告（R1，2026-11-13）

> 审计对象：`results/` 下全部 106 个 `results.json`、8 个 `mc_summary.json`、8 个 `fields.npz`、
> E1/E4/E7 专项文件、F1–F8 图、验收日志。
> 生成命令：`python -m exp.audit`（机器可读：[`AUDIT.json`](AUDIT.json)）；一键门禁：
> `python -m exp.check_all`（日志：[`check_all.log`](check_all.log)）。

## 1. 总结

| 项 | 结果 |
|---|---|
| 审计检查数 | **2268** |
| 失败 | **0** |
| 最大台账相对残差（全库 106 run） | $1.9\times10^{-7}$（合同 $<10^{-6}$） |
| 验收测试 | **17 passed**（[`pytest.log`](pytest.log)） |
| 合同自检 | **67/67** |
| CLI 可复现（同 seed 两次） | `results.json` md5 相同；`fields.npz` md5 相同 |

## 2. 具体检查项

| 类别 | 检查内容 | 结果 |
|---|---|---|
| schema | `meta/initial/duration/exposure/mass/cost/state` 七键齐全 | ✅ |
| 删失 | `(value is None) == censored`；时长值有限 | ✅ |
| 时长 | `T_safe_cum_w/b ∈ [0,15]` | ✅ |
| 暴露 | `E_w,E_b` 有限且非负 | ✅ |
| 质量 | `residual_rel_max < 1e-6`、`placed ≥ 0`、`cost ≥ 0` | ✅ |
| 台账 | 列齐全、时间单调、$t_0=0$、逐行 `residual_rel`、`placed` 对账 | ✅ |
| 闭合重算 | `placed − (V+O+flux_out+offshore+chronic)` 与台账 `residual` 一致 | ✅ |
| $R_c$ | `D_max_cum ≥ R_c_cum`；两列都存在 | ✅ |
| 场文件 | `fields.npz` 含 `y/O/w/exhausted/x/t`；形状一致；`exhausted` 为 bool | ✅ |
| MC | `n` 与行数一致、分位存在且单调、KM 删失比例 ∈[0,1] | ✅ |
| E1 | 三布置齐全；沙去向三项之和 = 投放量（$<10^{-3}$） | ✅ |
| E4 | c0 扫描 6×4=24 行、四策略齐全、无项目不收 $c_0$ | ✅ |
| E7 | 12×8×2=192 行、保护比例 ∈[0,1] | ✅ |
| 图 | F1–F8 存在、>20 KB、PNG 签名正确 | ✅ |
| 日志 | `pytest.log` 含“17 passed”（兼容 UTF-8/UTF-16） | ✅ |

## 3. 独立复核（不依赖审计脚本）

### 3.1 台账手算（`results/E0_local`，5 yr，S1，zeroflux）

```
rows = 252，t_end = 5.0
placed = 0
V_domain = -620516.7921954514
O_domain = 5877.373976979553
offshore = 17822.962249315766
chronic  = 596816.4559691336
重算残差 = placed - (V+O+offshore+chronic) = 2.246815711259842e-08
台账残差 = 2.246815711259842e-08   ← 完全一致
```

> 相对残差的绝对值 $2.2\times10^{-8}$ m³ 是 750 步浮点累加的下限；投放量 $10^6$ 的 run 上
> 相对残差为 $10^{-14}$ 量级。T1 的门槛 $10^{-6}$ 仍有 45× 余量。

### 3.2 CLI 复现性（S2，seed=7，5 yr，两次独立进程）

| 文件 | 第 1 次 md5 | 第 2 次 md5 |
|---|---|---|
| `results.json` | `D89CED31B03D40AC7EAEFBDA51ED6CD6` | 同左 |
| `fields.npz` | `F76B122CE0F2EBDC34276A8C52C5381C` | 同左 |

### 3.3 仓库卫生

- `git diff main -- modeling handoff ledger 资料 problem data/raw configs/base.yaml` **为空**（只读区未动）；
- 入库最大文件 230 KB（图 PNG）；台账/场文件按 `.gitignore` 不入库（约 45 MB，留在磁盘）；
- 代码中无本机绝对路径（仅 `REPRODUCE.md` 记录本机解释器路径）。

## 4. 审计的边界（不要把它当成物理正确性证明）

- 审计检查的是**自洽性**（schema、闭合、形状、文件存在），不是物理正确性；
- 物理正确性由 T1–T13 的**构造性测试**（erf 解、解析保护期、恢复比、边界已知外流）保证；
- T9（历史岸线）与 L0 的“观测对照”属于**跨资料一致性检查**，不是独立验证；
- 审计不会发现“口径选错”这类问题——那类问题见 [`feedback/TO_MODELER.md`](../../feedback/TO_MODELER.md)。

## 5. 复跑

```powershell
python -m exp.audit            # 只跑结果层
python -m exp.check_all        # 原型 + 17 测试 + 67 合同 + 2268 审计
```
