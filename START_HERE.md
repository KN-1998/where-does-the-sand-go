# START_HERE.md — 编程手从这里开始（2026-11-11 23:20）

> **目标：今晚先让"能跑的东西"跑起来，不是写完整求解器。**
> 60 分钟的验收 = 三条测试绿 + 一个 E0 基线产物目录。做完再谈别的。
>
> 你现在什么都不用问。合同已冻结（D1–D18）、自检 63 项全绿、参考实现 190 行可运行。
> 遇到文档矛盾按 `handoff/CODER_SPEC.md` §0.6 自裁（**守恒 > 可执行 > 保守**）。

---

## 0. 先跑 30 秒，确认环境和口径

```bash
python modeling/sanity/discrete_contract.py
```

期望最后一行 `===== ALL PASS =====`，退出码 0。它已经跑通：
`T3a`（零源项）、`T3c`（O 衰减）、`T11`（y 不截断 / V 不越界）、`T1`（5 组闭合）、
`T13`（侵蚀 5 年再补回 5 年）、投放守恒、风暴足迹峰值归一化。

**这就是你要复刻的最小口径。** 看不懂哪一行，去看 `CODER_SPEC` 对应小节（表在下面）。

---

## 1. 开分支（10 秒）

```bash
git checkout -b code
```

`main` 只由建模手合并，你只在 `code` 上提交。

---

## 2. 建骨架（照抄）

```bash
mkdir -p src/sim src/exp tests configs results figures
touch src/__init__.py src/sim/__init__.py src/exp/__init__.py
```

四个文件先写，别的都不要写：

| 文件 | 内容 | 对应参考实现 |
|---|---|---|
| `src/sim/grid.py` | `thomas()` + `step()` | `discrete_contract.py` 的同名函数 |
| `src/sim/model.py` | `run()`（含 V 下限、R_c、台账） | 同上 |
| `src/sim/io.py` | 读 `params.yaml` + 覆盖 `configs/base.yaml` | 新增，~40 行 |
| `tests/test_mass.py` | 把参考实现的 `chk(...)` 改成 `assert` | 直接搬 |

> **先搬后改**：`cp modeling/sanity/discrete_contract.py src/sim/_ref.py`，拆完再删。
> 不要从零重写——重写会把已经踩平的三个坑（y 截断、R_c 峰值、360 格）再踩一遍。

---

## 3. 三条断言必须先绿（40 分钟）

```bash
python -m pytest -q tests/test_mass.py
```

| 测试 | 判据 | 参考实测 |
|---|---|---|
| `test_t1_closure` | `max residual_rel < 1e-6` | $1.1\times10^{-13}$ |
| `test_t3_zero_source` | `max|Δy| < 1e-12` 且 `O(t)=O0·e^{-(k+λ)t}` | $2.8\times10^{-15}$ |
| `test_t13_refill` | 侵蚀 5 年→补 1.5e7 m³→再跑 5 年，残差 $<10^{-10}$ | $1.4\times10^{-13}$ |

**三条全绿之前，不要开始 E0。**

---

## 4. 跑第一次 E0（10 分钟）

```bash
python -m exp.run_one --config configs/base.yaml --strategy none --out results/E0_local
```

`configs/base.yaml` 已经给你了（S1、5 年、zeroflux、dx=25）。跑完必须产出：

```
results/E0_local/
├── results.json     # 至少含 meta/initial/duration/mass
├── fields.npz       # y[nt,nx], O, w, x, t
├── ledger.csv       # 每行有 residual_rel
└── meta.json        # seed + params md5 + git sha
```

**判据**：`ledger.csv` 的 `residual_rel` 最大值 < 1e-6；`results.json` 里 `w_end_min` 不是 0 也不是 NaN。

---

## 5. 报工（一行，别写报告）

在 `PROGRESS.md` 的 `## 编程手提问` 段追加一行：

```
23:5X | N1 完成：T1/T3/T13 绿，E0 产出 | residual=1.1e-13 | 下一节点 N2
```

---

## 6. 卡住了怎么办

| 情况 | 动作 |
|---|---|
| 文档两处说法冲突 | 按 §0.6 自裁（守恒 > 可执行 > 保守），记 `[自决]` 一行，**不要停** |
| 数值对不上参考实现 | 先打印 `H`、`nx*dx`、`V_min.max()` 三个数——80% 的错在这 |
| 真的做不下去 | 提问段写一行 + 阻塞等级，建模手 2 h 内回；超时按 §0.4 取保守继续 |
| 时间不够 | 按 `SCHEDULE.md` §5 砍单，**不许改 DDL** |

---

## 7. 现在**不要**做的事

- ❌ 不要先写"漂亮的"抽象层、日志、可视化；
- ❌ 不要直接上 E4 策略比较（没有冻结模型，结论无意义）；
- ❌ 不要改 `params.yaml` 的数值（那是建模手的）；
- ❌ 不要动 `modeling/` 与 `handoff/`（只读）。

---

**下一步**：做完 §3 的三条断言就回来报一行。其余按 `SCHEDULE.md` 的 N2–N6 推进。
