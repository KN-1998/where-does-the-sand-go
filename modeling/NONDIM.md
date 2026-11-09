# NONDIM.md — 无量纲化与解析基准（阶段 1 门禁）

> 用途：① 给编程手**可对拍的解析解**；② 给论文**尺度直觉**；③ 让"补沙能买多久"有一个闭式答案，后面数值结果必须落在它的量级里。
> 全部数值与 `modeling/sanity/erf_prototype.py` 的输出一致（见 `sanity/results.txt`），可复算。

---

## 1. 特征尺度

| 尺度 | 定义 | 取值（基准算例） | 含义 |
|---|---|---|---|
| 沿岸长度 $\ell$ | 投放段长 | 500–5000 m | 补沙"铺多宽" |
| 扩散时间 $T_D$ | $\ell^2/D$ | 1.7–83 yr | 沙子沿岸摊开的时间 |
| 恢复时间 $\tau_{\text{rec}}$ | $1/k$ | 1.5 yr | 风暴沙坝回滩 |
| 损失时间 $\tau_{\text{loss}}$ | $1/\lambda$ | 10 yr | 离岸永久损失 |
| 风暴间隔 $\tau_s$ | $1/\lambda_s$ | 2.5 yr | 侵蚀性事件平均间隔 |
| 慢性侵蚀时间 $\tau_e$ | $w_0/\rho_e$ | 6–8 yr | 无补沙时滩宽耗尽的时间 |
| 对流时间 $T_u$ | $\ell/u$ | 10–100 yr | 岸线特征体漂出走廊 |

**基准取值**（`params.yaml` 为准）：$H=h_*+B=10$ m，$D=3\times10^{5}$ m²/yr，$\rho_e=3$ m/yr，$u=50$ m/yr，$k=0.67$ yr⁻¹，$\lambda=0.1$ yr⁻¹。

---

## 2. 无量纲参数

$$
\Pi_1=\frac{T_D}{\tau_e}=\frac{\ell^2\rho_e}{D\,w_0}\ \text{（扩散 vs 慢性侵蚀，谁先吃掉补沙）}
$$

$$
\Pi_2=\frac{D}{\ell\,u}=\frac{1}{\mathrm{Pe}}\ \text{（扩散 vs 净漂移）},\qquad
\mathrm{Pe}=\frac{u\ell}{D}
$$

$$
\Pi_3=\frac{\tau_{\text{rec}}}{\tau_s}=k\lambda_s\ \text{（恢复 vs 下一个风暴）}
$$

$$
\Pi_4=\frac{\Delta y_0}{w_{\text{crit}}-w_0}\ \text{（投放幅度 vs 需求）}
$$

| 情形 | $\Pi_1$ | 含义 | 保护期由谁决定 |
|---|---|---|---|
| 局部补沙（$\ell\lesssim1$ km） | $\ll1$ | 扩散快 | **扩散 + 慢性侵蚀** |
| 长段补沙（$\ell\gtrsim4$ km） | $\gg1$ | 扩散慢 | **慢性侵蚀（$\rho_e$）** |
| $\Pi_3\gg1$ | — | 上一场还没恢复下一场就来 | **风暴叠置**，$O$ 累积、$\lambda O$ 变大 |

$\Pi_1$ 是本题最重要的一条：**它决定了"补沙是被摊开吃掉的，还是被慢性侵蚀吃掉的"**，两种死法对应完全不同的管理对策（前者要加长投放段或做沙丘，后者说明补沙本身治不了根）。

---

## 3. 解析基准 A：补沙脉冲的 erf 解

忽略风暴、忽略空间变化的 $\rho_e$（或先取 $\rho_e=0$），一维扩散方程

$$
\frac{\partial y}{\partial t}=D\,\frac{\partial^2 y}{\partial x^2},
\qquad
y(x,0)=\begin{cases}\Delta y_0,&|x|\le \ell/2\\0,&\text{else}\end{cases}
$$

的精确解（无限域）：

$$
\boxed{\;y(x,t)=\frac{\Delta y_0}{2}\Bigl[\operatorname{erf}\!\Bigl(\frac{x+\ell/2}{2\sqrt{Dt}}\Bigr)-\operatorname{erf}\!\Bigl(\frac{x-\ell/2}{2\sqrt{Dt}}\Bigr)\Bigr]\;}
$$

中心点：$\;y(0,t)=\Delta y_0\operatorname{erf}\!\bigl(\ell/(4\sqrt{Dt})\bigr)$。

**半衰期**（中心点降到投放幅度一半）：

