# CODER_SPEC.md — 交给编程手的实现规格

> ## 0. 立即执行令（2026-11-11 17:25 发布，**优先级最高**）
>
> **你现在就开工，不要再等任何确认。** 合同已经冻结（D1–D18），本文件已自查 48 项，且附带 190 行可运行参考实现。
>
> 你只需要盯三个数：
> 1. `T1` 台账残差 $<10^{-6}$（参考实现实测 $10^{-13}$）；
> 2. `T3(a)(c)` 两条通过；
> 3. A/B/C 的中心 $T_p$ 落在 **6.15 / 7.33 / 7.36 yr 的 ±10%**。
>
> 三个数一绿，直接进 E0/E1。**不要**先把代码写"漂亮"，也不要先写文档。
>
> ### 0.1 你可以自己决定（不需要问任何人）
>
> | 事项 | 说明 |
> |---|---|
> | 代码结构与命名、日志格式 | 只要 §3 的模块职责不被破坏 |
> | 线性求解器 | `scipy.linalg.solve_banded` / 自写 Thomas / 稀疏，任选，只要 T2 阶数达标 |
> | 时间步与 CFL、自适应步长 | 只要事件仍在步边界、T4 的 2% 达标 |
> | 本文件**未定义**的默认值（例如诊断输出频率、缓存策略） | 自己定，写进 `configs/defaults.yaml` 即可 |
> | 图的样式、配色、字体、DPI | 只要满足 §7.2 的"黑白可辨 + 单位 + 数据类型标签" |
> | 测试的组织与断言写法 | 只要覆盖 T1–T12 |
> | 并行方式（进程池/线程/串行） | 只要 T8 可复现 |
> | 采样频率、诊断字段的增删 | 只要 §4.2b 的必备键不删 |
>
> ### 0.2 必须上报（只有这 6 条）
>
> 1. 要改 D1–D18 中的任何一条；
> 2. 要改主指标（$E_b$）、阈值（$w_{\text{mgmt}}$、$m_s$、$f_{\text{thr}}$）；
> 3. 要改情景 S1/S2/S3 或策略 `once/repeat/targeted/adaptive` 的定义；
> 4. 发现合同**内部矛盾**，且"取更保守或更简单"两种解法会给出不同结论；
> 5. 要删掉或放宽任何一条验收测试；
> 6. 结果与解析基准偏差 >10% 且自查后仍找不到原因。
>
> ### 0.3 上报方式与响应
>
> - 在 `PROGRESS.md` 末尾的 **`## 编程手提问`** 段追加一行：`HH:MM | 问题 | 我倾向的解法 | 阻塞等级`；
> - 建模手 **2 小时内**在该行下方回 `→ 决定：...`；
> - **等不到回复时按 §0.4 自行推进**，并把决定写在同一行，标 `[自决]`。
>
> ### 0.4 无回复时的默认裁决
>
> **取更保守（保护期更短、结论更难成立）的选项，并记录。** 例如：$D$ 取上沿、$\Delta y$ 取下沿、边界取 `open` 而非 `zeroflux`。
>
> ### 0.5 完成一个节点就做一件事
>
> 在 `PROGRESS.md` 追一行：`HH:MM | 节点 N# 完成 | 关键数字 | 下一个 DDL`。**不要发长篇报告。**
>
> ---
>
> 以下 §1–§10 是执行依据。**有冲突时以 §0 为准，其次以 `MODEL_SPEC` 为准。**


## 1. 目标与非目标

**要做**：一个一维、双状态（$V,O$）、事件驱动的沙量演化求解器 + 沙量台账 + 批量实验驱动 + 出图。

**不做**（别浪费时间）：
- 不做二维水动力、不做波形爬坡、不做 SBEACH；
- 不做 GUI、不做交互式可视化（只要 matplotlib 出图）；
- 不优化性能到极致——1000 次蒙特卡洛在单机上 < 30 min 即可。

---

## 2. 方程与离散（照抄即可）

### 2.0 初始化场与情景时变（**照抄，不要自己发明**）

```python
nx  = 360; Lb = 4500.0; dx = 25.0
x   = -Lb + dx/2 + dx*np.arange(nx)     # 360 个控制体中心；ΣΔx = 9000 m
w0  = w_far - (w_far - w_min) * np.exp(-x**2 / (2*sigma_w**2))     # 25,16,700
rho_base = rho_e * (1 + a_h * np.exp(-x**2 / (2*sigma_h**2)))      # 1.7,1.2,600
y0  = np.zeros(nx)                       # 岸线异常，单位 m
V0  = np.full(nx, V_ref)                 # 250 m^2，常数
O0  = np.zeros(nx)
V_min = V_ref - H * w0                   # 远场 0，热点 90 m^2
w   = w0 + y                             # 干滩宽度
```

- $H=h_*+B=10$ m；`V = V0 + H*y` 只允许出现在**这一个函数**里（`units.py`）。
- **网格自检**：`nx*dx == 9000`、中央 `|x|<=2500` 恰为 **200** 格（不是 201）。
- **初始场自检**：`abs(w.min()-16)<1e-9`、`abs(w.max()-25)<0.05`、`abs(V_min.max()-90)<1e-9`。

**S3 的时变律（线性插值，端点由 `params.yaml` 给）**：

```python
u = t / 15.0                                   # 0 -> 1
lambda_s(t) = 0.4 + (0.8-0.4)*u                # 0.4 -> 0.8
dy_ref(t)   = 8.0 + (11.0-8.0)*u               # 8 -> 11
target_total(t) = 3.0 + (5.0-3.0)*u            # 3 -> 5
rho_storm(t) = lambda_s(t) * dy_ref(t)*exp(sig**2/2) * lam/(k+lam)
scale(t)     = (target_total(t) - rho_storm(t)) / 2.31
rho_e(x,t)   = scale(t) * rho_base(x)
```

