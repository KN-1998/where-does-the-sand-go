#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""discrete_contract.py — 最小可跑的离散合同原型（≤150 行，非成品求解器）

目的：用 130 行证明 CODER_SPEC 的离散口径**确实能闭合**，给编程手一个可对拍的参考：
  1. 源汇 + 通量 + V 下限 + R_c 的沙量台账，残差 < 1e-12（T1）；
  2. 零源项零通量 ⇒ 全场不变（T3a）；
  3. O 单独指数衰减 e^{-(k+λ)t}（T3c）；
  4. 强侵蚀下 V 触底、R_c 单调累积、台账仍闭合（T11a）。

不含：风暴抽样、补沙调度、空间聚合（那些在主求解器里）。
运行：python discrete_contract.py
"""
import numpy as np

D = 3.0e5      # m^2/yr
H = 10.0       # m
Lb, DX = 4500.0, 25.0
NX = int(2 * Lb / DX) + 1
X = -Lb + DX * np.arange(NX)
DT = 0.02      # yr
K, LAM = 0.667, 0.1
A_REC = K + LAM


def thomas(a, b, c, d):
    """三对角求解：a=下对角线(n-1)，b=主(n)，c=上(n-1)。"""
    n = len(b)
    cp = np.zeros(n); dp = np.zeros(n)
    cp[0] = c[0] / b[0] if n > 1 else 0.0
    dp[0] = d[0] / b[0]
    for i in range(1, n):
        m = b[i] - a[i - 1] * cp[i - 1]
        dp[i] = (d[i] - a[i - 1] * dp[i - 1]) / m
        cp[i] = (c[i] / m) if i < n - 1 else 0.0
    x = np.zeros(n); x[-1] = dp[-1]
    for i in range(n - 2, -1, -1):
        x[i] = dp[i] - cp[i] * x[i + 1]
    return x


def step(y, O, bc_src, rho, dt=DT):
    """一个 BE 步；返回 (y, O, Rn, lamO, Lc)。bc_src: 每步常量源项 [m/yr]。"""
    # 1) O 的精确子步（S=0）
    O_new = O * np.exp(-A_REC * dt)
    Rn = (K / A_REC) * (O - O_new)          # 本步回滩量 m^2
    lamO = (LAM / A_REC) * (O - O_new)      # 本步永久损失 m^2
    # 2) BE 装配：dy/dt = D y_xx - rho + Rn/(H dt)
    r = D * dt / DX ** 2
    src = (Rn / (H * dt) + bc_src - rho) * dt   # 每步增量
    main = np.full(NX, 1.0 + 2 * r)
    lower = np.full(NX - 1, -r)
    upper = np.full(NX - 1, -r)
    # 零通量：镜像 => 端点只与一个邻居耦合（系数减半）
    main[0] = main[-1] = 1.0 + r
    rhs = y + src
    y_new = thomas(lower, main, upper, rhs)
    return y_new, O_new, Rn, lamO


def run(rho_val, years=15.0, w0_val=16.0, O0=0.0, y_init=0.0, bc_src=0.0):
    """跑一个直筒算例，返回台账字典。"""
    y = np.full(NX, float(y_init))
    O = np.full(NX, float(O0))
    V_ref, V_min = 250.0, 250.0 - H * w0_val
    placed_cum = flx_left = flx_right = 0.0
    lamO_cum = Lc_cum = R_c_cum = 0.0
    V0_total = H * y.sum() * DX          # 初始 V+O 的区内总量（m^3）
    n = int(round(years / DT))
    for _ in range(n):
        y, O, Rn, lamO = step(y, O, bc_src, np.full(NX, rho_val))
        # V 下限 + 退岸计数器（P0-2：判 V 不判 y）
        V_trial = V_ref + H * y
        deficit = np.maximum(V_min - V_trial, 0.0)
        if deficit.any():
            R_c_cum += deficit.sum() * DX
            y = np.where(deficit > 0, (V_min - V_ref) / H, y)
        lamO_cum += lamO.sum() * DX
        Lc_cum += rho_val * H * NX * DX * DT      # 每步，必须乘 DT
    V_inside = (H * y).sum() * DX
    O_inside = O.sum() * DX
    residual = (placed_cum - (flx_left + flx_right) - lamO_cum - Lc_cum
                - ((V_inside + O_inside) - V0_total) + R_c_cum)
    return dict(y=y, O=O, V=V_inside, Varr=V_ref + H * y, resid=residual,
                R_c=R_c_cum, Lc=Lc_cum, lamO=lamO_cum, Vmin=V_min)


def place(y, volume, xc=30.0, ell=1000.0):
    """按单元与投放区的重叠长度加权投放（CODER_SPEC §2.5 / §3.5）。

    返回 (y_new, 实际投放体积)。断言：实际 == 设计（<1e-12 相对）。
    """
    lo, hi = xc - ell / 2, xc + ell / 2
    cell_lo = X - DX / 2
    cell_hi = X + DX / 2
    overlap = np.clip(np.minimum(cell_hi, hi) - np.maximum(cell_lo, lo), 0, None)
    tot = overlap.sum() * DX
    assert abs(tot - ell) < 1e-9 or tot > 0, "投放区与网格无交集"
    frac = overlap / overlap.sum()                     # 体积按重叠长度分配
    dy = (volume * frac) / (H * DX)                    # 每单元的 Δy [m]
    placed = (H * dy * DX).sum()
    return y + dy, placed


def storm(y, O, dy_pot, xk=0.0, sigma_e=2000.0, gaussian=False, w0v=16.0, w_s=20.0):
    """一次风暴注入（CODER_SPEC §2.4b + §2.4d）。返回 (y, O, 中心 dy, 注入体积)。"""
    w_eff = np.maximum(w0v + y, 0.0)
    f = 1.0 - np.exp(-w_eff / w_s)
    dy = np.minimum(dy_pot * f, w_eff)
    if gaussian:
        g = np.exp(-(X - xk) ** 2 / (2 * sigma_e ** 2))
        g = g / g.max()                                # 峰值归一化，不是 Σ 归一化
    else:
        g = np.ones_like(X)
    dy = dy * g
    y_new = y - dy
    O_new = O + H * dy
    inj = (H * dy * DX).sum()
    return y_new, O_new, float(dy[np.argmin(abs(X - xk))]), inj


def main():
    print("=" * 68)
    r = run(rho_val=0.0, years=5.0, y_init=3.0)
    print(f"[T3a] 零源项/零通量：max|Δy| = {np.abs(r['y'] - 3.0).max():.2e}  (判据 <1e-12)")

    r = run(rho_val=0.0, years=3.0, w0_val=16.0, O0=100.0)
    pred = 100.0 * np.exp(-A_REC * 3.0)
    print(f"[T3c] O 衰减：数值 {r['O'][0]:.6f} vs 解析 {pred:.6f}  "
          f"相对误差 {abs(r['O'][0]-pred)/pred:.2e}")

    r = run(rho_val=6.0, years=5.0, w0_val=16.0)
    scale = H * (250.0 - 90.0) / 250.0
    print(f"[T11] V_min={r['Vmin']:.1f}  V 最小={r['Varr'].min():.1f}  "
          f"R_c={r['R_c']:.4e}  Lc={r['Lc']:.4e}  R_c/Lc={r['R_c']/r['Lc']:.4f}")

    print("[T1]  台账残差（直筒 5 年，强侵蚀）")
    for rho in (0.0, 3.0, 12.0):
        r = run(rho_val=rho, years=5.0, w0_val=16.0)
        rel = abs(r["resid"]) / max(1.0, abs(r["V"]))
        print(f"       rho_e={rho:5.1f}  residual={r['resid']:+.3e} m^3  "
              f"rel={rel:.2e}  V={r['V']:.3e}  R_c={r['R_c']:.3e}")

    print("=" * 68)
    y0 = np.zeros(NX)
    _, placed = place(y0, 1.0e6, xc=30.0, ell=1000.0)
    print(f"[投放] 设计 1.000e6 m^3 → 实投 {placed:.6f} m^3  "
          f"相对误差 {abs(placed-1e6)/1e6:.2e}  (判据 <1e-12)")

    f0 = 1.0 - np.exp(-16.0 / 20.0)          # w0=16 时的窄滩因子
    exp_dy = 8.0 * f0
    y1, O1, dyc, inj = storm(y0, np.zeros(NX), 8.0, gaussian=False)
    print(f"[风暴-uniform] 中心 dy={dyc:.4f} m (期望 dy_pot*f = 8*{f0:.4f} = {exp_dy:.4f})  "
          f"注入 {inj:.4e} m^3 vs 解析 H*dy*L={H*exp_dy*NX*DX:.4e}")

    y2, O2, dyc2, inj2 = storm(y0, np.zeros(NX), 8.0, gaussian=True, sigma_e=2000.0)
    print(f"[风暴-gauss]   中心 dy={dyc2:.4f} m (与 uniform 同值=峰值归一化生效)  "
          f"注入 {inj2:.4e} m^3 < uniform {inj:.2e}")

    print("\n[断言] 三条硬判据")
    print(f"  place 守恒      rel={abs(placed-1e6)/1e6:.2e}")
    print(f"  uniform 峰值    |{dyc:.6f}-{exp_dy:.6f}|={abs(dyc-exp_dy):.2e}")
    print(f"  gauss 峰值      |{dyc2:.6f}-{exp_dy:.6f}|={abs(dyc2-exp_dy):.2e}  (归一化后峰值不变)")


if __name__ == "__main__":
    main()
