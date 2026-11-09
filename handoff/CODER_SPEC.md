# CODER_SPEC.md — 交给编程手的实现规格（阶段 4 交接）

> **给编程手**：这份文件是合同。你只需要实现它，**不需要**重新决定模型含义。
> 有疑问 → 写进 `OPEN_QUESTIONS.md`，不要自己改模型。有 bug → 修；有规格缺口 → 问。
>
> 配套：`modeling/MODEL_SPEC.md`（方程来源）、`modeling/NONDIM.md`（解析基准与对拍数值）、
> `modeling/params.yaml`（参数）、`modeling/SCENARIOS_STRATEGIES.md`（情景与策略）。
> 版本：v0.3（2026-11-09）。参数以 `params.yaml` 为准，本文中的数值若不一致以 yaml 为准。

---

## 1. 目标与非目标

**要做**：一个一维、双状态（$V,O$）、事件驱动的沙量演化求解器 + 沙量台账 + 批量实验驱动 + 出图。

**不做**（别浪费时间）：
- 不做二维水动力、不做波形爬坡、不做 SBEACH；
- 不做 GUI、不做交互式可视化（只要 matplotlib 出图）；
- 不优化性能到极致——1000 次蒙特卡洛在单机上 < 30 min 即可。

---

## 2. 方程与离散（照抄即可）

### 2.1 连续形式

$$
\frac{\partial y}{\partial t}=-u\frac{\partial y}{\partial x}+D\frac{\partial^2 y}{\partial x^2}+\frac{I-S}{H}+\frac{k\,O}{H}-\rho_e(x)
$$

$$
\frac{\partial O}{\partial t}=S-\left(k+\lambda\right)O
\qquad\text{（}y\text{ 用 m，}O\text{ 用 m}^2\text{=m}^3\text{/m，}S\text{ 用 m}^2\text{/yr）}
$$

> 量纲自检：$kO$ 是 m²/yr，除 $H$ 得 m/yr ✓；$\lambda O$ **不出现在** $y$ 的方程里（它是 $O$ 的永久损失，不是海滩的体积变化）——写成 $(kO-\lambda O)/H$ 是常见错误。

> 实现建议：**主变量用 $y$（m）和 $O$（m²）**；$V=H y+$常数，只在需要报体积时换算。
> 这样 $y$ 的量级（米）与 $O$ 的量级（m²）都可以直接做量纲检查。

### 2.2 空间离散：守恒型有限体积（cell-centered）

- 域 $[-4500,4500]$ m，$\Delta x=25$ m（基准）→ $n_x=360$ 个单元，单元中心 $x_i$。
- 面通量 $F_{i+1/2}$（单位 m²/yr）：
  $$
  F_{i+1/2}=\underbrace{u\,\tilde y_{i+1/2}}_{\text{迎风}}-\underbrace{D\,\frac{y_{i+1}-y_i}{\Delta x}}_{\text{中心差分}}
  $$
  迎风：$u>0$ 取 $y_i$，$u<0$ 取 $y_{i+1}$。
- 更新：$\dfrac{dy_i}{dt}=-\dfrac{F_{i+1/2}-F_{i-1/2}}{\Delta x}+\text{sources}_i$

> ✅ 这样写**天然守恒**：$\sum_i dy_i/dt\cdot\Delta x=-(F_{N}-F_{0})$，边界通量就是唯一的泄漏项。

### 2.3 $O$ 的子步精确解（**别用显式，会不稳**）

令 $a=k+\lambda$。一个时间步 $\Delta t$ 内，先注入风暴沙 $S$（m²，即时），随后

$$
O^{n+1}=\bigl(O^{n}+S\bigr)\,e^{-a\Delta t}
$$

$$
\Bigl[kO\Bigr]_{\text{本步回滩总量}}=\frac{k}{a}\Bigl(O^{n}-O^{n+1}+S\Bigr)
\qquad
\Bigl[\lambda O\Bigr]_{\text{本步永久损失}}=\frac{\lambda}{a}\Bigl(O^{n}-O^{n+1}+S\Bigr)
$$

**守恒校验**：$\Delta O+\Delta V_{\text{rec}}+\text{loss}=S$。这三行是 T1 能过 $10^{-12}$ 的关键，**不要**用 Euler 离散 $O$。