> S1、S2 是**定常**的，直接用表里的常数，不要插值。
> `lambda_s(t)` 是**非齐次泊松**：到达率随时间变，抽样要用**反函数/细化法**（thin-and-simplify 到 $\lambda_{\max}=0.8$ 再接受/拒绝），不能把 15 年当成一个常数率。

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

> **$V_0$ 取常数（A3/D10）**：主算 $V_0(x)\equiv V_{\text{ref}}$，故 $V_{0,x}=0$，面通量里**不要**再加 $V_0$ 的梯度项。
> 敏感性方案 $V_0=H\,w_0$ 才需要 $F \mathrel{+}= -D\,H\,w_{0,x}$；两种口径用同一个开关，不得混跑。

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

> **P0-3：$O\to V$ 的恢复必须用"步平均量"接入 BE，不能把 $kO$ 当成速率直接塞进隐式方程。**
> 记本步回滩量（m²）
> $$
> \boxed{\ R_n=\frac{k}{k+\lambda}\bigl(O^{n}-O^{n+1}+S\bigr)\ }
> $$
> 则 $y$ 方程的源项为 $+\dfrac{R_n}{H\,\Delta t}$（m/yr），**逐单元常数**，与隐式矩阵无关。
> **禁止**三种写法：$kO^{n+1}/H$（高估，且把 $O$ 隐式耦合进三对角）、$kO^{n}/H$（低估）、$\frac{k}{H}\frac{O^n+O^{n+1}}{2}$（与 $O$ 的精确解不一致，T6 会漂）。
> 自检：$\sum_i R_n/H\,\Delta t\cdot\Delta x$ 必须等于台账里的 `recovery_cum` 增量。

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
   > **$f$ 是可变的**：$w=16$ 时 $f=0.551$、$w=25$ 时 $f=0.713$。所以 8 m 的"潜在后退"在热点实际只有 4.41 m。
   > S2 要把**实际**后退钉到 25 m，必须反解 $\Delta y_{\text{pot}}=25/f$（再受 $w_{\text{eff}}$ 上限）；直接给 25 只会得到 $25f\approx13$–18 m。
4. **上限**：$\Delta y_k=\min(\Delta y_k,\;w_{\text{eff}})$。**不能用 $w_{\text{eff}}+\Delta y_{\text{cut}}$**（会让 $w$ 跨过 0）；`dy_cut` 废弃。先因子、后上限。
5. **空间足迹**：$S_k(x)=H\Delta y_k\,\phi_k(x)$。主算 $\phi_k=1$ 覆盖整个 9 km 域（区域风暴）；敏感性用 $\phi_k=\exp[-(x-x_k)^2/(2\sigma_e^2)]$，$\sigma_e=2$ km，$x_k\sim U(-L_b,L_b)$。`events.csv` 记 $x_k$、$\sigma_e$、中央/全域注入体积。**不得只给标量 $\Delta y$ 而不给足迹**。
6. **注入**：$y\leftarrow y-\Delta y_k\phi_k$；$O\leftarrow O+H\Delta y_k\phi_k$；$S_k\ge0$。事件时刻按 §2.4 截到步边界。
7. **干滩耗尽**：`w_raw=w0+y`，`w_eff=max(w_raw,0)`。`w_eff=0` 时该步风暴 $\Delta y=0$（无干滩沙；沙丘侵蚀不由风暴项建模），但 **$L_c$、$O$ 的恢复/损失、边界通量、后续补沙全部继续**。
   - `y` **可以**继续为负（侵蚀前锋进陆），**不加下限**；
   - **下限加在 $V$ 上**：`V=max(V0+H*y, V0-H*w0)`，触底差额进 `R_c`（§2.4c）；
   - `risk_w=1{w_eff<w_mgmt}`（耗尽后恒 1）；`risk_b=1{d_b+y<m_s}`（**按公式算，不强制 1**）。
8. $R_k/\gamma$ 参数化只作敏感性；当前 `params.yaml` 未给 $R_{\text{ref}}$，**不作为主算**。

**事件推进伪代码（必须按此顺序，禁止把 $S$ 放进连续步）**：

```
t = 0
apply_due_placements(0.0)                        # ★ 先做 t=0 投放，再抽样任何事件
next_event = sample_first_arrival()              # Poisson, 单位 yr（严格 > 0）
while t < T:
    t_stop = min(t + dt_max, next_event, T)      # 步长截到事件时刻
    h      = t_stop - t
    # (1) 连续步：BE 解 [t, t_stop)，源项为 -Lc + R_n/(H*dt)；I=0、S=0
    #     R_n = k/(k+lambda)*(O^n - O^{n+1} + S)  ← 步平均，见 §2.3
    solve_BE(h)                                  # 扩散 + 漂移 + Lc + kO 恢复 + 边界
    t = t_stop
    # (2) 跳变：仅当 t 到达事件时刻，注入一次
    if abs(t - next_event) < 1e-9:
        apply_storm_once()                       # y -= dy_k*phi; O += H*dy_k*phi
        next_event = t + sample_interarrival()   # 用同一个 RNG 流
    # (3) 同一时刻若有补沙计划，放在风暴跳变之后；瞬时加 y，不经过 BE 源项
    apply_due_placements(t)
```

