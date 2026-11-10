# VALIDATION_PLAN.md — 标定、验证、敏感性与可辨识性（阶段 2）

> 目标：回答 Q3 的五件事 —— 参数有出处、**验证（能做到的是跨资料一致性检查，不是严格独立验证）**、敏感性、可辨识性、不完美数据的影响、以及"分不开机制时缺什么测量"。
> 原则：**验证集绝不参与标定**；分不开就说分不开，不许用漂亮的 $R^2$ 掩盖。

---

## 1. 数据分块（先画线，再跑数）

| 块 | 内容 | 用途 | 规模 |
|---|---|---|---|
| **CAL-1 长期速率** | NC DCM/DEQ 长期平均年侵蚀率（逐段或分区） | 标定 $\rho_e(x)$（先验） | 全岸段表 |
| **CAL-2 波浪气候** | $H_s$、$T_{\text{peak}}$、波向（浮标/再分析） | 计算 $D$（不是标定 $D$） | 月度统计 |
| **CAL-3 工程记录** | 补沙方量、成本、实施时刻 | 设定 $\mathcal{V}$、$c_1$ | 少量项目 |
| **CAL-4 风暴年表** | 历史风暴路径/强度/日期 | 设定 $\lambda_s$ 与强度分布 | 数十年事件表 |
| **VAL-1 岸线序列** ★ | **USGS OFR 2015-1002**：Hatteras Island 1978–2002 的 **14 条 HWL 岸线**（shapefile；不确定度 DBF=1.6 m，报告/元数据=4.5–4.8 m，按 4.5–4.8 主量级）；未参与 $\rho_e$ 标定 | **跨资料一致性检查**（不是严格 out-of-sample） | 14 个时刻 × 全岛 |
| **VAL-2 事件响应** ★ | W11（Matthew 2016, Nags Head, 1.43M cy ≈ 6.8 m）；W10（2025 Buxton, 平均 20.7 / 最大 43 m） | **验证** 风暴模块的量级 | 2 个事件 |
| **VAL-3 守恒/退化** | 沙量收支、零源项、erf 极限 | **验证** 代码正确性 | 合成 |

**分块铁律**：CAL-1 用的是"速率"（斜率），VAL-1 用的是"位置"（水平）。用斜率标定、用位置做**跨资料一致性检查**，**信息不完全重叠**；但在证明原始影像/处理链独立之前，不要称它为"independent validation"。

> 若数据只够做"拟合优度"而没有真正独立的验证集，**必须明白写出来**："我们无法进行严格意义上的 out-of-sample validation；以下为 consistency check"，并给出补测方案（§7）。这比假装有验证强得多。
>
> **2026-11-09 更新**：VAL-1 有真实数据——USGS 1978–2002 的 14 条岸线在 `资料/06_原始摘录/_gis/`，未参与 $\rho_e$ 标定。但**不能据此宣布"独立方法验证"**：速率本就是从岸线位置算出来的，机构不同也不保证原始影像独立；两组资料共享哪些航片/日期/处理链尚未查清。正确措辞是 **"cross-source consistency check"**：不同发布方、不同指标（HWL vs DEQ 的 wet-dry/endpoint）、不同时段；若无法证明影像独立，不能写 "independent validation"。**也不是 out-of-sample 预测验证**（时段 1978–2002 不覆盖 2027–2042）。
>
> **VAL-1 的具体做法（给编程手）**：以 USGS 的 baseline 为参考线，在 Rodanthe 段每 50–100 m 取 transect，对 14 个时刻的岸线求交点，做线性回归得 $1978$–$2002$ 的 LRR；与 DEQ 的段平均、与我们模型的"无补沙基线"对比。**不要**用我临时按纬度截取的粗算值（那只用于确认数据可用）。

---

## 1.5 L0 无补沙基线（A4 裁决实验，**必须先跑**）

目的有两个：裁决"长期速率是否已含风暴"，并顺带标定热点形状参数 $a_h$。

