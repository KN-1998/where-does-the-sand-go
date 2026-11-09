#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
erf_prototype.py — 参考原型（阶段 1 门禁用，非成品，<150 行）
只做四件事：① 校验 erf 解析解推导；② 保护期闭式解与数值解对拍；
③ 给编程手一组对照数值；④ 扫描投放宽度 ℓ 看沙量效率。
不含风暴、不含沙库 O、w0 均匀 —— 这些是成品求解器的事。

运行:  python erf_prototype.py  > results.txt
"""
import numpy as np
from math import erf

H, D, RHO = 10.0, 3.0e5, 2.3     # m, m^2/yr, m/yr
WC0, WCRIT, V_TOT, L_CORR = 18.0, 20.0, 1.0e6, 5000.0

_erf = np.vectorize(erf)

def y_field(x, t, ell, dy0, D=D, rho=0.0):
    """有限长均匀投放 + 常沉汇：y = dy0/2[erf((x+ell/2)/s)-erf((x-ell/2)/s)] - rho*t"""
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
    """保护期：解 dy0*erf(ell/(4 sqrt(D t))) - rho t = dy_req"""
    if dy_req <= 0:
        return float("inf")
    if dy0 <= dy_req:
        return 0.0
    if rho == 0.0:
        return ell ** 2 / (16.0 * D * inv_erf(dy_req / dy0) ** 2)
    lo, hi = 0.0, 500.0
    for _ in range(200):
        mid = 0.5 * (lo + hi)
        lo, hi = (mid, hi) if y_center(mid, ell, dy0, D, rho) > dy_req else (lo, mid)
    return 0.5 * (lo + hi)

def ftcs(dx=50.0, dt=0.25, t_end=1.0, ell=1000.0, dy0=100.0, half=4500.0):
    """FTCS 显式格式 + 零通量边界；返回 (r, 相对 L∞ 误差, 质量相对变化)"""
    n = int(round(2 * half / dx)) + 1
    x = -half + dx * np.arange(n)
    y = np.where(np.abs(x) <= ell / 2, dy0, 0.0)
    m0 = y.sum() * dx
    r = D * dt / dx ** 2
    assert r <= 0.5, f"FTCS 不稳定 r={r}"
    for _ in range(int(round(t_end / dt))):
        y[1:-1] += r * (y[2:] - 2 * y[1:-1] + y[:-2])
        y[0], y[-1] = y[1], y[-2]
    ya = y_field(x, t_end, ell, dy0)
    return r, np.max(np.abs(y - ya)) / dy0, abs(y.sum() * dx - m0) / m0

def protected_years(ell, v_tot=V_TOT, D=D, rho=RHO, w0=WC0, wcrit=WCRIT,
                    tmax=15.0, nx=501, nt=151):
    """走廊内 1{w>=wcrit} 的面积-时间积分 [m·yr]"""
    dy0 = v_tot / (H * ell)
    x = np.linspace(-L_CORR / 2, L_CORR / 2, nx)
    dx, tot = x[1] - x[0], 0.0
    for tk in np.linspace(tmax / (nt - 1), tmax, nt):
        w = w0 + y_field(x, tk, ell, dy0, D, rho)
        tot += np.count_nonzero(w >= wcrit) * dx * (tmax / (nt - 1))
    return tot, dy0

def w0_hotspot(x, w_far=25.0, dip=9.0, sig=700.0):
    """单一热点：中央 25-9=16 m，向外回到 25 m；w_crit=20 → 基线风险带宽约 ±534 m"""
    return w_far - dip * np.exp(-(x / sig) ** 2)

def risk_avoided(ell, xc=0.0, D=D, rho=RHO, wcrit=WCRIT, tmax=15.0, nx=501, nt=151):
    """避免的风险 [m·yr] = ∫∫[1{w_base>=wcrit} - 1{w>=wcrit}]"""
    dy0 = V_TOT / (H * ell)
    x = np.linspace(-L_CORR / 2, L_CORR / 2, nx)
    dx, tot, wb = x[1] - x[0], 0.0, w0_hotspot(x)
    for tk in np.linspace(tmax / (nt - 1), tmax, nt):
        w = wb + y_field(x - xc, tk, ell, dy0, D, rho)
        tot += (np.count_nonzero(wb >= wcrit) - np.count_nonzero(w >= wcrit)) * dx * (tmax / (nt - 1))
    return tot

def main():
    print("=" * 72)
    print("[1] 扩散半衰期 T_half = 0.2748*ell^2/D")
    for ell in (500, 1000, 2000, 5000):
        print(f"    ell={ell:5.0f} m -> T_half={0.2748*ell**2/D:7.2f} yr")

    print("=" * 72); print("[2] FTCS vs erf（ell=1000, dy0=100, t=1 yr）")
    for dx in (100.0, 50.0, 25.0):
        r, err, dm = ftcs(dx, 0.4 * dx ** 2 / D)
        print(f"    dx={dx:5.0f} r={r:.3f}  L∞相对误差={err:.3e}  质量相对变化={dm:.2e}")

    print("=" * 72); print("[3] 保护期：闭式(rho=0) 与含沉汇数值根")
    for w0 in (18.0, 12.0):
        print(f"  -- w0={w0:.0f} m (dy_req={WCRIT-w0:.0f} m)")
        for ell in (1000, 2000, 5000):
            dy0 = V_TOT / (H * ell)
            print(f"    ell={ell:5.0f} dy0={dy0:6.1f} m  "
                  f"T_p(rho=0)={Tp(ell,dy0,WCRIT-w0,D,0):8.2f} yr"
                  f"  T_p(rho=2.3)={Tp(ell,dy0,WCRIT-w0,D,RHO):6.2f} yr")

    print("=" * 72); print("[4] 投放宽度扫描（V=1e6 m^3, w0=18, w_crit=20）")
    rows = [(e, *protected_years(e)) for e in np.linspace(400, 6000, 29)]
    pmax = max(r[1] for r in rows)
    print(f"    {'ell(m)':>8}{'dy0(m)':>9}{'保护岸线·年':>14}{'效率':>9}")
    for ell, py, dy0 in rows:
        print(f"    {ell:8.0f}{dy0:9.1f}{py:14.0f}{py/pmax:9.3f}"
              + ("  <== 最优" if py >= pmax - 1e-9 else ""))

    print("=" * 72); print("[5] 三方案对照（V=1e6 m^3, rho=2.3）")
    for name, ell in (("A 匀铺 5km", 5000.0), ("B 热点 1km", 1000.0), ("C 单段 0.5km", 500.0)):
        dy0 = V_TOT / (H * ell)
        print(f"    {name:12s} ell={ell:5.0f} dy0={dy0:6.1f} m"
              f"  T_p(中心)={Tp(ell,dy0,WCRIT-WC0,D,RHO):5.2f} yr"
              f"  均匀滩保护岸线·年={protected_years(ell)[0]:8.0f}"
              f"  热点避免风险={risk_avoided(ell):8.0f}")
    print("=" * 72)
    v_thr = H * L_CORR * (WCRIT - (25.0 - 9.0))
    print(f"[6] 匀铺可覆盖全域的临界沙量 V_thr = H*L*(w_crit-w_min) = {v_thr:.0f} m^3")
    print(f"    V={V_TOT:.0f} >= V_thr={v_thr:.0f} -> 匀铺可行（本例）")
    print( "    若 V<V_thr，匀铺后仍有岸段低于阈值 -> 必须集中投放（NONDIM §4）")


if __name__ == "__main__":
    import io, os, contextlib
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        main()
    txt = buf.getvalue()
    open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "results.txt"),
         "w", encoding="utf-8").write(txt)
    print(txt)  # 控制台可能乱码，以 results.txt 为准




