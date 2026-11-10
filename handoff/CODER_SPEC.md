# CODER_SPEC.md — 交给编程手的实现规格（阶段 4 交接）

> **给编程手**：这是**实现规格**，不是模型合同。**模型含义以 `modeling/MODEL_SPEC.md` 为唯一合同**；本文只说明怎么实现。若本文与 `MODEL_SPEC` 冲突，以 `MODEL_SPEC` 为准，并在 `OPEN_QUESTIONS.md` 记录。
> 有疑问 → 写进 `OPEN_QUESTIONS.md`，不要自己改模型。有 bug → 修；有规格缺口 → 问。
>
> 配套：`modeling/MODEL_SPEC.md`（**模型合同**）、`modeling/NONDIM.md`（解析基准与对拍数值）、
> `modeling/params.yaml`（参数）、`modeling/SCENARIOS_STRATEGIES.md`（情景与策略）。
> 版本：v0.5（2026-11-10 第三轮审查后）。参数以 `params.yaml` 为准，本文中的数值若不一致以 yaml 为准。

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

- **生产格式冻结为向后 Euler（BE）+ 守恒有限体积**：一阶时间、无条件稳定、单调性较好。三对角求解（`scipy.linalg.solve_banded` 或 `scipy.sparse.linalg.spsolve`）。
- CN 仅作**可选对照**（时间二阶），且必须另测非负性；基准 $r=9.6$ 时 CN 可能振荡出负值。不要用 CN 作为主算。
- T2 判据按格式区分：BE + $\Delta t\propto\Delta x$ ⇒ 比值 1.8–2.2；CN + $\Delta t\propto\Delta x^2$ ⇒ 3.5–4.5。
- $\Delta t=0.02$ yr（基准）。风暴事件时刻必须**落在步边界**：若下一事件在 $t_k$，令本步 $\Delta t=t_k-t$。
- **S3 波候**：`Hs_trend=+3%/decade` 通过 $D\propto H_b^{5/2}$ 进入，$D(t)=D_0(1+0.03t/10)^{5/2}$；在 CFL 与面通量里用**瞬时** $D(t)$。不要只改一个标签而不改 $D$。

### 2.4b 风暴事件的抽样与注入（主算例）

主算例**不**使用 $R_k$ 强度参数化，而是直接抽"宽滩潜在后退"：

1. **到达**：齐次 Poisson，$\lambda_s$ 取 `params.yaml`。
2. **潜在后退**：$\Delta y_{\text{pot}}\sim\mathrm{LogNormal}$，中位 $\Delta y_{\text{ref}}=8$ m，$P_{95}=25$ m ⇒ $\sigma_{\ln}=\ln(25/8)/1.645=0.694$。
3. **窄滩饱和**：$w_{\text{eff}}=\max(w,0)$；$f=1-\exp(-w_{\text{eff}}/w_s)$，$w_s=20$ m；$\Delta y_k=\Delta y_{\text{pot}}f$。**必须取 max**。
4. **上限**：$\Delta y_k=\min(\Delta y_k,\;w_{\text{eff}})$。**不能用 $w_{\text{eff}}+\Delta y_{\text{cut}}$**（会让 $w$ 跨过 0）；`dy_cut` 废弃。先因子、后上限。
5. **空间足迹**：$S_k(x)=H\Delta y_k\,\phi_k(x)$。主算 $\phi_k=1$ 覆盖整个 9 km 域（区域风暴）；敏感性用 $\phi_k=\exp[-(x-x_k)^2/(2\sigma_e^2)]$，$\sigma_e=2$ km，$x_k\sim U(-L_b,L_b)$。`events.csv` 记 $x_k$、$\sigma_e$、中央/全域注入体积。**不得只给标量 $\Delta y$ 而不给足迹**。
6. **注入**：$y\leftarrow y-\Delta y_k\phi_k$；$O\leftarrow O+H\Delta y_k\phi_k$；$S_k\ge0$。事件时刻按 §2.4 截到步边界。
7. **干滩耗尽**：`w_raw=w0+y`，`w_eff=max(w_raw,0)`。`w_eff=0` 时该步风暴 $\Delta y=0$（无干滩沙；沙丘侵蚀不在模型内），但 **$L_c$、$O$ 的恢复/损失、边界通量、后续补沙全部继续**；`y` 可为负。`beach_exhausted` 只作诊断，不冻结、不删失。`risk_w=1{w_eff<w_mgmt}`，`risk_b=1{d_b+y<m_s}` 分开计算。
8. $R_k/\gamma$ 参数化只作敏感性；当前 `params.yaml` 未给 $R_{\text{ref}}$，**不作为主算**。