> **为什么是 $(O^n+S)e^{-a\Delta t}$ 而不是"连续注入"式**：§2.4b 规定风暴沙在事件时刻**一次性**注入（$S$ 是总量 m²，不是速率），随后自由衰减。连续注入式 $O^n e^{-a\Delta t}+\frac{S}{\Delta t a}(1-e^{-a\Delta t})$ 会把事件摊到整个 $\Delta t$，与"即时"不符；两者相差约 $a\Delta t/2\approx0.8\%$，虽小但会让 T6 的 0.87 判据漂移。恢复/损失两式对两种写法都成立（都只依赖 $O^n,O^{n+1},S$）。

### 2.4 时间推进

- 基准：**Crank–Nicolson**（时间二阶），三对角求解（`scipy.linalg.solve_banded` 或 `scipy.sparse.linalg.spsolve`）。
- 也可用向后 Euler（一阶，更稳），但 T2 的收敛阶验收要求二阶 ⇒ **建议 CN**。
- $\Delta t=0.02$ yr（基准）。风暴事件时刻必须**落在步边界**：若下一事件在 $t_k$，令本步 $\Delta t=t_k-t$。
- **S3 波候**：`Hs_trend=+3%/decade` 通过 $D\propto H_b^{5/2}$ 进入，$D(t)=D_0(1+0.03t/10)^{5/2}$；在 CFL 与面通量里用**瞬时** $D(t)$。不要只改一个标签而不改 $D$。

### 2.4b 风暴事件的抽样与注入（主算例）

主算例**不**使用 $R_k$ 强度参数化，而是直接抽"宽滩潜在后退"：

1. **到达**：齐次 Poisson，$\lambda_s$ 取 `params.yaml`。
2. **潜在后退**：$\Delta y_{\text{pot}}\sim\mathrm{LogNormal}$，中位 $\Delta y_{\text{ref}}=8$ m，$P_{95}=25$ m ⇒ $\sigma_{\ln}=\ln(25/8)/1.645=0.694$。
3. **窄滩饱和**：$\Delta y_k=\Delta y_{\text{pot}}\,[1-\exp(-w/w_s)]$，$w_s=20$ m。
4. **上限**：$\Delta y_k=\min(\Delta y_k,\;w+\Delta y_{\text{cut}})$，$\Delta y_{\text{cut}}=5$ m。**不得用 $0.5H$**：$H=10$ m 时会把 25 m 事件错误截到 5 m。
5. **注入**：$S_k=H\Delta y_k$ [m²]；$y\leftarrow y-\Delta y_k$；$O\leftarrow O+S_k$。事件时刻按 §2.4 截到步边界。
6. $R_k/\gamma$ 参数化只作敏感性；若使用，需另给 $R_{\text{ref}}$ 分布，当前 `params.yaml` 未给，**不作为主算**。

> `S2` 的 `forced_dy=25` 是**潜在**后退；实际值会被窄滩因子折减（$w=20$ m 时约 0.63 ⇒ 15.8 m）。若情景要的是"实际 25 m"，需把 forced_dy 设为 $25/\text{因子}$ 或对该事件关闭饱和——这是 `OPEN_QUESTIONS` Q-34，待建模手裁定。
>
> **S3 的 SLR**：主通道是 `rho_e_scale(t)`（走廊均值 3.0→5.0）；若启用"风暴基线"第二通道，令 $\Delta y_{\text{ref}}(t)=\Delta y_{\text{ref},0}[1+\beta(S_{\text{SLR}}(t)-S_{\text{SLR},0})]$，$\beta$ 必须作为 ASSUME 写入台账；若不启用，在结果里注明"storm-water-level baseline 未单独建模"。

### 2.5 补沙源项 $I$

瞬时投放：在 $t_s$ 那一步把 $\Delta y=\mathcal{V}/(H\ell_s)$ 加到 $|x-x_c|\le\ell_s/2$ 的单元上（**按单元与投放区重叠长度加权，保证总量精确**）。

> ⚠ 常见 bug：用 `x_c ± l/2` 直接 `np.where` 会把边界单元整格计入，导致总方量误差 1–2%，T1 直接不过。

### 2.6 边界条件（三套，`--bc` 切换）

