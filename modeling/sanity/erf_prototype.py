#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""erf_prototype.py — 参考原型（阶段 1 门禁，非成品，<150 行）。
校验 erf 解析解、保护期闭式/数值对拍、给编程手对照数值、扫描投放宽度。
不含风暴与沙库 O。2026-11-09 修订：避免风险符号/基线、积分权重、高斯定义、Tp 负需求。
运行: python erf_prototype.py（同时写 results.txt）"""
import numpy as np
from math import erf
H, D, RHO = 10.0, 3.0e5, 2.3      # m, m^2/yr, m/yr
WC0, WCRIT, V_TOT, L_CORR = 18.0, 20.0, 1.0e6, 5000.0
W_FAR, DIP, SIG = 25.0, 9.0, 700.0  # 热点场：25-9*exp(-x^2/(2*700^2))
_erf = np.vectorize(erf)
def y_field(x, t, ell, dy0, D=D, rho=0.0):
    """有限长均匀投放 + 常沉汇：erf 解（无限域）"""
    x = np.asarray(x, dtype=float)
    if t <= 0:
        return np.where(np.abs(x) <= ell / 2, dy0, 0.0)
    s = 2.0 * np.sqrt(D * t)
    return 0.5 * dy0 * (_erf((x + ell / 2) / s) - _erf((x - ell / 2) / s)) - rho * t
def y_center(t, ell, dy0, D=D, rho=0.0):
    if t <= 0:
        return dy0
    return dy0 * erf(ell / (4.0 * np.sqrt(D * t))) - rho * t
def inv_erf(r):
    lo, hi = 0.0, 9.0
    for _ in range(200):
        mid = 0.5 * (lo + hi)
        lo, hi = (mid, hi) if erf(mid) < r else (lo, mid)
    return 0.5 * (lo + hi)
def Tp(ell, dy0, dy_req, D=D, rho=0.0):
    """保护期：解 dy0*erf(ell/(4 sqrt(D t))) - rho t = dy_req。
    dy_req<=0 且 rho>0 时仍有有限根（初始安全 ≠ 永久安全）。"""
    if dy0 <= dy_req:
        return 0.0
    if rho == 0.0:
        return float("inf") if dy_req <= 0 else ell**2 / (16.0*D*inv_erf(dy_req/dy0)**2)
    lo, hi = 0.0, 500.0
    for _ in range(200):
        mid = 0.5 * (lo + hi)
        lo, hi = (mid, hi) if y_center(mid, ell, dy0, D, rho) > dy_req else (lo, mid)
    return 0.5 * (lo + hi)
def centers(L, n):
    dx = L / n
    return -L/2 + (np.arange(n) + 0.5) * dx, dx
def protected_years(ell, v_tot=V_TOT, D=D, rho=RHO, w0=WC0, wcrit=WCRIT,
                    tmax=15.0, n=500, nt=150):
    """1{w>=w_mgmt} 的面积-时间积分 [m·yr]，用单元中心 + 时间中点"""
    dy0 = v_tot / (H * ell)
    x, dx = centers(L_CORR, n)
    dt, tot = tmax / nt, 0.0
    for k in range(nt):
        w = w0 + y_field(x, (k + 0.5) * dt, ell, dy0, D, rho)
        tot += np.count_nonzero(w >= wcrit) * dx * dt
    return tot, dy0
def w0_hotspot(x):
    """单一热点：中央 16 m，向外回到 25 m；与主模型同定义 exp(-x^2/(2σ^2))"""
    return W_FAR - DIP * np.exp(-(x / SIG) ** 2 / 2.0)
def risk_avoided(ell, xc=0.0, D=D, rho=RHO, wcrit=WCRIT, tmax=15.0, n=500, nt=150):
    """避免的风险 [m·yr] = ∫∫[1{w_nour>=wc} - 1{w_base>=wc}]，基线含 -rho*t"""
    dy0 = V_TOT / (H * ell)
    x, dx = centers(L_CORR, n)
    wb0 = w0_hotspot(x)
    dt, tot = tmax / nt, 0.0
    for k in range(nt):
        tk = (k + 0.5) * dt
        wb = wb0 + y_field(x, tk, ell, 0.0, D, rho)       # 无补沙基线
        wn = wb0 + y_field(x - xc, tk, ell, dy0, D, rho)  # 有补沙
        tot += (np.count_nonzero(wn >= wcrit) - np.count_nonzero(wb >= wcrit)) * dx * dt
    return tot
def ftcs(dx, dt, t_end, ell=1000.0, dy0=100.0):
    """守恒有限体积 + FTCS；零通量边界；单元平均初值（按重叠长度）"""
    n = int(round(2 * 2500.0 / dx)); L = n * dx
    x, _ = centers(L, n)
    y = np.clip((ell/2 - np.abs(x)) / dx + 0.5, 0.0, 1.0) * dy0
    m0 = y.sum() * dx
    assert D * dt / dx**2 <= 0.5
    for _ in range(int(round(t_end / dt))):
        F = np.zeros(n + 1)
        F[1:-1] = -D * (y[1:] - y[:-1]) / dx
        y += dt / dx * (F[:-1] - F[1:])
    ya = y_field(x, round(t_end/dt)*dt, ell, dy0)
    return D*dt/dx**2, np.max(np.abs(y - ya))/dy0, abs(y.sum()*dx - m0)/m0
def smooth_order():
    """光滑初值（高斯）下的收敛阶：FTCS 应接近二阶"""
    out = []
    for dx in (100.0, 50.0, 25.0):
        n = int(round(5000.0 / dx)); L = n * dx
        x, _ = centers(L, n)
        s = 200.0
        y = np.exp(-x**2/(2*s**2))
        dt = 0.2 * dx**2 / D
        t_end = 0.2
        for _ in range(int(round(t_end/dt))):
            F = np.zeros(n + 1); F[1:-1] = -D*(y[1:]-y[:-1])/dx
            y += dt/dx*(F[:-1]-F[1:])
        s2 = s*s + 2*D*t_end  # 高斯初值的精确扩散解
        ya = np.sqrt(s*s/s2) * np.exp(-x**2/(2*s2))
        out.append(np.sqrt(np.mean((y-ya)**2)))
    return out
def main():
    print("="*72); print("[1] T_half = 0.2748*ell^2/D")
    for ell in (500, 1000, 2000, 5000):
        print(f"    ell={ell:5.0f} m -> T_half={0.2748*ell**2/D:7.2f} yr")
    print("="*72); print("[2] FTCS vs erf（ell=1000, dy0=100, t=1 yr）")
    for dx in (100.0, 50.0, 25.0):
        r, err, dm = ftcs(dx, 0.4*dx**2/D, 1.0)
        print(f"    dx={dx:5.0f} r={r:.3f}  L_inf相对误差={err:.3e}  质量相对变化={dm:.2e}")
    e = smooth_order()
    print(f"    光滑初值 L2 误差比: {e[0]/e[1]:.2f}, {e[1]/e[2]:.2f}（理论→4）")
    print("="*72); print("[3] 保护期：闭式(rho=0) 与含沉汇数值根")
    for w0 in (18.0, 12.0):
        print(f"  -- w0={w0:.0f} m (dy_req={WCRIT-w0:.0f} m)")
        for ell in (1000, 2000, 5000):
            dy0 = V_TOT/(H*ell)
            print(f"    ell={ell:5.0f} dy0={dy0:6.1f}  T_p(rho=0)={Tp(ell,dy0,WCRIT-w0,D,0):8.2f}"
                  f"  T_p(rho=2.3)={Tp(ell,dy0,WCRIT-w0,D,RHO):6.2f}")
    print(f"    dy_req=-5, ell=5000, dy0=20, rho=2.3 -> T_p={Tp(5000,20,-5,D,RHO):.3f} yr（旧版返回 inf）")
    print("="*72); print("[4] 投放宽度扫描（V=1e6, w0=18, w_mgmt=20）")
    rows = [(ell, *protected_years(ell)) for ell in np.linspace(400, 6000, 29)]
    pmax = max(r[1] for r in rows)
    print(f"    {'ell(m)':>8}{'dy0(m)':>9}{'保护岸线·年':>14}{'效率':>9}")
    for ell, py, dy0 in rows:
        print(f"    {ell:8.0f}{dy0:9.1f}{py:14.0f}{py/pmax:9.3f}"
              + ("  <== 最优" if py >= pmax - 1e-9 else ""))
    print("="*72); print("[5] 三方案（V=1e6, rho=2.3；管理滩宽口径 w>=20）")
    for name, ell in (("A 匀铺 5km", 5000.0), ("B 热点 1km", 1000.0),
                      ("C 单段 0.5km（全部沙量）", 500.0)):
        dy0 = V_TOT/(H*ell)
        print(f"    {name:22s} ell={ell:5.0f} dy0={dy0:6.1f}"
              f"  T_p(中心)={Tp(ell,dy0,WCRIT-WC0,D,RHO):5.2f}"
              f"  均匀滩保护岸线·年={protected_years(ell)[0]:8.0f}"
              f"  热点避免风险={risk_avoided(ell):8.0f}")
    print("    注：C 是“全部沙量集中在 0.5 km”，不是五段方案的一段；五段等分需另算。")
    print("="*72)
    v_thr = H*L_CORR*(WCRIT - (W_FAR - DIP))
    print(f"[6] V_thr = H*L*(w_mgmt-w_min) = {v_thr:.0f} m^3")
    print(f"    V={V_TOT:.0f} >= V_thr={v_thr:.0f} -> 匀铺可行（本例）")
    print("    若 V<V_thr，匀铺后仍有岸段低于阈值 -> 需集中投放（NONDIM §4）")
if __name__ == "__main__":
    import io, os, contextlib
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        main()
    txt = buf.getvalue()
    print(txt, end="")
    open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "results.txt"),
         "w", encoding="utf-8").write(txt)