**事件推进伪代码（必须按此顺序，禁止把 $S$ 放进连续步）**：

```
t = 0;  next_event = sample_first_arrival()      # Poisson, 单位 yr
while t < T:
    t_stop = min(t + dt_max, next_event, T)      # 步长截到事件时刻
    h      = t_stop - t
    # (1) 连续步：BE 解 [t, t_stop)，源项只有 -Lc；I=0、S=0
    solve_BE(h)                                  # 扩散 + 漂移 + Lc + 边界
    t = t_stop
    # (2) 跳变：仅当 t 到达事件时刻，注入一次
    if abs(t - next_event) < 1e-9:
        apply_storm_once()                       # y -= dy_k*phi; O += H*dy_k*phi
        next_event = t + sample_interarrival()   # 用同一个 RNG 流
    # (3) 同一时刻若有补沙计划，放在风暴跳变之后；瞬时加 y，不经过 BE 源项
    apply_due_placements(t)
```

> 默认 A/B/C 的补沙是**瞬时脉冲**（§2.5），所以连续步里 $I=0$。若以后实现 `ramp` 匀速投放，则 $I$ 进入连续步，且 `apply_due_placements` 只负责登记起止时刻，**不得再加同一笔**——两种模式只能选一种。

- 浮点比较用 `abs(t - next_event) < 1e-9`，不要用 `==`。
- 事件**只注入一次**：`apply_storm_once()` 内部不推进时间，也不再次抽样。
- 若事件恰好落在 $t=T$（模拟终点），仍须注入并记账；不得因循环结束而丢弃。
- 连续步中的 $L_c$、$O$ 恢复/损失用**跳变后**的 $O$ 进入下一步（§2.4a 的 $(O^n+S)e^{-a\Delta t}$ 即等价写法）。

> **S2 的 `forced_dy=25` 按"实际后退"定义**：代码先算 $f(w)$，再取 $\Delta y_{\text{pot}}=25/f$（若 $f>0$），使**实际** $\Delta y=25$ m；若 $w$ 太窄以致 $25>w$，取 $w$（耗尽）。这样"大风暴"情景的强度不随滩宽漂移（Q-34 的推荐口径）。
>
> **S3 的 SLR**：主通道是 `rho_e_scale(t)`（走廊均值 3.0→5.0）；若启用"风暴基线"第二通道，令 $\Delta y_{\text{ref}}(t)=\Delta y_{\text{ref},0}[1+\beta(S_{\text{SLR}}(t)-S_{\text{SLR},0})]$，$\beta$ 必须作为 ASSUME 写入台账；若不启用，在结果里注明"storm-water-level baseline 未单独建模"。

### 2.5 补沙源项 $I$

瞬时投放：在 $t_s$ 那一步把 $\Delta y=\mathcal{V}/(H\ell_s)$ 加到 $|x-x_c|\le\ell_s/2$ 的单元上（**按单元与投放区重叠长度加权，保证总量精确**）。

> ⚠ 常见 bug：用 `x_c ± l/2` 直接 `np.where` 会把边界单元整格计入，导致总方量误差 1–2%，T1 直接不过。