> **P0-4 顺序铁律**：$t=0$ 的投放必须发生在**第一次抽样之前**，否则第一行连续步会在"没有投放"的初始场上推进，且若手工把事件设到 $t=0$，风暴会先于投放执行。
> 完整顺序固定为：`t=0 投放 → 抽样首个事件 → 截步 → 连续步 → 事件跳变 → 同一时刻的投放 → 记录 → 下一事件`。
> 事件时刻若恰为 $t=0$（仅测试用），也必须在 `apply_due_placements(0)` **之后**注入。
>
> 默认 A/B/C 的补沙是**瞬时脉冲**（§2.5），所以连续步里 $I=0$。若以后实现 `ramp` 匀速投放，则 $I$ 进入连续步，且 `apply_due_placements` 只负责登记起止时刻，**不得再加同一笔**——两种模式只能选一种。

- 浮点比较用 `abs(t - next_event) < 1e-9`，不要用 `==`。
- 事件**只注入一次**：`apply_storm_once()` 内部不推进时间，也不再次抽样。
- 若事件恰好落在 $t=T$（模拟终点），仍须注入并记账；不得因循环结束而丢弃。
- 连续步中的 $L_c$、$O$ 恢复/损失用**跳变后**的 $O$ 进入下一步（§2.4a 的 $(O^n+S)e^{-a\Delta t}$ 即等价写法）。

> **S2 的强制事件用绝对时刻 $t=2.25$ yr**（$=\tau_{\text{permit}}(1.0)+\tau_{\text{build}}(0.75)+0.5$）。
> 为什么不是"相对首次投放"：**基线与补沙必须用同一张事件表**（`MODEL_SPEC` §6.2），否则两跑差里混进了不同的风暴时间，差值就不能解释为补沙效应。
> 事件表按 `scenario+seed` **预先生成**（`event_table: shared_per_scenario`），基线、三种布置、四种策略**重放同一张表**。
> 若研究"风暴距投放 0.5 年"的条件效应，另开一个实验（E3），**不得**与同事件配对的策略效应混用。
>
> **S2 的 `forced_dy=25` 按"实际后退"定义**：代码先算 $f(w_{\text{eff}})$，再取 $\Delta y_{\text{pot}}=25/f$（若 $f>0$），使**实际** $\Delta y=25$ m；若 $w_{\text{eff}}$ 太窄以致 $25>w_{\text{eff}}$，取 $w_{\text{eff}}$（耗尽）。这样"大风暴"情景的强度不随滩宽漂移（Q-34 的推荐口径）。
>
> **S3 的 SLR**：主通道是 `rho_e_scale(t)`（走廊均值 3.0→5.0）；若启用"风暴基线"第二通道，令 $\Delta y_{\text{ref}}(t)=\Delta y_{\text{ref},0}[1+\beta(S_{\text{SLR}}(t)-S_{\text{SLR},0})]$，$\beta$ 必须作为 ASSUME 写入台账；若不启用，在结果里注明"storm-water-level baseline 未单独建模"。

### 2.4c 非负性裁剪与退岸计数器（A2/D9 + P0-2，**必须实现**）

**裁剪对象是 $V$，不是 $y$。**

```python
V_abs  = V_ref + H*y                     # 代数存量，可为负
V_min  = V_ref - H*w0(x)                 # 逐单元下界
V_book = np.maximum(V_abs, V_min)        # 账面存量（>= V_min）
R_c    = np.maximum(V_min - V_abs, 0.0)  # ★ 当前亏空（可恢复），进台账
D_max  = np.maximum(D_max, R_c)          # 诊断：历史最深亏空，不进守恒
# y 一律不裁剪：它是侵蚀前锋，risk_b 直接用
```

> ⚠ **不要写 `R_c = np.maximum(R_c, deficit)`**（历史峰值）。补沙后 $R_c$ 不回落，T1 会在"侵蚀后再补沙"的算例里炸掉（实测残差 $3.6\times10^{6}$ m³）。

- `R_c` **只增不减**；补沙抬升 $y$ 后，一旦 $y>-w_0$，$V$ 重新由 $V_0+Hy$ 决定，但 `R_c` 不回退；
- `ledger.csv` 增加 `R_c_cum`（区内 $\int R_c\,dx$，m³）并计入守恒式右端；
- **通量限制器**：连续步装配前，把每个单元的可用存量算出来；若某步净流出使 $V<V_{\min}$，按比例缩放该单元的对岸通量，**未搬走的部分不记账**（不要"先搬再补"）。`Q_limited_cum` 只作诊断；
- `exhausted = (V - V_min < 1e-12)`：该掩膜只用于**诊断与输出屏蔽**（$V$ 不再作物理量报告），**不冻结、不删失**；
- `fields.npz` 输出 `exhausted[nt,nx]` 布尔掩膜；后处理引用 $V$ 前必须先掩膜。
### 2.4d 风暴足迹 $\phi$ 的归一化（**必须写死，否则总量会随机变**）

$\Delta y_k$ 的语义是**足迹峰值的后退量**（不是全段等效后退）。逐单元：

```python
for i:
    f_i  = 1 - np.exp(-w_eff[i] / w_s)          # 窄滩饱和
    dy_i = np.minimum(dy_pot * f_i, w_eff[i])   # 上限：不能超过可蚀宽度
    dy_i = dy_i * phi[i]                         # 足迹（峰值=1）
y   -= dy
O   += H * dy
```