1. 关补沙（$I=0$）；主算参数 $\rho^{\text{bg}}=1.18$ m/yr（`MODEL-APPROX`）、$\lambda_s=0.4$、$\mathbb{E}[\Delta y]=10.0$（对数正态均值）；
2. 跑 15 年 MC（$\ge200$ 次），统计**走廊平均**与**热点区**的总岸线变化率；
3. 与 DEQ 对照：段平均 1.62–1.83 m/yr、热点峰值 3.8–4.0 m/yr；
4. 不吻合时**只调 $a_h$**（0.5–2.0），**不动 $\rho^{\text{obs}}$**（那是观测）；
5. 再用"不去重"的 $\rho^{\text{obs}}=1.7$ 跑一次，报出双计数的**偏差方向与大小**。

判据：去重方案的总速率应落在 DEQ 区间内；不去重方案应系统性偏高约 $\rho^{\text{storm}}/\rho^{\text{obs}}\approx25\%$。
若不成立，说明 $\lambda_s$ 或 $\lambda/(k+\lambda)$ 的取值有问题，回去改风暴参数而不是改速率。


## 2. 标定目标函数

$$
J(\theta)=\sum_{i}\Bigl[\frac{y^{\text{mod}}_i-y^{\text{obs}}_i}{\sigma_i}\Bigr]^2
+\sum_j\Bigl[\frac{\theta_j-\theta_j^{0}}{\sigma^{0}_j}\Bigr]^2
$$

- 第一项：位置残差（VAL 不用，仅 CAL 用）；
- 第二项：**先验正则**（贝叶斯式）。这是本题的关键技巧：数据少，就必须用文献先验约束，否则参数飞到无意义的角落。
- $\theta=\{D,u,\lambda_s,\Delta y_{\text{ref}},k,\lambda\}$；$\rho_e$ 由 CAL-1 **直接给定**，是**固定先验输入、不参与拟合**（MC 里对 $\rho_e$ 抽样只是传播不确定性，不是标定）。

**优化**：差分进化（全局）+ Nelder-Mead 精修；或用 MCMC（emcee / PyMC）给后验。**必须报后验，不只报点估计**。

---

## 3. 验证指标（三个层次，别只报一个 $R^2$）

| 层次 | 指标 | 判据 | 说明 |
|---|---|---|---|
| L1 趋势 | 岸线变化率的偏差 $b=\overline{\dot y^{\text{mod}}-\dot y^{\text{obs}}}$ | $\lvert b\rvert<0.5$ m/yr | 最容易过，但最不说明问题 |
| L2 位置 | RMSE（m）、MAE | RMSE < 2× 观测不确定度（若岸线测量 $\sigma\approx3$ m ⇒ RMSE<6 m） | 主指标 |
| L3 变率 | 岸线标准差之比 $\sigma_{\text{mod}}/\sigma_{\text{obs}}$ | 0.5–2.0 | **防止"平滑得像直线"** —— 很多队伍在这里翻车 |
| L4 事件 | 单次风暴后退量的相对误差 | <50%（量级对即可） | 数据极少，只做量级校验 |

> **L3 是最容易被忽略、也最能区分队伍的一条**：模型如果只复现趋势而抹平了年际波动，$R^2$ 会很好看，但它在物理上是错的（把风暴噪声吃掉了）。论文里放这一条会明显加分。

**L0 基线速率核对（Q-37 专用，先做）**：无补沙、无风暴、只有 $\rho_e$ 时，15 年后退量应为 $\rho_e\times15$；加入风暴后，按口径 (i) 总后退率应落在 **1.9–2.1 m/yr**（背景段；`MODEL_SPEC` §3.5 估计风暴净贡献 +0.2–0.4）。风暴净贡献是
$$\lambda_s\,\mathbb{E}[\Delta y_{\text{actual}}]\,\frac{\lambda}{k+\lambda},$$
**不是**把 $\lambda_s$ 直接加到 $\rho_e$ 上（量纲不同）。若总速率 $>2.2$ m/yr 或比 DEQ 高 $>30\%$，说明双计数，按 `MODEL_SPEC` §3.5 的口径 (ii) 修正。**这一条不需要任何新数据，跑一次基线即可。**

---

## 4. 敏感性分析

### 4.1 一次一因子（OAT）—— 先做，便宜