**每次投放的可行量（必须按顺序取 min，且记账）**：

```
V_j = min( V_desired,
           V_event_max,
           V15_total   - V_used,
           S_cap       - S_used,          # S_cap = a_borrow*S_borrow_total (local)
                                          #       = V15_total (external)
           (C_max - cost_used - c0) / c1_eff )
c1_eff = c1                       # cost_model = all_in
       = c1 + c_transport          # supply_scenario = external
       = c1 + c_transport          # marginal_plus_fixed 也照加
```

- `local` 主算：`S_cap = 1.0 × 2.45e6`（可用率 0.8 仅敏感性）；`external`：`S_cap = V15_total`。
- 若 `V_j < V_min_meaningful`（例如低于 1e5 m³），**不得静默投放**：记录 `skipped_reason`，策略 A/B/C 的对比必须报告实际投放总量与设计总量的差。
- 每次投放后更新 `V_used += V_j`、`S_used += V_j`、`cost_used += c0 + c1_eff*V_j`；`permit_delay`/`tau_build` 只影响**批准到施工**的时间，不改变方量。

### 2.6 边界条件（三套，`--bc` 切换）

| 代码 | 实现 |
|---|---|
| `open`（默认） | **扩散**：零梯度 ghost $y_{\text{ghost}}=y_0$（$y_0$ = **第一个内点** `y[0]`，不是初值；不是 $2y_0-y_1$，后者给梯度 $(y_1-y_0)/\Delta x\neq0$）。**对流**：$u>0$ 时左端入流需要上游状态，取 $y_{\text{ghost}}=y_0$（或情景给定的上游值），右端出流用 $y_N$；$u<0$ 镜像。**边界体积通量**记 `flux += H*F*dt`（m³），不是 $F\,dt$（m²） |
| `zeroflux` | **直接把总面通量置零**：$F_{\text{boundary}}=0$（扩散+对流都为零）。只设镜像 ghost 只零掉扩散项 |
| `dirichlet` | 若给定的是**物理边界面值** $y_b$，则 ghost $=2y_b-y_0$（$y_0$ = 第一个内点 `y[0]`；不是 $y_b$）；面通量按上式正常计算 |

> **单位（审查 P0）**：$F=u y-Dy_x$ 的单位是 m²/yr；账本存量是 m³。累计边界体积必须是 $H F\Delta t$。接口里只做一次转换，不要在两处各乘一次。
>
> **不要**在面通量里再加 $Q_\infty$：$\tilde Q_0=Q_0+D V_{0,x}$ 的空间梯度已经并入 $L_c=\rho_e H$，再加一次就是双计数。若 $V_0$ 沿岸变化，面通量的扩散部分仍用 $D H y_x$；不要改写成 $D V_x$ 而漏掉 $V_{0,x}$。
>
> **T7 不再断言"zeroflux 留存一定更高"**：无净输送、边界未受扰或有入流时两者可相等。改用一个**有已知外流**的算例：初始在域中心放一个凸起、$u>0$、$D>0$，用解析/半解析估计边界流出量，比较 `open` 的 `flux` 台账与估计值；`zeroflux` 只作为"流出为零"的对照。

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
| `results.json` | 标量结果：四个时长指标（`T_first_fail_w/b`、`T_safe_cum_w/b`、`T_recovery`）、$E_w/E_b$、留存率、成本、参数快照。**不得再输出含糊的 `T_p` 字段**；解析基准的 $T_p$ 只能出现在 validation 报告里 | — |
| `fields.npz` | `y[nt,nx]` [m]、`O[nt,nx]` [m²]、`w[nt,nx]` [m]、`x[nx]` [m]、`t[nt]` [yr] | float32（体积考虑） |
| `ledger.csv` | 逐时间步的沙量台账（见 §4.3） | — |
| `events.csv` | 每次风暴：$t_k$、$\Delta y_{\rm pot}$、$\Delta y_k$、$x_k$、$\sigma_e$、中央 5 km/全域 9 km 的注入体积（m³）、耗尽单元数 | — |
| `meta.json` | 代码 md5、params md5、Git commit、seed、运行耗时 | — |