- **uniform（主算）**：$\phi_i\equiv1$，注入总体积 $=H\sum dy_i\Delta x$；
- **Gaussian（仅敏感性）**：$\phi_i=\exp[-(x_i-x_k)^2/(2\sigma_e^2)]$，**再除以 $\max_i\phi_i$ 使峰值为 1**（不是除以 $\sum\phi$——那会把峰值压低，$\Delta y$ 的含义就变了）；
- `events.csv` 必须同时记：**中心后退** $\Delta y_k$、$\phi$ 的形状与 $\sigma_e$、**全域注入体积**与**中央 5 km 注入体积**。
- **自检**：$\sum_i H\,dy_i\Delta x$ 必须等于 `storm_injected_cum` 的增量（相对误差 $<10^{-12}$）。

> ⚠ 常见错法：把 Gaussian 归一化成 $\sum\phi_i\Delta x=1$（即"总量守恒但峰值极小"），此时 $\Delta y_k$ 不再是中心后退，情景强度全变。


### 2.5 补沙源项 $I$

瞬时投放：在 $t_s$ 那一步把 $\Delta y=\mathcal{V}/(H\ell_s)$ 加到 $|x-x_c|\le\ell_s/2$ 的单元上（**按单元与投放区重叠长度加权，保证总量精确**）。

> ⚠ 常见 bug：用 `x_c ± l/2` 直接 `np.where` 会把边界单元整格计入，导致总方量误差 1–2%，T1 直接不过。

### 2.5b 成本模型（A6/D18，两种结构**分开**算）

$$
\text{cost}_{\text{all\_in}}=\sum_{j:\ \mathcal V_j>0} c_1\,\mathcal V_j
\qquad c_1=27\ \text{USD/m}^3,\ c_0=0
$$

$$
\text{cost}_{\text{marginal}}=\sum_{j:\ \mathcal V_j>0}\bigl(c_0+c_{1}^{\text{marg}}\,\mathcal V_j\bigr)
\qquad c_1^{\text{marg}}=11\ \text{USD/m}^3,\ c_0\in[0,10]\ \text{M}
$$

- **实际投放量为 0 的工程不收 $c_0$**（`if V_j <= 0: continue`）；
- **外调沙的单价必须按结构分别算（P0-5）**：
  - `all_in` + `external`：$c_1^{\text{eff}}=27+3=\mathbf{30}$ USD/m³；
  - `marginal_plus_fixed` + `external`：$c_1^{\text{eff}}=11+3=\mathbf{14}$ USD/m³，**不是 30**；
  - 外调成本**只加到 $c_1$ 上**，绝不能再乘一次或加到 $c_0$ 上。
- 两种结构的输出目录必须不同（`results/E4_all_in/...`、`results/E4_marginal/...`），**不得**把两条成本曲线画在同一张图上；
- $c_0^*$ **只在 `marginal_plus_fixed` 下输出**；`all_in` 下 `c0_star` 字段写 `null`，不要伪造。

**每次投放的可行量（必须按顺序取 min，且记账）**：

```
V_j = min( V_desired,
           V_event_max,
           V15_total   - V_used,
           S_cap       - S_used,          # S_cap = a_borrow*S_borrow_total (local)
                                          #       = V15_total (external)
           (C_max - cost_used - c0) / c1_eff )
c_unit = c1                        # cost_model == all_in        (27 USD/m3)
       = c1_marginal               # cost_model == marginal_plus_fixed (11 USD/m3)
c1_eff = c_unit + (c_transport if supply_scenario == "external" else 0.0)
       # => all_in+local 27 | all_in+external 30 | marginal+local 11 | marginal+external 14
```

- `local` 主算：`S_cap = 1.0 × 2.45e6`（可用率 0.8 仅敏感性）；`external`：`S_cap = V15_total`。
- 若 `V_j < V_min_meaningful`（例如低于 1e5 m³），**不得静默投放**：记录 `skipped_reason`，布置/策略的对比必须报告实际投放总量与设计总量的差。
- 每次投放后更新 `V_used += V_j`、`S_used += V_j`、`cost_used += c0 + c1_eff*V_j`；`permit_delay`/`tau_build` 只影响**批准到施工**的时间，不改变方量。

### 2.5c 两个族：布置（Q2）与策略（Q5）——**命名不要混**

题型里有两组"A/B/C"，含义不同，实现时必须用不同枚举名，否则 E1 与 E4 会对不上。

**布置族 `placement`（Q2 / E1，总方量相同）**

| 名 | 规则 |
|---|---|
| `uniform` | $x_c=0,\ \ell=5000$ m |
| `hotspot` | $x_c=x_h=0,\ \ell=1000$ m |
| `multi` | 5 段 × 500 m，中心间隔 900 m，各投 $\mathcal{V}/5$ |

**策略族 `strategy`（Q5 / E4，同一预算/沙源约束）**

| 名 | 次数与时刻 | 空间 | 每次方量 |
|---|---|---|---|
| `once` | 1 次，$t=\tau_{\text{permit}}+\tau_{\text{build}}$ | `uniform` | 可行量全部 |
| `repeat` | 3 次，$t\in\{0,5,10\}+\tau_{\text{permit}}+\tau_{\text{build}}$ | `uniform` | 每次取 1/3 |
| `targeted` | 1 次（可追加至 4 次，每次触发后） | `hotspot` 1 km，投到 $\arg\max \Delta E_b/\text{cost}$ 处 | 可行量全部 |
| `adaptive` | 按 `SCENARIOS_STRATEGIES.md` §4.1 触发（$t=0$ 只评不动工） | 逐次选址 | 逐次决策 |