$$
\boxed{\;T_{1/2}=\frac{0.2748\;\ell^2}{D}\;}
$$

| $\ell$ | 500 m | 1000 m | 2000 m | 5000 m |
|---|---|---|---|---|
| $T_{1/2}$ | 0.23 yr | **0.92 yr** | 3.66 yr | 22.9 yr |

> **论文可以直说的一句**：补沙的"寿命"按 $\ell^2/D$ 缩放——**投放段长翻倍，寿命变四倍；扩散系数翻倍，寿命减半**。这是 $\ell$ 比总方量更值钱的根据。

---

## 4. 解析基准 B：保护期闭式解与"匀铺可行性"判据

设阈值宽度 $w_{\text{crit}}$、初始宽 $w_0$，需求幅度 $\Delta y_{\text{req}}=w_{\text{crit}}-w_0$（>$0$ 才需要补）。

### 4.1 纯扩散（$\rho_e=0$）

$$
\boxed{\;T_p=\frac{\ell^2}{16D\,\bigl[\operatorname{erf}^{-1}(\Delta y_{\text{req}}/\Delta y_0)\bigr]^2}\;}
$$

### 4.2 加慢性侵蚀 $\rho_e>0$

$y(0,t)=\Delta y_0\operatorname{erf}(\ell/(4\sqrt{Dt}))-\rho_e t=\Delta y_{\text{req}}$ 的一维求根。两个极限：

- 扩散主导（$\ell$ 小）：$T_p\approx$ 4.1 的结果；
- 侵蚀主导（$\ell$ 大，$\operatorname{erf}\to1$）：$T_p\approx\dfrac{\Delta y_0-\Delta y_{\text{req}}}{\rho_e}$（就是"多出来的沙除以侵蚀率"）。

### 4.3 匀铺可行性判据（★ 本篇最有用的一个式子）

总沙量 $\mathcal{V}$ 均匀铺满走廊长度 $L$，得到的幅度是 $\Delta y_0=\mathcal{V}/(HL)$。要**让整段都达标**，必须

$$
\boxed{\;\mathcal{V}\ \ge\ \mathcal{V}_{\text{thr}}=H\,L\,\bigl(w_{\text{crit}}-w_{\min}\bigr)\;}
$$

其中 $w_{\min}$ 是走廊内最窄处的滩宽。

- $\mathcal{V}\ge\mathcal{V}_{\text{thr}}$ ⇒ 匀铺可行，再比"持续多久"；
- $\mathcal{V}<\mathcal{V}_{\text{thr}}$ ⇒ **匀铺必然留下不达标岸段**，必须集中投放（策略 C）。

算例：$H=10$ m，$L=5000$ m，$w_{\text{crit}}=20$ m，$w_{\min}=16$ m ⇒ $\mathcal{V}_{\text{thr}}=2.0\times10^{5}$ m³。
本例 $\mathcal{V}=1.0\times10^{6}$ m³ $\gg$ 阈值 ⇒ 匀铺可行。

> 这条判据回答了 Q2 的一半："什么时候两种布置的差别是本质的（过不了阈值）vs 只是效率差别"。编程手应把它做成 $\mathcal{V}$–$w_{\min}$ 平面上的**相图**。

---

## 5. 解析基准 C：沙量守恒恒等式（编程手 T1 验收用）

$$
\mathcal{V}_{\text{placed}}(t)
=\underbrace{\int_{\text{区内}}\!\!\bigl[(V+O)-(V_0+O_0)\bigr]dx}_{\text{区内净增}}
+\underbrace{\int_0^t\!\bigl[Q(L_b)-Q(-L_b)\bigr]d\tau}_{\text{边界净流出}}
+\underbrace{\int_0^t\!\!\int \lambda O\,dx\,d\tau}_{\text{永久离岸}}
+\underbrace{\int_0^t\!\!\int L_c\,dx\,d\tau}_{\text{慢性损失}}
$$

离散实现必须满足：**相对残差 $<10^{-6}$**（双精度下可达 $10^{-12}$，留 6 个量级余量）。

⚠ 关键细节：$L_c$ 会吃**背景沙**，所以上式只在"补沙增量场"上成立。实现方式：跑两遍（基线/补沙）相减，或在代码里同时追踪"总场"与"增量场"，用增量场做守恒检查。

---

## 6. 数值格式与收敛（已实测）

参考原型用 FTCS 显式格式验证 erf 解（$\ell=1000$ m，$\Delta y_0=100$ m，$t=1$ yr）：