| 代码 | 实现 |
|---|---|
| `open`（默认） | 两端 ghost cell 用外推 $y_{\text{ghost}}=2y_0-y_1$（面梯度的扩散通量为 0）；**但面通量仍按 $F=u\,y_{\text{upwind}}$ 计算并施加到边界单元**（$u>0$ 时右端流出、左端流入），同时 `flux_left/right += F*dt` 记入台账。**必须真的从边界单元扣/加沙**，否则它不是开边界，T7 会失败 |
| `zeroflux` | **直接把面通量置零**：$F_{\text{boundary}}=0$。仅把 ghost 设成镜像 $y_{\text{ghost}}=y_1$ 只零掉了扩散通量，**没有**零掉对流通量；这是 T7 常见 bug |
| `dirichlet` | $y_{\text{ghost}}=y_{\text{adj}}(t)$，$y_{\text{adj}}$ 由相邻岸段 $\rho_e$ 外推；面通量按上式正常计算 |

> **不要**在面通量里再加 $Q_\infty$：$Q_0$ 的空间梯度已经并入慢性汇 $L_c=\rho_e H$（`MODEL_SPEC` §3.5），再加一次就是双计数。开边界唯一要额外维护的是 `flux_left/right` 台账；T1 的收支式里已经包含它们。
>
> **方向自检**：$u>0$（南向）时，左端是流入、右端是流出；若 `zeroflux` 的留存率**低于** `open`，说明边界通量符号写反（T7 会抓）。

---

## 3. 代码结构（建议）

```
src/
  sim/
    grid.py        # 网格、面通量、三对角求解
    model.py       # 一步推进（split: 扩散/对流/源汇/O子步）
    storms.py      # 泊松到达 + 强度抽样 + 事件注入
    strategies.py  # A/B/C/自适应 四种投放调度
    accounting.py  # 沙量台账（§4）
    io.py          # params 读入、结果落盘
  exp/
    run_one.py     # 单次运行（--scenario --strategy --seed --bc）
    sweep.py       # 参数扫描（OAT / Sobol）
    mc.py          # 蒙特卡洛（多进程）
  viz/
    plots.py       # 全部出图函数（§7）
tests/
  test_mass.py     # T1
  test_erf.py      # T2
  test_zeroforce.py# T3
  test_refine.py   # T4
  test_storm.py    # T6
configs/
  base.yaml  S1.yaml  S2.yaml  S3.yaml
```

**命令行**（必须支持）：
```bash
python -m exp.run_one  --config configs/S2.yaml --strategy A --seed 42 \
                       --bc open --out results/E2_S2_A_s42/
python -m exp.mc       --config configs/S2.yaml --strategy A --n 1000 --jobs 8 \
                       --out results/MC_S2_A/
```

---

## 4. 输入输出接口

### 4.1 输入：`config.yaml`（在 `params.yaml` 基础上覆盖）

```yaml
inherit: params.yaml
scenario: S2                 # S1 | S2 | S3
strategy: A                  # A | B | C | adaptive
bc: open                     # open | zeroflux | dirichlet
seed: 42
t_end: 15.0
dx: 25.0
dt: 0.02
placement:                   # 覆盖默认投放（不填则用 strategy 的默认）
  - {t: 0.0, xc: 0.0, len: 5000.0, volume: 1500000.0}
overrides:                   # 任何 params.yaml 里的键
  rho_e_scale: 1.30         # 走廊均值目标 3.0 / 基线 2.3；乘基线 rho_e(x)，保留热点
  D_diff: 300000.0
```

> **$\rho_e$ 是空间场，不是标量**：情景里只给"走廊均值目标"（如 S2=3.0 m/yr）；实现用 `rho_e_scale = target / 2.3` 乘基线 $\rho_e(x)$，保留热点结构。**不要**用 `rho_e: 3.0` 覆盖整场，否则热点消失、定点投放的对比失真。

### 4.2 输出目录（**每件必备**）

| 文件 | 内容 | 形状/单位 |
|---|---|---|
| `results.json` | 标量结果：$T_p$ 分位、$E$、留存率、成本、参数快照 | — |
| `fields.npz` | `y[nt,nx]` [m]、`O[nt,nx]` [m²]、`w[nt,nx]` [m]、`x[nx]` [m]、`t[nt]` [yr] | float32（体积考虑） |
| `ledger.csv` | 逐时间步的沙量台账（见 §4.3） | — |
| `events.csv` | 每次风暴：$t_k$、$R_k$、$\Delta y_k$、$S_k$ 场汇总 | — |
| `meta.json` | 代码 md5、params md5、Git commit、seed、运行耗时 | — |

### 4.3 `ledger.csv` 列（**沙量台账，T1 的载体**）