- 所有时刻都要加 $\tau_{\text{permit}}+\tau_{\text{build}}$（默认 1.0 + 0.75 yr）；若加完超过 $T=15$，该次**取消并记录** `skipped_due_to_window`。
- `repeat` 的 5 年间隔是**设计选择**（不是最优值），论文必须写明。
- 策略比较一律用**实际可投方量**（§2.5 的 `V_j`），并报告设计量 vs 实投量的差。
- `adaptive` 的空间选址依赖主指标 $E_b$（D12），不是 $E_w$。
- **E1（布置对比）用理想化 $t=0$ 投放、不计许可/施工时滞**；**E4（策略对比）必须计**。两套结果不能混报，
  否则"一次 vs 多次"的差异会同时包含"空间形态"与"时滞"两个因素，归因不清。


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

## 3.5 全局数值口径约定（**第二轮审查新增；不遵守必出怪数**）

| 项 | 约定 | 为什么必须写死 |
|---|---|---|
| **状态与台账** | 内部状态用**绝对** $V=V_{\text{ref}}+Hy$（$V_{\text{ref}}=250$）；`ledger.csv` 的 `V_*`、`O_*` 是**相对初始的增量**（$V-V_{\text{ref}}$、$O-O(0)$） | 混用会让 T11 的 $\min V\ge V_{\min}$ 与 T1 的闭合差一个 $V_{\text{ref}}L$ 的常数 |
| **指标定义域** | 所有时长/暴露/失败比例 $f_c(t)$ 只在**中央 5 km** $[-2500,2500]$ 上算；边界通量与沙量闭合算**全域 9 km** | 两者混用会被"缓冲区"污染，且与论文口径不符 |
| **通量符号** | `flux_outer_left_cum` 表示**从左边流出域**的累计体积（m³），流出为正；右边同理。实现时先用面通量 $F$ 的正方向，再乘符号 | 符号写反时 T7 会给出"流出为负" |
| **补沙时刻** | 计划时刻 $t_s$ 必须**吸附到第一个 $\ge t_s$ 的步边界**，并在 `events.csv` 记 `t_s_actual`；若 $t_s_{\text{actual}}>T$ 则取消并记 `skipped_due_to_window` | 否则同一输入会因 $dt$ 不同给出不同结果 |
| **投放体积守恒** | 投放必须按**单元与投放区重叠长度加权**，并断言 $\lvert\sum_i H\Delta y_i\Delta x-\mathcal{V}\rvert/\mathcal{V}<10^{-12}$ | 整格投放会有 1–2% 误差，T1 直接不过 |
| **MC 随机种子** | 第 $i$ 次实现用 `seed_i = (seed * 1000003 + i) % 2**32`，并把它写进 `meta.json` | 否则 T8 不可复现，也无法事后重跑单条 |
| **风暴强度分布** | 对数正态，**中位 $\Delta y_{\text{ref}}$、$\sigma_{\ln}=0.6927$ 固定**（即 P95/中位 = 3.125 恒定）；S3 只改中位，不改形状 | 形状随时间变会让情景之间不可比 |
| **两类随机流** | 到达时刻与强度用**两条独立 RNG 流**（`rng_arrival`、`rng_mag`），不共用 | 共用会让"加一次事件"改变后续所有强度 |


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
  rho_e_scale: 1.068        # S2: (3.0 - 0.530)/2.31；乘基线 rho_e(x)，保留热点
  D_diff: 300000.0