### 4.3 `ledger.csv` 列（**沙量台账，T1 的载体**）

```
t, V_central, O_central, V_domain, O_domain,
placed_cum, flux_inner_left_cum, flux_inner_right_cum,
flux_outer_left_cum, flux_outer_right_cum,
offshore_loss_cum, chronic_loss_cum, residual, residual_rel
```

- **两个控制体，不能混**：中央研究区 $[-2500,2500]$（5 km）与全计算域 $[-4500,4500]$（9 km）。
  - `V_central` $=H\sum_{|x|\le2500}y_i\Delta x$；`V_domain` $=H\sum_{\text{all}}y_i\Delta x$（均为**增量**，$O(0)=0$）。
  - `flux_inner_*`：穿过 $x=\pm2500$ 的**体积**通量；`flux_outer_*`：穿过 $x=\pm4500$ 的。
  - 中央流出的沙可能仍在 2 km 缓冲区，**不能**当成已离开 9 km 域，更不能解释为"下游社区受害"。
- **单位**：体积通量累计 $=H\cdot F\cdot\Delta t$（m³）；$F$ 是 m²/yr。
- 全域闭合：`placed = (V+O)_domain + (outer_out) + offshore + chronic`；中央闭合把 `outer_out` 换成 `inner_out`，并把 offshore/chronic 限定在中央。
- `residual_rel` 分母取 $\max(1\ \mathrm{m^3}, |placed\_cum|)$；T1 看最大值。
- 账本与验收场用 **float64**；`fields.npz` 的 float32 只用于展示，不能拿来重算收支。

**⚠ 关于 chronic_loss 与两跑相减**：$\rho_e$ 不依赖 $y$，所以基线/补沙两跑的 $\delta L_c=0$。差额收支里**没有"慢性汇吃掉补沙"这一项**；不要再画这个饼图份额。完整总场的收支本来就从初始状态成立，不需要"只在增量场成立"。

---

## 5. 验收测试清单（**建模手拥有，你必须全部通过**）