```
t, V_inside, O_inside, placed_cum, flux_left_cum, flux_right_cum,
offshore_loss_cum, chronic_loss_cum, residual, residual_rel
```

- `V_inside` = $\sum_i y_i\Delta x\cdot H$（m³）；`O_inside` = $\sum_i O_i\Delta x$（m³）
- **口径（必须固定）**：$y$ 是相对 $t=0$ 岸线的位置，$O(0)=0$，所以"初始总量"$=0$；$V_{\text{inside}}$ 是**增量体积**，不是含 $V_0$ 的绝对体积。若实现里保留 $V_0$，则 `V_inside` 必须同步减去 $\int V_0 dx$，两种写法只能选一种。
- `residual = placed_cum + 0 − (V+O) − flux − offshore − chronic`
- **每行都要写 `residual_rel`**，T1 就是看它的最大值。分母取 $\max(1\ \mathrm{m^3},\ \lvert\text{placed\_cum}\rvert+\lvert\text{初始总量}\rvert)$，避免 $t=0$ 时除零。

**⚠ 关于 chronic_loss**：它会吃掉背景沙。所以**必须同时跑一条"无补沙基线"**，台账里再给一列 `baseline_chronic_loss_cum`，并在 `results.json` 里用**两跑相减**得到"补沙自身的去向"。别把基线侵蚀算到补沙头上。

---

## 5. 验收测试清单（**建模手拥有，你必须全部通过**）

| # | 测试 | 做法 | 判据 | 预期数值 |
|---|---|---|---|---|
| **T1** | 沙量收支闭合 | 任意一次运行，读 `ledger.csv` | $\max\lvert\text{residual\_rel}\rvert<10^{-6}$ | 实测可达 $10^{-12}$ |
| **T2** | 对 erf 解收敛 | $\lambda_s=0,\rho_e=0,u=0$，初始为宽 $\ell$ 的阶跃；$\Delta x=100/50/25$，$\Delta t\propto\Delta x$ | **CN：** L2 误差比 $\in[3.5,4.5]$；**向后 Euler：** $\in[1.8,2.2]$（若用 BE 必须在结果里注明）；且 $dx=50$ 时 $t=1$ yr 相对误差 $<2\times10^{-2}$ | 见下 |
| **T3** | 零源项零通量 | $I=S=0$，零通量边界，$\rho_e=0$ | $y$ 全场变化 $<10^{-12}$ | — |
| **T4** | 网格/时间步一致性 | $dx=50$ vs $25$，同一情景确定性运行 | 关键指标（$T_p$、留存率）差异 $<2\%$ | — |
| **T5** | 无风暴退化 | 配置：$\lambda_s=0$、$\lambda=0$、$u=0$、$\rho_e$ 均匀 2.3、$w_0$ 均匀 18、$w_{crit}=20$；与 NONDIM §7 的解析值对拍 | $T_p$ 相对误差 $<10\%$ | 见 §6 |
| **T6** | 单事件恢复 | 一次 $S_0$，无后续事件 | 最终回滩比例 $\to k/(k+\lambda)=0.87$；$t\to\infty$ 时 $O\to0$ | $0.87\pm0.001$ |
| **T7** | 边界对比 | `zeroflux` vs `open` | 前者留存率**更高**（方向必须对） | 差异应 >0 |
| **T8** | 可复现 | 同一 seed 跑两次 | `results.json` 逐字节相同（或用 `np.allclose`）+ `fields.npz` md5 相同 | — |
| **T9** | **历史岸线独立验证（Q3，不是代码测试）** | 读 `资料/06_原始摘录/_gis/` 的 14 条 USGS 岸线（1978–2002）；以 baseline 布正交 transect，算 Rodanthe 段 LRR；与模型"无补沙基线"对比 | 同一量级：模型基线速率应落在 **1.5–2.8 m/yr**（USGS 全岛 1.5、Flynn 热点 2.26） | 见 `资料/01_岸线侵蚀速率/USGS_岸线数据说明.md` |

### T2 的参考数值（已由原型实测，可直接对拍）

| $\Delta x$ | $L_\infty$ 相对误差 | 质量相对变化 |
|---|---|---|
| 100 m | $4.02\times10^{-2}$ | $4.8\times10^{-8}$ |
| 50 m | $2.05\times10^{-2}$ | $2.8\times10^{-8}$ |
| 25 m | $1.04\times10^{-2}$ | $1.4\times10^{-8}$ |