| 参数 | 基准 | 扫描 | 看的输出 |
|---|---|---|---|
| $D$ | 3e5 | 1e5 → 8e5（×8） | $T_{\text{first,fail}}^{w}$、留存率 |
| $H$ | 10 | 8 → 12 | $\Delta y_0$、$T_{\text{first,fail}}^{w}$ |
| $\rho_e$（背景） | 1.7 | 1.2 → 2.1 | $T_{\text{first,fail}}^{w}$、$E_w/E_b$ |
| $a_h$（热点放大） | 1.2 | 0.5 → 2.0 | 热点达标速度 |
| $u$ | 50 | 0 → 150 | 沙去向（滞留 vs 出区） |
| $\lambda_s$ | 0.4 | 0.2 → 0.8 | $E_w/E_b$ 的上尾 |
| $\Delta y_{\text{ref}}$ | 8 | 4 → 12 | 同上 |
| $k$ | 0.667 | 0.33 → 2.0 | 恢复红利期长度 |
| $\lambda$ | 0.1 | 0.02 → 0.3 | 留存率 |
| $w_{0,\text{far}}$（远场） | 25 | 20 → 40 | $T_{\text{first,fail}}^{w}$、$E_w/E_b$ |
| $w_{\text{mgmt}}$ | 20 | 12 → 32 | $T_{\text{first,fail}}^{w}$、$E_w/E_b$ |
| $V_{15,\text{total}}$ | 5.0e6 | 3.5 → 6.8 e6 | 三策略排序、用沙量 |
| $V_{\text{event,max}}$ | 2.9e6 | 1.5 → 3.5 e6 | 单次方案可行性 |
| $S_{\text{borrow,total}}$ | 2.45e6 | 1.5 → 3.2 e6（另做 $a_{\text{borrow}}=0.8$ 点） | 本地沙可行性、A/B/C 排序 |
| $c_0$（仅 `marginal_plus_fixed`） | 0 | 0 → 10 e6 | $c_0^*$ 交叉点；`all_in` 下不扫 |

### 4.2 全局敏感性（Salib / Sobol'，二阶）

**必须做的三组**：
1. $(D,\rho_e,u)$ → $T_{\text{first,fail}}^{w}$、留存率（扩散/侵蚀/漂移三分天下）
2. $(\lambda_s,\Delta y_{\text{ref}},k)$ → $E_w/E_b$、$T_{\text{first,fail}}^{w}$ 的 $P_{10}$（风暴组）
3. $(V_{15,\text{total}},V_{\text{event,max}},S_{\text{borrow,total}},c_1)$ → 三策略的**排序是否稳定** ★ 最关键；分别跑 `local`/`external` 两种沙源。$c_0^*$ **只在 `marginal_plus_fixed` 成本结构下**输出（$c_0\in[0,10]$M），`all_in` 主算没有 $c_0^*$，不得把两者混成一条曲线。

> 第 3 组的结论决定 Q5 能不能给"推荐策略"。**如果策略排序在参数范围内翻转，就必须说"在该供沙/成本配置下 A 优于 B，但排序对 X 敏感"，而不是硬给一个策略。**

---

## 5. 可辨识性（Q3 的硬骨头）

### 5.1 结构可辨识性（先想清楚，再算）

问："这两个参数能不能同时改动而让输出不变？"

| 情形 | 是否可辨识 | 理由 |
|---|---|---|
| $D$ vs $\lambda$ | **可辨识** | $D$ 摊开（形状变、总量不变），$\lambda$ 丢失（总量减少） |
| $D$ vs $u$ | **可辨识** | 一阶矩 vs 二阶矩 |
| $\lambda_s$ vs $\Delta y_{\text{ref}}$ | **不可辨识**（年际数据下） | 只进乘积 $\lambda_s\overline{\Delta y}$ |
| $\rho_e$ vs $\lambda_s$ | **不可辨识**（只有长期速率时） | 长期速率只约束 $\rho_e+\lambda_s\mathbb{E}[\Delta y]\lambda/(k+\lambda)$；两者都让岸线匀速后退 |
| $\Delta y_{\text{ref}}$ vs $\gamma$ vs $w_s$ | **弱** | 都需要事件级强度-响应配对 |
| $k$ vs $\lambda$ | **弱** | 都需要灾后时间序列 |

### 5.2 实用可辨识性（跑出来的）

1. 计算 Fisher 信息矩阵 / 近似 Hessian 的条件数 $\kappa$；$\kappa>10^{4}$ ⇒ 强共线性；
2. 画两两**剖面似然**（profile likelihood）：固定一个、扫另一个，看似然脊是否"山脊"而非"山峰"；
3. 报**后验相关系数矩阵**（尤其 $\rho(D,\lambda)$、$\rho(\lambda_s,\Delta y_{\text{ref}})$）。