| # | 测试 | 做法 | 判据 | 预期数值 |
|---|---|---|---|---|
| **T1** | 沙量收支闭合 | 任意一次运行，读 `ledger.csv` | $\max\lvert\text{residual\_rel}\rvert<10^{-6}$ | 目标 $10^{-12}$，double 可达 $10^{-16}$ |
| **T2** | 对 erf 解收敛 | **光滑高斯初值**（$\sigma=200$ m）；主格式 **BE + $\Delta t\propto\Delta x$**；CN 可选，用 $\Delta t\propto\Delta x^2$；另用阶跃初值测 $L_1$/前沿 | **BE：** L2 比值 $\in[1.8,2.2]$；**CN（可选）：** $\in[3.5,4.5]$；阶跃的 $L_\infty$ 不判阶；另做**非负性检查** | 见下 |
| **T3** | 零源项/守恒 | (a) 均匀 $y$、$O=0$、$u=0$、零通量 ⇒ 全场不变；(b) 非均匀 $y$、零通量 ⇒ 总量守恒 + 对 erf 解；(c) $O$ 单独指数衰减 | (a) $<10^{-12}$；(b) 质量 $<10^{-10}$；(c) $e^{-(k+\lambda)t}$ | — |
| **T4** | 网格/时间步一致性 | $dx=50$ vs $25$，同一情景确定性运行 | 关键指标（$T_p$、留存率）差异 $<2\%$ | — |
| **T5** | 无风暴退化 | 配置：$\lambda_s=0$、$\lambda=0$、$u=0$、$\rho_e$ 均匀 2.3、$w_0$ 均匀 18、$w_{mgmt}=20$；与 NONDIM §7 对拍 | $T_p$ 相对误差 $<10\%$ | 见 §6 |
| **T6** | 单事件恢复 | 一次 $S_0$，无后续事件 | 最终回滩比例 $\to k/(k+\lambda)=0.87$；$t\to\infty$ 时 $O\to0$ | $0.87\pm0.001$ |
| **T7** | 边界通量 | 初始中心凸起、$u>0,D>0$ 的**已知外流**算例 | `open` 的 `flux_outer` 与半解析估计差 $<10\%$；`zeroflux` 的 `flux=0` | 不比较"留存率高低" |
| **T8** | 可复现 | 同一 seed 跑两次 | `results.json` 逐字节相同 + `fields.npz` md5 相同 | — |
| **T9** | **历史岸线诊断（Q3，不是通过/失败测试）** | 用 `_gis/hatteras_transects/Hatteras_Transects.dbf` 的 `LRR78_2002`/`LRR89_2002`（1308 条，含 DAS_km）；**先固定 transect 选择规则**（走廊范围、DAS 窗口、缺测/异常剔除），再算观测分布 | 报告观测均值/中位/区间与模型基线的**差异**；**2.5–4.5 m/yr 只是设计参考区间，不是通过标准**。不确定度按 4.5–4.8 m 披露 | 见 `资料/01_岸线侵蚀速率/USGS_岸线数据说明.md` |
| **T10** | **事件落在步边界/终点** | 三次运行：事件在 $t=1.00$（$\Delta t=0.02$ 的整倍数）、$t=1.01$（步中）、$t=T$（终点）；每次只放 1 个事件，关闭后续抽样 | (a) `n_events_applied=1`，不得 0 或 2；(b) 跳变后瞬时 $O=H\Delta y_k\phi$（误差 $<10^{-12}$ 相对）；(c) `storm_injected_cum` = 设计注入量；(d) 质量账本闭合（T1 同时成立） | 解析值 |

### T2 的参考数值（已由原型实测，可直接对拍）

| $\Delta x$ | 阶跃 $L_\infty$ 相对误差 | 质量相对变化 |
|---|---|---|
| 100 m | $3.73\times10^{-3}$ | $1.5\times10^{-16}$ |
| 50 m | $4.35\times10^{-3}$ | $0$ |
| 25 m | $4.62\times10^{-3}$ | $4.4\times10^{-16}$ |

> **阶跃 $L_\infty$ 不收敛是正常的**：间断处的离散误差由初值主导，不能用来判阶（旧表把它读成"一阶"是错的）。
> 原型另用**光滑高斯初值**测得 $L_2$ 误差比 **3.96 / 3.99**（理论 4）。你的 CN + 有限体积应在光滑初值上给 ≈4；若给 ≈1，先查时间步是否随 $\Delta x$ 同步细化。BE + $\Delta t\propto\Delta x$ 才给 ≈2。

---

## 6. 参考对照数值（无风暴、无对流、单次投放）

参数：$H=10$ m，$D=3\times10^{5}$ m²/yr，$\rho_e=2.3$ m/yr（DEQ 实测推得的走廊等效值），$\mathcal{V}=10^{6}$ m³，$w_0=18$ m，$w_{\text{mgmt}}=20$ m。

> **这是解析基准配置，不是主算例的初始场**：它用均匀 $w_0=18$ m 和均匀 $\rho_e=2.3$ m/yr；主算例用热点 $w_0(x)$（远场 25、最小 16）和 $\rho_e(x)$（1.7 + 热点放大）。T5 只在这个基准配置下对拍，不能拿主算例的热点场去比。
>
> **口径**：下表 $T_p$ 是"滩宽 $w\ge20$ m"的**管理滩宽保护期**，不是建筑净距风险；建筑净距口径见 `MODEL_SPEC` §6.2。