```

> **$\rho_e$ 是空间场，不是标量；而且缩放必须扣掉情景自己的风暴贡献（2026-11-11 修正）。**
>
> 情景表里的 `rho_e` 是**走廊总速率目标**（含风暴），模型里 $\rho^{\text{storm}}$ 是另外加上去的。所以：
> $$
> \text{scale}(s)=\frac{\text{target}(s)-\rho^{\text{storm}}(s)}{\bar\rho_e},\qquad
> \rho^{\text{storm}}(s)=\lambda_s(s)\cdot\bigl[\Delta y_{\text{ref}}(s)e^{\sigma^2/2}\bigr]\cdot\frac{\lambda}{k+\lambda}
> $$
> 其中 $\bar\rho_e=2.31$、$\sigma=0.6927$、$\lambda/(k+\lambda)=0.1304$。然后 $\rho_e(x;s)=\text{scale}(s)\cdot\rho_e^{\text{base}}(x)$，**保留热点结构**。
>
> | 情景 | $\rho^{\text{storm}}$ | target | **scale** |
> |---|---|---|---|
> | S1 | 0.199 | 1.7 | **0.649** |
> | S2 | 0.530 | 3.0 | **1.068** |
> | S3 $t=0$ | 0.530 | 3.0 | **1.068** |
> | S3 $t=15$ | 1.459 | 5.0 | **1.531** |
>
> **不要用 `target/2.3`**（S2 会给 1.304），那是把风暴算了两遍，S2 总速率会高估约 22%。
> **不要**用 `rho_e: 3.0` 覆盖整场，否则热点消失、定点投放的对比失真。

### 4.2 输出目录（**每件必备**）

| 文件 | 内容 | 形状/单位 |
|---|---|---|
| `results.json` | 标量结果：五个时长量（`T_first_fail_w/b`、`T_safe_cum_w/b`、`T_recovery`）、$E_w/E_b$、留存率、成本、参数快照。**不得再输出含糊的 `T_p` 字段**；解析基准的 $T_p$ 只能出现在 validation 报告里 | — |
| `fields.npz` | `y[nt,nx]` [m]、`O[nt,nx]` [m²]、`w[nt,nx]` [m]、`x[nx]` [m]、`t[nt]` [yr] | float32（体积考虑） |
| `ledger.csv` | 逐时间步的沙量台账（见 §4.3） | — |
| `events.csv` | 每次风暴：$t_k$、$\Delta y_{\rm pot}$、$\Delta y_k$、$x_k$、$\sigma_e$、中央 5 km/全域 9 km 的注入体积（m³）、耗尽单元数 | — |
| `meta.json` | 代码 md5、params md5、Git commit、seed、运行耗时 | — |

### 4.2b `results.json` 字段（**固定 schema，论文手按名取值**）

```json
{
  "meta": {"scenario":"S2","strategy":"A","bc":"open","cost_model":"all_in",
           "supply":"local","seed":42,"commit":"<git sha>","params_md5":"..."},

  "initial": {"f_w0": 0.3036, "f_b0": 0.0, "w_min": 16.0, "w_mean": 21.84},

  "duration": {
    "T_first_fail_w": {"value": 4.21, "censored": false},
    "T_first_fail_b": {"value": 11.8, "censored": false},
    "T_safe_cum_w":   14.02,
    "T_safe_cum_b":   15.00,
    "T_recovery":     {"median": 1.31, "n": 7, "censored": 2}
  },

  "exposure": {"E_w": 3.1, "E_b": 0.42},
  "retention": {"R_ret_1yr": 0.71, "R_ret_5yr": 0.38, "R_ret_15yr": 0.11},

  "mass": {"placed": 2.45e6, "flux_out": 3.1e5, "offshore": 1.2e5,
           "chronic": 8.0e5, "R_c": 1.4e5, "residual_rel_max": 3.2e-15},

  "cost": {"cost_used": 6.62e7, "n_projects": 3, "c0_star": null},

  "state": {"w_end_min": 3.2, "w_end_mean": 14.6, "exhausted_frac": 0.27}
}
```

- **删失语义**：`censored=true` 时 `value` 必须写 `null`，不许写 15 冒充观测到的失守时间；分位数统计要按右删失处理（Kaplan–Meier 或直接报"≤15 年"的计数）。
- `c0_star` 在 `cost_model=all_in` 下必须为 `null`。
- 任何字段算不出来（未跑）就删掉键，**不要填 0**——0 会被当成真实结果画进图。

### 4.3 `ledger.csv` 列（**沙量台账，T1 的载体**）

```
t, V_central, O_central, V_domain, O_domain, R_c_cum,
placed_cum, flux_inner_left_cum, flux_inner_right_cum,
flux_outer_left_cum, flux_outer_right_cum,
offshore_loss_cum, chronic_loss_cum, storm_injected_cum, recovery_cum,
residual, residual_rel
```

- **两个控制体，不能混**：中央研究区 $[-2500,2500]$（5 km）与全计算域 $[-4500,4500]$（9 km）。
  - `V_central` $=H\sum_{|x|\le2500}y_i\Delta x$；`V_domain` $=H\sum_{\text{all}}y_i\Delta x$（均为**增量**，$O(0)=0$）。
  - `flux_inner_*`：穿过 $x=\pm2500$ 的**体积**通量；`flux_outer_*`：穿过 $x=\pm4500$ 的。
  - 中央流出的沙可能仍在 2 km 缓冲区，**不能**当成已离开 9 km 域，更不能解释为"下游社区受害"。
- **单位**：体积通量累计 $=H\cdot F\cdot\Delta t$（m³）；$F$ 是 m²/yr。
- **全域闭合（含 $R_c$，符号 2026-11-11 修正）**：
  ```
  placed_cum = (V+O)_domain + flux_outer_left_cum + flux_outer_right_cum
             + offshore_loss_cum + chronic_loss_cum - R_c_cum
  residual   = placed_cum - (上面右端)
  ```
  中央闭合把 `flux_outer_*` 换成 `flux_inner_*`，并把 offshore/chronic 限定在中央。
  **$R_c$ 是减项**：它是"本该被侵蚀、但被下限挡住没真的侵蚀掉"的部分。
  更严格地写是 `− (R_c_end − R_c_start)`；初始 $V_{\text{abs}}=V_{\text{ref}}\ge V_{\min}$ ⇒ $R_c^{start}=0$，但测试里请显式记 $D_0$。
  自检：无补沙、无通量、$\lambda=0$、$L_c>0$ 且全程触底 ⇒ `R_c_cum = chronic_loss_cum`，残差 0。
- `residual_rel` 分母取 $\max(1\ \mathrm{m^3}, |placed\_cum|)$；T1 看最大值。
- 账本与验收场用 **float64**；`fields.npz` 的 float32 只用于展示，不能拿来重算收支。

**⚠ 关于 chronic_loss 与两跑相减**：$\rho_e$ 不依赖 $y$，所以基线/补沙两跑的 $\delta L_c=0$。差额收支里**没有"慢性汇吃掉补沙"这一项**；不要再画这个饼图份额。完整总场的收支本来就从初始状态成立，不需要"只在增量场成立"。

---

## 5. 验收测试清单（**建模手拥有，你必须全部通过**）

> **边界说明（2026-11-11）**：`tools/verify_contract.py` 只检查**文档结构与数值一致性**（57 项），**不运行模型**。真正的验收是 `tests/` 里 T1–T12 的**退出码测试**。
> 参考实现 `modeling/sanity/discrete_contract.py` 已全部改成 `assert`/`sys.exit`，可直接当第一个真测试的模板。


| # | 测试 | 做法 | 判据 | 预期数值 |
|---|---|---|---|---|
| **T1** | 沙量收支闭合 | 任意一次运行，读 `ledger.csv` | $\max\lvert\text{residual\_rel}\rvert<10^{-6}$ | 目标 $10^{-12}$，double 可达 $10^{-16}$ |
| **T2** | 对 erf 解收敛 | **光滑高斯初值**（$\sigma=200$ m）；主格式 **BE + $\Delta t\propto\Delta x$**；CN 可选，用 $\Delta t\propto\Delta x^2$；另用阶跃初值测 $L_1$/前沿 | **BE：** L2 比值 $\in[1.8,2.2]$；**CN（可选）：** $\in[3.5,4.5]$；阶跃的 $L_\infty$ 不判阶；另做**非负性检查** | 见下 |
| **T3** | 零源项/守恒 | (a) 均匀 $y$、$O=0$、$u=0$、零通量 ⇒ 全场不变；(b) 非均匀 $y$、零通量 ⇒ **总量守恒**（不比对 erf，零通量下 erf 不适用）；(b') 大域 + 开边界 ⇒ 对 erf 解（与 T2 共用算例）；(c) $O$ 单独指数衰减 | (a) $<10^{-12}$；(b) 质量 $<10^{-10}$；(c) $e^{-(k+\lambda)t}$ | — |
| **T4** | 网格/时间步一致性 | $dx=50$ vs $25$，同一情景确定性运行 | 关键指标（$T_{\text{first,fail}}^{w}$、留存率）差异 $<2\%$ | — |
| **T5** | 无风暴退化 | 配置：$\lambda_s=0$、$\lambda=0$、$u=0$、$\rho_e$ 均匀 2.3、$w_0$ 均匀 18、$w_{mgmt}=20$；与 NONDIM §7 对拍 | **解析 $T_p$**（仅 validation）相对误差 $<10\%$ | 见 §6 |
| **T6** | 单事件恢复 | 一次 $S_0$，无后续事件 | 最终回滩比例 $\to k/(k+\lambda)=0.87$；$t\to\infty$ 时 $O\to0$ | $0.87\pm0.001$ |
| **T7** | 边界通量 | 初始中心凸起、$u>0,D>0$ 的**已知外流**算例 | `open` 的 `flux_outer` 与半解析估计差 $<10\%$；`zeroflux` 的 `flux=0` | 不比较"留存率高低" |
| **T8** | 可复现 | 同一 seed 跑两次 | `results.json` 逐字节相同 + `fields.npz` md5 相同 | — |
| **T9** | **历史岸线诊断（Q3，不是通过/失败测试）** | 用 `_gis/hatteras_transects/Hatteras_Transects.dbf` 的 `LRR78_2002`/`LRR89_2002`（1308 条，含 DAS_km）；**先固定 transect 选择规则**（走廊范围、DAS 窗口、缺测/异常剔除），再算观测分布 | 报告观测均值/中位/区间与模型基线的**差异**；**2.5–4.5 m/yr 只是设计参考区间，不是通过标准**。不确定度按 4.5–4.8 m 披露 | 见 `资料/01_岸线侵蚀速率/USGS_岸线数据说明.md` |
| **T10** | **事件落在步边界/终点** | 三次运行：事件在 $t=1.00$（$\Delta t=0.02$ 的整倍数）、$t=1.01$（步中）、$t=T$（终点）；每次只放 1 个事件，关闭后续抽样 | (a) `n_events_applied=1`，不得 0 或 2；(b) 跳变后瞬时 $O=H\Delta y_k\phi$（误差 $<10^{-12}$ 相对）；(c) `storm_injected_cum` = 设计注入量；(d) 质量账本闭合（T1 同时成立） | 解析值 |
| **T11** | **非负性与退岸计数器** | 强制 $y$ 越过下限（$\rho_e$ 拉大 10 倍、$\lambda_s=0$）跑 5 年 | (a) $\min V \ge V_{\min}-10^{-9}$（**判 $V$，不是判 $y$**）；(b) 存在单元 $y<-w_0$ 且 **$y$ 未被裁剪**；(c) $R_c^{n}=\bigl[V_{\min}-V_{\text{abs}}^{n}\bigr]^{+}$（**当前亏空**，可恢复；不是时间积分、也不是历史峰值）；另报诊断量 $D_{\max}$；(d) 台账含 `R_c_cum` 后残差仍 $<10^{-6}$；(e) `risk_w` 在 $w\le0$ 时恒 1，而 `risk_b` 仍按 $d_b+y<m_s$ 计算（热点要到 $y<-20$ m 才为 1） | — |
| **T13** | **侵蚀后再补沙的守恒**（复核 P0） | 先 $\rho_e=12$ 跑 5 yr，再于 $t=5$ 一次性补 $1.5\times10^{7}$ m³，再跑 5 yr | (a) 台账残差 $<10^{-10}$（相对）；(b) $R_c$ 在补沙后**下降**；(c) $D_{\max}$ 单调不减 | 参考实现实测 rel $1.4\times10^{-13}$ |
| **T12** | **空间聚合与初始条件** | 用初始场直接算 $f_w(0),f_b(0)$；再用 $f\ge0.5$ 求 $T_{\text{first,fail}}$ | (a) $f_w(0)=0.3036$（解析 $1518/5000$）；**360 个单元、$dx=25$ 时离散值 0.3000（60 格），容差 $\pm0.005$**、$f_b(0)=0$；(b) 结果里**不存在** `T_first_any` 参与排序；(c) $T_{\text{safe,cum}}\in[0,15]$；(d) 删失标记 `censored=true` 与数值字段互斥 | 见 `MODEL_SPEC` §6.3 |

### T1/T3/T11 的参考实现与实测值（`modeling/sanity/discrete_contract.py`，130 行）

**先跑这个再写你的求解器**：它把"BE + 零通量 + O 子步 + V 下限 + R_c + 台账"这条最小链跑通，实测：

| 检查 | 实测 | 判据 |
|---|---|---|
| T3a 零源项零通量 | $\max\lvert\Delta y\rvert=7.5\times10^{-13}$ | $<10^{-12}$ |
| T3c O 指数衰减 | 相对误差 $2.8\times10^{-15}$ | 机器精度 |
| T11 V 触底 | $\min V=V_{\min}=90$，$y$ 未被裁剪 | 判 $V$ |
| T1 台账残差 | $\rho_e=3$: $1.1\times10^{-13}$；$\rho_e=12$: $1.6\times10^{-13}$ | $<10^{-6}$ |

> 关键：**残差公式里 $R_c$ 是减项**。把它写成加号，同一个算例会给出 $\sim10^{13}$ 的相对残差——这是最快的自检。
> 该脚本不含风暴/补沙/聚合，只验证离散与台账；不要直接拿它当求解器。


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
> **口径**：下表 $T_p$ 是**无风暴解析基准**下"滩宽 $w\ge20$ m"的时间，仅用于 T5 对拍，不是 MC 输出字段，也不是建筑净距风险；建筑净距口径见 `MODEL_SPEC` §6.2。

| 方案 | $\ell$ | $\Delta y_0$ | 中心 $T_p$ | 保护岸线·年 | 避免风险（热点场） |
|---|---|---|---|---|---|
| A 匀铺 | 5000 m | 20 m | **6.15 yr** | 26408 m·yr | 28086 m·yr |
| B 热点 | 1000 m | 100 m | **7.33 yr** | 24836 m·yr | **31320 m·yr** |
| C 单段 0.5 km（全部沙量集中） | 500 m | 200 m | **7.36 yr** | 24504 m·yr | **31412 m·yr** |

> **C 行是"把 100 万 m³ 全放在 0.5 km"**，不是五段方案的一段；五段等分每段 20 万 m³（$\Delta y_0=40$ m），必须单独算。
> **避免风险排序已修正**：B/C 高于 A；旧表把符号算反，已作废。

还有两条闭式：
- $T_{1/2}=0.2748\,\ell^2/D$（$\ell$=1000 m ⇒ 0.92 yr）
- 匀铺可行性 $\mathcal{V}_{\text{thr}}=H L(w_{\text{mgmt}}-w_{\min})$：**T5 基准配置** $w_{\min}=18$ m ⇒ $\mathcal{V}_{\text{thr}}=1.0\times10^{5}$ m³；**主算热点** $w_{\min}=16$ m ⇒ $2.0\times10^{5}$ m³。两者不要混用。

> 这些数字全部可由 `modeling/sanity/erf_prototype.py` 复现（跑一次 < 2 s）。**你的求解器在关掉风暴后必须落在这张表 ±10% 内**，否则先查换算（$H$ 用错是最常见原因）。

---

## 7. 实验清单与出图

### 7.1 必跑实验（对应 `SCENARIOS_STRATEGIES.md` §7）

| 编号 | 命令要点 | 输出 |
|---|---|---|
| E0 | `--scenario S{1,2,3} --strategy none` | 基线 $w(x,t)$、$E_0$ |
| E1 | `--scenario S1 --placement {uniform,hotspot,multi}` | 三方案对照表 + 沙去向堆叠图 |
| E2 | `--scenario {S1,S2,S3} --strategy once --mc 1000` | 四个时长指标分位、$E_w/E_b$ 分位 |
| E3 | **风暴时机**对照：early（0–5 yr）/ spread（每 2.5 yr）/ late（10–15 yr），各 6 次事件、同一强度分布、seed 固定 | 时机对照表（$T_{\text{first,fail}}^{w}$、min $w$、2042 年 $w$） |
| E4 | `--scenario {S1,S2,S3} --strategy {once,repeat,targeted,adaptive} --supply {local,external} --cost-model {all_in,marginal_plus_fixed}`。**主算 `all_in`（$c_1=27,c_0=0$）**；$c_0\in[0,10]$ M\$ 扫描**只在 `marginal_plus_fixed` 下做**，不得与 `all_in` 混算 | 三策略同约束对比 + 成本；`marginal_plus_fixed` 才输出 $c_0^*$ 交叉点 |
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
| F3 | 沙去向堆叠图（留存/出区/离岸，**仅三块**）随 $t$；慢性损失只在总场收支图中单列，不得与补沙差分混画 | 百分比 + 绝对量 |
| F4 | $T_{\text{first,fail}}^{w}$ 与 $T_{\text{first,fail}}^{b}$ 直方图（1000 次 MC） | 中位 + $P_{10}/P_{90}$ |
| F5 | 三方案对比条形图（$T_{\text{safe,cum}}^{w}$ + 保护岸线·年） | 同一纵轴口径 |
| F6 | tornado 图（OAT） | 参数名 + 基准值 |
| F7 | $\mathcal{V}$–$w_{\min}$ 相图 | $\mathcal{V}_{\text{thr}}$ 分界线 |
| F8 | 三策略 $E$ vs $c_0$ 曲线（**仅 `marginal_plus_fixed`**；`all_in` 不画此轴） | 交叉点标注 |

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
| 时长 $T_{\text{first,fail}}$ 是 `inf` | 阈值从未被穿越（$\Delta y_0$ 太大或 $\rho_e=0$） | 加保护：超过 `t_end` 记为 `>=15`，**不要**记 inf |

---

## 9. 交付给建模手的东西

1. `tests/` 全部通过的截图/日志（T1–T10，逐条）；
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

> 如果时间不够：**砍 E5 的 Sobol，保 OAT；砍 F1 的 3D，保热图**。不要砍 T1–T10 —— 那是"可信"的唯一凭证。