### 5.3 报告方式（写进论文的一段模板）

> "The diffusion coefficient and the offshore-loss rate are individually identifiable because they act on different moments of the post-nourishment profile (spreading vs. total volume). In contrast, the storm arrival rate and the per-storm erosion scale enter the annual budget only as a product; with annual shoreline data we can constrain $\lambda_s\overline{\Delta y}$ to ±X% but cannot separate the two without event-scale surveys."

---

## 6. 不完美数据的影响

| 数据缺陷 | 传播方式 | 定量做法 |
|---|---|---|
| 岸线测量误差 $\sigma_y\approx2$–5 m | 直接加到 $\rho_e$ 的估计误差 | 蒙特卡洛：给观测加噪声，看 $\rho_e$ 的分布宽度 |
| 速率时段不一致（1930s vs 1998–2022） | $\rho_e$ 系统偏差可达 2× | 用两组分别跑，报差异 |
| 岸线"位置"与"体积"口径不同 | $H$ 的不确定 | $H\in[8,12]$ 的敏感性即覆盖 |
| 风暴记录漏记（小事件） | $\lambda_s$ 低估 | 用"观测到的最大事件"反推截断阈值 |
| 补沙方量是"设计方量"而非"实投方量" | $\mathcal{V}$ 有 5–15% 偏差（松方/压实） | $\mathcal{V}$ 改 0.9/1.0/1.1 倍做敏感性 |
| 成本是数年平均值 | $c_1$ 有 ±30% 漂移 | 已在 range 内 |

---

## 7. "分不开机制"时缺什么测量（Q3 必答项）

按**性价比**排序，写进论文 §Discussion：

| 缺口 | 需要的测量 | 频率/规模 | 能解决什么 |
|---|---|---|---|
| **事件级响应** ★ | 每次风暴前后 1–2 周的岸线/剖面（RTK-GPS 或无人机摄影测量） | 每年 3–5 次，共 2–3 年 | 分离 $\lambda_s$ 与 $\Delta y_{\text{ref}}$；标定 $\gamma$ |
| **恢复曲线** ★ | 一次风暴后的剖面序列（+1 周、+1 月、+3 月、+6 月、+1 年） | 1–2 个事件即可 | 分离 $k$ 与 $\lambda$ |
| **沿岸输沙** | 波浪方向 + 岸线曲率 → 反演 $Q$；或示踪沙 | 季度 | 直接定 $u$ 与 $D$ |
| **剖面深度** | 每条剖面测到闭合深度（$h_*\approx8$ m） | 年度 | 定 $H$，去掉最大的换算不确定 |
| **粒径** | 补沙源与原地 $D_{50}$ 对比 | 一次 | 检验 A7（同质假设） |

> **一句话**："如果只能再加一项测量，加**事件级灾后岸线**——它同时解锁风暴频率、单事件侵蚀量和恢复率三个参数。"

---

## 8. 敏感性结果的呈现规格（给论文手）

- 一张 **tornado 图**：15 个 OAT 参数对 $T_{\text{first,fail}}^{w}$ 的影响，按幅度排序；
- 一张 **Sobol 一阶/二阶条形图**：$D$、$\rho_e$ 通常占主导 —— 这本身就是结论（"该测的是剖面与波浪，不是补沙量"）；
- 一张 **策略排序稳定性图**（仅 `marginal_plus_fixed`）：横轴 $c_0$，纵轴三策略的 $E$，看交叉点；`all_in` 主算另给"沙源 local/external × 策略"的排序表，不画 $c_0$ 轴。
- 所有图必须标：参数版本（`params.yaml` 的 version 字段）+ 数据类型（MODEL / ASSUME）。

---

## 9. 验收（本文件对应的门禁）

- [ ] 标定集/验证集在跑数**之前**已固定并写入本文件（防事后挑选）
- [ ] L1–L4 四项指标全部报出（缺项要写理由）
- [ ] OAT 15 项 + Sobol 3 组跑完
- [ ] 后验相关系数矩阵报出，$\lvert\rho\rvert>0.8$ 的参数对逐个讨论
- [ ] §7 的补测清单进了论文 Discussion
- [ ] 所有数字在 `ledger/claims.csv` 有行