> 原型用的是显式 FTCS（一阶收敛是因为初始条件不连续）。**上表是 FTCS 的 $L_\infty$ 参考，不是 CN 的目标值**；你的 CN + 有限体积若做对，应为二阶：$\Delta t\propto\Delta x^2$ 时 L2 误差比 ≈4，$\Delta t\propto\Delta x$ 时 ≈2。若得到比值 ≈1，先查时间步是否随 $\Delta x$ 同步细化。

---

## 6. 参考对照数值（无风暴、无对流、单次投放）

参数：$H=10$ m，$D=3\times10^{5}$ m²/yr，$\rho_e=2.3$ m/yr（DEQ 实测推得的走廊等效值），$\mathcal{V}=10^{6}$ m³，$w_0=18$ m，$w_{\text{crit}}=20$ m。

> **这是解析基准配置，不是主算例的初始场**：它用均匀 $w_0=18$ m 和均匀 $\rho_e=2.3$ m/yr；主算例用热点 $w_0(x)$（远场 25、最小 16）和 $\rho_e(x)$（1.7 + 热点放大）。T5 只在这个基准配置下对拍，不能拿主算例的热点场去比。

| 方案 | $\ell$ | $\Delta y_0$ | 中心 $T_p$ | 保护岸线·年 |
|---|---|---|---|---|
| A 匀铺 | 5000 m | 20 m | **6.15 yr** | 26371 m·yr |
| B 热点 | 1000 m | 100 m | **7.33 yr** | 24917 m·yr |
| C 单段 0.5 km（5 段方案的一段） | 500 m | 200 m | **7.36 yr** | 24616 m·yr |

> **C 行只算了一段 0.5 km**，不是整个 5 段方案。5 段的实际总保护岸线·年必须由求解器按实际间距叠加（扩散区会重叠，不能简单乘 5）。`E1` 必须单独跑 5 段方案。

还有两条闭式：
- $T_{1/2}=0.2748\,\ell^2/D$（$\ell$=1000 m ⇒ 0.92 yr）
- 匀铺可行性 $\mathcal{V}_{\text{thr}}=H L(w_{\text{crit}}-w_{\min})$（本例 $2.0\times10^{5}$ m³）

> 这些数字全部可由 `modeling/sanity/erf_prototype.py` 复现（跑一次 < 2 s）。**你的求解器在关掉风暴后必须落在这张表 ±10% 内**，否则先查换算（$H$ 用错是最常见原因）。

---

## 7. 实验清单与出图

### 7.1 必跑实验（对应 `SCENARIOS_STRATEGIES.md` §7）

| 编号 | 命令要点 | 输出 |
|---|---|---|
| E0 | `--scenario S{1,2,3} --strategy none` | 基线 $w(x,t)$、$E_0$ |
| E1 | `--scenario S1 --strategy {A,B,C}` | 三方案对照表 + 沙去向堆叠图 |
| E2 | `--scenario {S1,S2,S3} --strategy A --mc 1000` | $T_p$ 分位、$E$ 分位 |
| E3 | **风暴时机**对照：early（0–5 yr）/ spread（每 2.5 yr）/ late（10–15 yr），各 6 次事件、同一强度分布、seed 固定 | 时机对照表（$T_p$、min $w$、2042 年 $w$） |
| E4 | `--scenario {S1,S2,S3} --strategy {A,B,C,adaptive}`，并对 $c_0\in[0,10]$ M\$ 扫描（Q-38 建议；未批前可按 $[3,15]$ 跑，但必须同时给 $[0,10]$） | 三策略同约束对比 + $c_0^*$ 交叉点 + 成本 |
| E5 | `sweep.py --oat` + `--sobol`；风暴组必须含 `dy_p95=40`（2025 Buxton 观测到 43 m） | tornado 图 + Sobol 图 |
| E6 | `--bc {open,zeroflux,dirichlet}` | 边界敏感性表 |
| E7 | $\mathcal{V}\in[1e5,3e6]$ × $w_{\min}\in[6,22]$ 网格 | 相图（含 $\mathcal{V}_{\text{thr}}$ 线） |