| $\Delta x$ | $r=D\Delta t/\Delta x^2$ | $L_\infty$ 相对误差 | 质量相对变化 |
|---|---|---|---|
| 100 m | 0.40 | $4.02\times10^{-2}$ | $4.8\times10^{-8}$ |
| 50 m | 0.40 | $2.05\times10^{-2}$ | $2.8\times10^{-8}$ |
| 25 m | 0.40 | $1.04\times10^{-2}$ | $1.4\times10^{-8}$ |

读数：
1. **误差按一阶收敛**（$\Delta x$ 减半误差减半）——因为初始条件是不连续的阶跃，$L_\infty$ 范数下一阶是**理论预期**。若用平滑初始条件（如余弦型投放），应收二阶。
2. **质量守恒到 $10^{-8}$**（只是浮点累积），说明零通量 FTCS 的守恒性没问题。
3. 生产代码建议：**隐式（Crank–Nicolson 或向后 Euler）+ 守恒有限体积**，允许 $\Delta t$ 大得多；显式格式仅用于对照测试。

**收敛性验收标准**（写进 CODER_SPEC）：
- 对 erf 解，$\Delta x$ 减半时 $L_2$ 误差比 $\in[1.9,\,2.1]$（二阶格式）；
- 与本文 §3 的解析解在 $t\le1$ yr（边界未影响）上相对误差 $<10^{-2}$（$\Delta x=50$ m）。

---

## 7. 三方案对照的参考数值（编程手对拍用）

参数：$\mathcal{V}=10^{6}$ m³，$H=10$ m，$D=3\times10^{5}$ m²/yr，$\rho_e=3$ m/yr，$w_0=18$ m（均匀），$w_{\text{crit}}=20$ m，忽略风暴。

| 方案 | $\ell$ | $\Delta y_0$ | 中心 $T_p$ | 保护岸线·年 |
|---|---|---|---|---|
| A 匀铺 5 km | 5000 m | 20 m | 5.01 yr | **21172 m·yr** |
| B 热点 1 km | 1000 m | 100 m | 6.17 yr | 19426 m·yr |
| C 5 段 × 0.5 km | 500 m | 200 m | 6.21 yr | 19150 m·yr |

**怎么读这张表（写进论文的关键句）**：
- **中心保护期**：B、C 更长（投放幅度大）；
- **走廊总收益**：A 更高（覆盖长）；
- 两者不矛盾：**"中心能撑多久"与"保住多少公里"是两个不同的目标函数**。Q5 必须明确选哪个做目标，否则三种策略无法排序。

**投放宽度扫描**（同一总方量）：保护岸线·年在 $\ell\approx3.8$ km 处取最大（21955 m·yr），$\ell=400$ m 时只有 19120。也就是说，**在"整段都低于阈值"的配置下，铺太窄是浪费**（沙堆在不需要的地方）；但一旦 $\mathcal{V}<\mathcal{V}_{\text{thr}}$，这条结论反转——因为窄投放是唯一能让热点达标的办法（§4.3）。

---

## 8. 风暴项的量级自检

单次风暴的等效后退 $\Delta y_k$ 与岸线-体积换算：

$$
S_k=H\,\Delta y_k\ \ [\text{m}^2]
$$

取 $\Delta y_k=10$ m ⇒ 每米岸线 100 m³ 沙被搬到沙坝；1000 m 投放段 ⇒ $10^{5}$ m³。
对照 $O$ 的恢复：$\tau_{\text{rec}}=1.5$ yr ⇒ 恢复通量 $kO=100/1.5\approx67$ m²/yr，约为慢性侵蚀 $\rho_e H=30$ m²/yr 的两倍——**风暴后头两年是"恢复红利期"**，模型必须体现，否则会低估保护期（题面 D-3 考点）。

---

## 9. 与解析解的对拍清单（阶段 1 门禁）

- [x] erf 解公式与原型一致（`sanity/results.txt` §[1][2]）
- [x] $T_{1/2}=0.2748\ell^2/D$ 与数值解一致
- [x] 含沉汇 $T_p$ 的根与闭式（$\rho_e=0$）在 $\rho_e\to0$ 时连续
- [x] 质量守恒 $<10^{-6}$（实测 $10^{-8}$）
- [x] 匀铺可行性判据 $\mathcal{V}_{\text{thr}}$ 有解析式且与原型输出一致
- [ ] **待编程手**：全模型（含风暴）在 $\lambda_s=0$、$\rho_e=0$ 时退化回 erf 解（T2 验收）
