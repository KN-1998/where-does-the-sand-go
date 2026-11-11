#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""discrete_contract.py — 离散合同参考实现（非成品求解器）

2026-11-11 第二轮修正（针对复核 ac8b71d 的 P0/P1）：
  1. 不截断 y：y 是侵蚀前锋，可继续 < -w0；只把账面存量记成 max(V_abs, V_min)。
     R_c 用峰值亏空逐步累加（max 运算天然单调，不重复计同一亏空）。
  2. 网格 360 个 cell-centered 控制体（dx=25，域 [-4500,4500]），
     总长 9000 m；中央 5 km 恰为 200 格。
  3. 台账补 O0 与连续源项；判据全部真断言，失败退出码 1。
不含：风暴抽样、补沙调度、空间聚合。
运行：python discrete_contract.py  -> 退出码 0 = 全过
"""
import sys
import numpy as np

D = 3.0e5
H = 10.0
LB, DX = 4500.0, 25.0
NX = int(2 * LB / DX)
X = -LB + DX / 2 + DX * np.arange(NX)
NCENT = int(5000 / DX)
DT = 0.02
K, LAM = 0.667, 0.1
A = K + LAM
V_REF = 250.0


def thomas(a, b, c, d):
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


def step(y, O, src, rho, dt=DT):
    O_new = O * np.exp(-A * dt)
    Rn = (K / A) * (O - O_new)
    lamO = (LAM / A) * (O - O_new)
    r = D * dt / DX ** 2
    main = np.full(NX, 1.0 + 2 * r)
    lower = np.full(NX - 1, -r)
    upper = np.full(NX - 1, -r)
    main[0] = main[-1] = 1.0 + r
    rhs = y + (Rn / (H * dt) + src - rho) * dt
    return thomas(lower, main, upper, rhs), O_new, Rn, lamO


def run(rho_val, years=5.0, w0_val=16.0, O0=0.0, y_init=0.0, src=0.0):
    y = np.full(NX, float(y_init))
    O = np.full(NX, float(O0))
    V_min = np.full(NX, V_REF - H * float(w0_val))
    Rc_cell = np.zeros(NX)
    lamO_cum = Lc_cum = 0.0
    V0_total = ((V_REF + H * y).sum() * DX) + O.sum() * DX   # 绝对存量（含 V_REF）
    src_cum = src * H * NX * DX * years
    for _ in range(int(round(years / DT))):
        y, O, Rn, lamO = step(y, O, src, np.full(NX, rho_val))
        V_abs = V_REF + H * y
        Rc_cell = np.maximum(Rc_cell, np.maximum(V_min - V_abs, 0.0))
        lamO_cum += lamO.sum() * DX
        Lc_cum += rho_val * H * NX * DX * DT
    V_book = np.maximum(V_REF + H * y, V_min)
    R_c = Rc_cell.sum() * DX
    placed = src_cum
    dVO = (V_book.sum() * DX + O.sum() * DX) - V0_total
    residual = placed - (lamO_cum + Lc_cum) - dVO + R_c
    return dict(y=y, O=O, V=V_book, R_c=R_c, resid=residual,
                Lc=Lc_cum, lamO=lamO_cum, placed=placed, Vmin=float(V_min[0]))


def place(y, volume, xc=30.0, ell=1000.0):
    lo, hi = xc - ell / 2, xc + ell / 2
    overlap = np.clip(np.minimum(X + DX / 2, hi) - np.maximum(X - DX / 2, lo), 0, None)
    frac = overlap / overlap.sum()
    dy = (volume * frac) / (H * DX)
    placed = (H * dy * DX).sum()
    assert abs(placed - volume) / volume < 1e-12, "place not conservative"
    return y + dy, placed


def storm(y, O, dy_pot, xk=0.0, sigma_e=2000.0, gaussian=False, w0v=16.0, w_s=20.0):
    w_eff = np.maximum(w0v + y, 0.0)
    f = 1.0 - np.exp(-w_eff / w_s)
    dy = np.minimum(dy_pot * f, w_eff)
    g = (np.exp(-(X - xk) ** 2 / (2 * sigma_e ** 2)) if gaussian else np.ones(NX))
    g = g / g.max()
    dy = dy * g
    inj = (H * dy * DX).sum()
    return y - dy, O + H * dy, float(dy[np.argmin(abs(X - xk))]), inj


def main():
    fails = []

    def chk(name, ok, detail=""):
        print(f"  [{'PASS' if ok else 'FAIL'}] {name}  {detail}")
        if not ok:
            fails.append(name)

    print(f"grid: NX={NX} cells x {DX} m = {NX*DX:.0f} m; central {NCENT} cells = {NCENT*DX:.0f} m")
    chk("total length 9000 m", abs(NX * DX - 9000) < 1e-9, f"{NX*DX}")
    chk("central 5 km = 200 cells", NCENT == 200)

    print("\n[T3a] zero source / zero flux")
    r = run(0.0, years=5.0, y_init=3.0)
    e = np.abs(r["y"] - 3.0).max()
    chk("max|dy| < 1e-12", e < 1e-12, f"{e:.2e}")

    print("\n[T3c] O exponential decay")
    r = run(0.0, years=3.0, O0=100.0)
    pred = 100.0 * np.exp(-A * 3.0)
    rel = abs(r["O"][0] - pred) / pred
    chk("rel err < 1e-12", rel < 1e-12, f"{rel:.2e}")

    print("\n[T11] strong erosion: y unclipped / V floored / R_c accumulates")
    r = run(12.0, years=8.0)
    chk("min y < -w0 (unclipped)", r["y"].min() < -16.0 + 1e-9, f"y_min={r['y'].min():.2f}")
    chk("min V >= V_min", (r["V"] - r["Vmin"]).min() > -1e-9, f"V_min={r['V'].min():.1f}")
    chk("R_c > 0", r["R_c"] > 0, f"{r['R_c']:.3e}")

    print("\n[T1] ledger closure (with O0 and continuous source)")
    for kw in (dict(rho_val=0.0, years=5.0),
               dict(rho_val=3.0, years=5.0),
               dict(rho_val=12.0, years=5.0),
               dict(rho_val=3.0, years=3.0, O0=100.0),
               dict(rho_val=3.0, years=1.0, src=1.0)):
        r = run(**kw)
        scale = max(1.0, abs(r["placed"]) + abs(r["Lc"]))
        rel = abs(r["resid"]) / scale
        chk(f"residual {kw}", rel < 1e-10, f"resid={r['resid']:+.2e} rel={rel:.1e}")

    print("\n[placement] overlap-weighted conservation")
    _, placed = place(np.zeros(NX), 1.0e6, xc=30.0, ell=1000.0)
    chk("rel err < 1e-12", abs(placed - 1e6) / 1e6 < 1e-12, f"{placed:.3f}")

    print("\n[storm] narrow-beach factor and footprint normalisation")
    f0 = 1 - np.exp(-16.0 / 20.0)
    y1, O1, dyc, inj = storm(np.zeros(NX), np.zeros(NX), 8.0)
    y2, O2, dyc2, inj2 = storm(np.zeros(NX), np.zeros(NX), 8.0, gaussian=True)
    chk("uniform peak = 8*f", abs(dyc - 8.0 * f0) < 1e-12, f"{dyc:.6f}")
    chk("gauss peak unchanged", abs(dyc2 - dyc) < 1e-12, f"{dyc2:.6f}")
    chk("gauss total < uniform", inj2 < inj, f"{inj2:.3e} < {inj:.3e}")

    print("\n===== " + ("ALL PASS" if not fails else "FAIL: " + ", ".join(fails)) + " =====")
    return 0 if not fails else 1


if __name__ == "__main__":
    sys.exit(main())