> **CRITICAL（预算约束不绑定）**：当前 $C_{\max}=120$ M USD、$V_{\max}=2.5$ M m³，在 $c_0=8$ M USD 时，$N=1$ 与 $N=3$ 都能买满 $V_{\max}$（$N=1$：$(120-8)/25=4.48>2.5$；$N=3$：$(120-24)/25=3.84>2.5$）。**此时 $c_0^*$ 无定义，E4 是假比较**。跑 E4 前必须选一个：
> (a) 用 5 km 走廊分摊的 $C_{\max}\approx60$ M USD（推荐；5 km 约为 PSDS 5.7 mi 覆盖面的 54%）；
> (b) 把 $V_{\max}$ 提到 CSE 需求之上（例如 4 M m³）；
> (c) 把 $c_0^*$ 重新解释为"时机/风险"权衡，而不是"买沙量"权衡。
> 见 `OPEN_QUESTIONS` Q-33。**不要**在约束不绑定的情况下报告 $c_0^*$。

### 7.2 出图规格（论文手直接用）

| 图 | 内容 | 必须标注 |
|---|---|---|
| F1 | $w(x,t)$ 时空图（热图或 3D 面） | 坐标轴单位、$w_{\text{crit}}$ 等值线、时间标签 |
| F2 | $w(t)$ 在 3 个代表位置（热点中心、边缘、区外） | 观测/模型/假设 三标签 |
| F3 | 沙去向堆叠图（留存/出区/离岸/慢性）随 $t$ | 百分比 + 绝对量 |
| F4 | $T_p$ 直方图（1000 次 MC） | 中位 + $P_{10}/P_{90}$ |
| F5 | 三方案对比条形图（$T_p$ + 保护岸线·年） | 同一纵轴口径 |
| F6 | tornado 图（OAT） | 参数名 + 基准值 |
| F7 | $\mathcal{V}$–$w_{\min}$ 相图 | $\mathcal{V}_{\text{thr}}$ 分界线 |
| F8 | 三策略 $E$ vs $c_0$ 曲线（排序稳定性） | 交叉点标注 |

> **黑白可辨**：线型 + 标记区分，不只靠颜色（美赛常黑白打印）。

---

## 8. 常见坑（照这个查，能省半天）

| 症状 | 可能原因 | 查法 |
|---|---|---|
| T1 残差 $10^{-3}$ 量级 | 补沙量按整格投放（§2.5） | 打印"实投总量 / 设计总量" |
| T1 残差缓慢增长 | $O$ 用显式 Euler | 换成 §2.3 的精确解 |
| T2 收敛比 ≈2 而非 4 | 时间步没随 dx 细化，或空间用了一阶迎风做扩散 | 关掉对流重测 |
| 结果对 $H$ 极敏感 | $H$ 与 $\mathcal{V}$ 的口径混了（m³ vs m³/m） | 检查 `V = H*y` 只在一处出现 |
| 风暴后 $w$ 反弹超过初始 | $O$ 的回滩没扣 $\lambda$ | 对 T6 |
| `zeroflux` 留存率居然低于 `open` | 边界 ghost cell 符号写反 | 手算一个 3 格例子 |
| MC 跑不完 | 每次重复都重新读文件/重建网格 | 进程池 + 只传 seed |
| 保护期 $T_p$ 是 `inf` | 阈值从未被穿越（$\Delta y_0$ 太大或 $\rho_e=0$） | 加保护：超过 `t_end` 记为 `>=15`，**不要**记 inf |

---

## 9. 交付给建模手的东西

1. `tests/` 全部通过的截图/日志（T1–T8，逐条）；
2. `results/` 下 E0–E7 的目录树 + 每目录的 `results.json` 与 `meta.json`；
3. 一张**总表**：每个实验 → 关键指标 → 分位区间；
4. `figures/` 下 F1–F8 的 PNG（300 dpi）+ 生成脚本；
5. 一页 `REPRODUCE.md`：干净环境下从 `make all` 到出图的完整命令；
6. 已知问题清单（没跑成的、跑得慢的、结果反常的，**不要藏**）。

---

## 10. 时间预算建议

| 任务 | 预计 |
|---|---|
| 求解器 + T1/T3 | 4–6 h |
| T2/T4/T5/T6/T7/T8 | 3–4 h |
| E0/E1/E2 | 3 h |
| E3/E4 | 3 h |
| E5（Sobol） | 2–3 h |
| E6/E7 | 1–2 h |
| 出图 F1–F8 | 3 h |
| **合计** | **约 20–25 h** |

> 如果时间不够：**砍 E5 的 Sobol，保 OAT；砍 F1 的 3D，保热图**。不要砍 T1–T8 —— 那是"可信"的唯一凭证。