| 方案 | $\ell$ | $\Delta y_0$ | 中心 $T_p$ | 保护岸线·年 | 避免风险（热点场） |
|---|---|---|---|---|---|
| A 匀铺 | 5000 m | 20 m | **6.15 yr** | 26408 m·yr | 28086 m·yr |
| B 热点 | 1000 m | 100 m | **7.33 yr** | 24836 m·yr | **31320 m·yr** |
| C 单段 0.5 km（全部沙量集中） | 500 m | 200 m | **7.36 yr** | 24504 m·yr | **31412 m·yr** |

> **C 行是"把 100 万 m³ 全放在 0.5 km"**，不是五段方案的一段；五段等分每段 20 万 m³（$\Delta y_0=40$ m），必须单独算。
> **避免风险排序已修正**：B/C 高于 A；旧表把符号算反，已作废。

还有两条闭式：
- $T_{1/2}=0.2748\,\ell^2/D$（$\ell$=1000 m ⇒ 0.92 yr）
- 匀铺可行性 $\mathcal{V}_{\text{thr}}=H L(w_{\text{mgmt}}-w_{\min})$（本例 $2.0\times10^{5}$ m³）

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
| E4 | `--scenario {S1,S2,S3} --strategy {A,B,C,adaptive} --supply {local,external} --cost-model {all_in,marginal_plus_fixed}`。**主算 `all_in`（$c_1=27,c_0=0$）**；$c_0\in[0,10]$ M\$ 扫描**只在 `marginal_plus_fixed` 下做**，不得与 `all_in` 混算 | 三策略同约束对比 + 成本；`marginal_plus_fixed` 才输出 $c_0^*$ 交叉点 |
| E5 | `sweep.py --oat` + `--sobol`；风暴组必须含 `dy_p95=40`（2025 Buxton 观测到 43 m） | tornado 图 + Sobol 图 |
| E6 | `--bc {open,zeroflux,dirichlet}`；另做 **域大小敏感性**：$L_b=4.5$ km vs $7$ km（中央 5 km 指标差异 >5% 则报告） | 边界/缓冲敏感性表 |
| E7 | $\mathcal{V}\in[1e5,5e6]$ × $w_{\min}\in[6,22]$ 网格 | 相图（含 $\mathcal{V}_{\text{thr}}$ 线） |

> **Q-33 已解决（2026-11-09，第三轮补沙源约束）**：符号拆成 $V_{15,\text{total}}=5.0$M（15 年总量）、$V_{\text{event,max}}=2.9$M（单次 5 年工程）、$S_{\text{borrow,total}}=2.45$M（本地沙源）。$C_{\max}=120$M、$c_1=27$、$c_0=0$ 时：
> - **本地沙（主算）**：$N=1$ 为 $\min(5,2.9,2.45,4.44)=2.45$M（沙源绑定）；$N\ge2$ 仍为 2.45M（沙源绑定）。三策略都只能用 2.45M，差别在时机与空间分配。
> - **外调沙（情景）**：$N=1$ 为 $\min(5,2.9,5.0,4.0)=2.9$M（单次上限绑定）；$N=2,3$ 为 $\min(5,5.8/8.7,5.0,4.0)=4.0$M（预算绑定；外调 $c_1^{\text{eff}}=30$）。
>
> 主算 `all_in` 且 $c_0=0$：外调沙下 $N\ge2$ 可买总量相同（4.0M），差别只在**时机**；本地沙下所有 $N$ 都受 2.45M 约束。$c_0>0$ 只在 `marginal_plus_fixed` 下扫描，主算没有 $c_0^*$。
>
> **不需要改 $C_{\max}$**。

### 7.2 出图规格（论文手直接用）

| 图 | 内容 | 必须标注 |
|---|---|---|
| F1 | $w(x,t)$ 时空图（热图或 3D 面） | 坐标轴单位、$w_{\text{mgmt}}$ 等值线、时间标签 |
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
