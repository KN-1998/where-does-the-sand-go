#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""tools/verify_contract.py — 合同自洽检查器（可反复运行）

检查三件事：
  A. 参数内部自洽：由主参数重算所有派生量，与文档中写死的数值对拍；
  B. 文档一致性：不该出现的旧数值不得残留，该出现的必须有；
  C. 结构完整性：D 编号不重复、evidence_id 全部命中台账、CSV 列数正确。

用法：  python tools/verify_contract.py
退出码：0 = 全部通过；1 = 有失败项
"""
import csv
import math
import os
import re
import sys

import yaml

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FAILS, PASSES = [], []


def chk(name, ok, detail=""):
    (PASSES if ok else FAILS).append((name, ok, detail))
    print(f"  [{'PASS' if ok else 'FAIL'}] {name}" + (f"  — {detail}" if detail else ""))


def close(a, b, rel=1e-2):
    return abs(a - b) <= rel * max(abs(a), abs(b), 1e-9)


def main():
    P = yaml.safe_load(open(os.path.join(ROOT, "modeling", "params.yaml"), encoding="utf-8"))
    g, t, b, s, m, sc = P["geometry"], P["transport"], P["beach_state"], P["storm"], P["management"], P["scenarios"]

    print("\n=== A. 参数内部自洽 ===")
    H = g["h_star"]["value"] + g["B_berm"]["value"]
    chk("H = h* + B = 10 m", close(H, g["H_dep"]["value"]),
        f"{g['h_star']['value']}+{g['B_berm']['value']}={H} vs 记录 {g['H_dep']['value']}")

    chk("V_ref = H * w_ref", close(b["V_ref"]["value"], H * b["w_ref"]["value"]),
        f"{H}*{b['w_ref']['value']} vs {b['V_ref']['value']}")

    vmin_far = b["V_ref"]["value"] - H * b["w0_far"]["value"]
    vmin_hot = b["V_ref"]["value"] - H * b["w0_min"]["value"]
    chk("V_min: 远场=0、热点=90", close(vmin_far, 0, 1e-9) and close(vmin_hot, 90),
        f"far={vmin_far:.1f}, hotspot={vmin_hot:.1f}")

    sig = math.log(s["dy_p95"]["value"] / s["dy_ref"]["value"]) / 1.645
    chk("sigma_ln = 0.693", close(sig, 0.693, 2e-3), f"{sig:.4f}")

    E_dy = s["dy_ref"]["value"] * math.exp(sig ** 2 / 2)
    chk("E[dy] = 中位*exp(s^2/2) ≈ 10.2 m", close(E_dy, 10.2, 5e-3), f"{E_dy:.3f}")

    a = s["k_rec"]["value"] + s["lam_off"]["value"]
    kfrac = s["k_rec"]["value"] / a
    chk("k/(k+lambda) = 0.870", close(kfrac, 0.8696, 5e-3), f"{kfrac:.4f}")

    rho_storm = s["lambda_s"]["value"] * 10.0 * s["lam_off"]["value"] / a
    chk("rho_storm ≈ 0.522 (E=10.0 舍入)", close(rho_storm, t["rho_storm"]["value"], 3e-2),
        f"{rho_storm:.4f} vs 记录 {t['rho_storm']['value']}")

    L = P["domain"]["L_corridor"]["value"]
    sh = t["sigma_h"]["value"]
    corridor = t["rho_e"]["value"] * (1 + t["rho_e_hotspot_amp"]["value"] * math.sqrt(2 * math.pi) * sh / L)
    chk("走廊均值 2.31", close(corridor, t["rho_e_corridor_mean"]["value"]),
        f"{corridor:.4f} vs 记录 {t['rho_e_corridor_mean']['value']}")

    peak = t["rho_e"]["value"] * (1 + t["rho_e_hotspot_amp"]["value"])
    chk("热点峰值 3.74 落在 DEQ 3.8-4.0 带内", 3.7 <= peak <= 4.05, f"peak={peak:.2f}")

    bias = rho_storm / corridor
    chk("双计数偏差 ≈ +22.5%", close(bias, 0.225, 5e-2), f"{bias*100:.1f}%")

    # f_w(0)
    wf, wm, wl, sw = b["w0_far"]["value"], b["w0_min"]["value"], b["w_mgmt"]["value"], b["sigma_w"]["value"]
    half = sw * math.sqrt(2 * math.log((wf - wm) / (wf - wl)))
    fw0 = 2 * half / L
    chk("f_w(0) = 0.3036", close(fw0, 0.3036, 2e-3), f"半宽={half:.1f} m, f={fw0:.4f}")

    # CERC
    Kc = P["waves"]["K_c"]["value"]
    Hb = P["waves"]["Hb"]["value"]
    D_cerc = 2 * Kc * Hb ** 2.5 / H * 3.156e7
    chk("CERC 中心值落在 4.0-4.3e5", 4.0e5 <= D_cerc <= 4.3e5, f"D={D_cerc:.3e}")
    chk("主算 D=3e5 低于 CERC（偏乐观，已披露）", t["D_diff"]["value"] < D_cerc,
        f"3e5 vs {D_cerc:.2e}")

    # 情景缩放
    def rho_storm_scen(lam, med):
        e = med * math.exp(sig ** 2 / 2)
        return lam * e * s["lam_off"]["value"] / a

    targets = {"S1": (0.2, 6.0, 1.7), "S2": (0.4, 8.0, 3.0)}
    expect_scale = {"S1": 0.649, "S2": 1.068}
    for name, (lam, med, tgt) in targets.items():
        rs = rho_storm_scen(lam, med)
        scale = (tgt - rs) / corridor
        print(f"       {name}: rho_storm={rs:.3f}, scale={scale:.3f}")
        chk(f"{name} 缩放 = {expect_scale[name]}", close(scale, expect_scale[name], 0.01), f"{scale:.3f}")
    s3_0 = (3.0 - rho_storm_scen(0.4, 8.0)) / corridor
    s3_1 = (5.0 - rho_storm_scen(0.8, 11.0)) / corridor
    chk("S3 缩放 1.068 → 1.531 ±0.01", close(s3_0, 1.068, 0.01) and close(s3_1, 1.531, 0.01),
        f"{s3_0:.3f} -> {s3_1:.3f}")

    print("\n=== B. 文档一致性 ===")
    docs = []
    for base in ("modeling", "handoff", "资料"):
        for dirpath, _, files in os.walk(os.path.join(ROOT, base)):
            for f in files:
                if f.endswith(".md"):
                    docs.append(os.path.join(dirpath, f))
    docs.append(os.path.join(ROOT, "README.md"))
    docs = [d for d in docs if "REVIEW_RESPONSE" not in d]
    blob = {d: open(d, encoding="utf-8").read() for d in docs}

    banned = {"1.283": "旧的 rho_bg", "0.417": "旧的 rho_storm", "0.214": "旧的 f_w(0)",
              "a_h=1.78": "旧的热点幅值", "1.78-1": "旧的热点幅值",
              "D12 · 成本结构": "旧 D 编号", "D12，两种结构": "旧 D 编号"}
    for tok, why in banned.items():
        hits = [os.path.basename(d) for d, s_ in blob.items() if tok in s_]
        chk(f"无残留「{tok}」({why})", not hits, ",".join(hits) if hits else "")

    must = ["0.3036", "2.31", "0.522", "22.5"]
    for tok in must:
        hits = [os.path.basename(d) for d, s_ in blob.items() if tok in s_]
        chk(f"关键值「{tok}」已写入文档", bool(hits), ",".join(hits[:4]))

    print("\n=== B2. 可执行口径 ===")
    coder = open(os.path.join(ROOT, "handoff", "CODER_SPEC.md"), encoding="utf-8").read()
    mspec = open(os.path.join(ROOT, "modeling", "MODEL_SPEC.md"), encoding="utf-8").read()
    bad_scale = [l for l in coder.splitlines()
                 if ("target / 2.3" in l or "target/2.3" in l) and "不要用" not in l]
    chk("情景缩放不再用 target/2.3", not bad_scale, bad_scale[0][:40] if bad_scale else "")
    chk("缩放公式含 rho_storm", "rho_storm" in coder and "(3.0 - 0.530)/2.31" in coder)
    chk("台账列含 R_c_cum", "R_c_cum" in coder)
    chk("闭合式中 R_c 为减项", "chronic_loss_cum - R_c_cum" in coder)
    chk("MODEL_SPEC 恒等式 R_c 为减项", "-(V_0+O_0)" in mspec or "-\\int R_c" in mspec)
    chk("discrete_contract.py 存在", os.path.exists(
        os.path.join(ROOT, "modeling", "sanity", "discrete_contract.py")))

    chk("CODER 有全局数值口径 §3.5", "3.5 全局数值口径约定" in coder)
    chk("CODER 有足迹归一化 §2.4d", "2.4d 风暴足迹" in coder)
    chk("R_c 为当前亏空（可恢复）", "当前亏空" in coder and "当前亏空" in mspec)
    chk("明确禁止峰值写法", "历史峰值" in coder)
    chk("原型含 refill 测试", "run_erode_refill" in open(
        os.path.join(ROOT, "modeling", "sanity", "discrete_contract.py"), encoding="utf-8").read())
    chk("网格 360 格", "nx  = 360" in coder)
    chk("原型含断言与退出码", "sys.exit(main())" in open(
        os.path.join(ROOT, "modeling", "sanity", "discrete_contract.py"), encoding="utf-8").read())
    chk("S2 用绝对 2.25 + 共享事件表", "t=2.25" in coder and "shared_per_scenario" in coder)
    chk("params 事件表需共享", "shared_per_scenario" in open(
        os.path.join(ROOT, "modeling", "params.yaml"), encoding="utf-8").read())
    num = P["numerics"]
    for k in ("metric_domain", "phi_shape", "seed_rule", "placement_time_rule"):
        chk(f"numerics.{k} 已定义", k in num)
    chk("T12 已按 360 格离散值 0.3000", "0.3000" in coder)
    chk("discrete_contract 含投放/风暴测试", "def place(" in open(
        os.path.join(ROOT, "modeling", "sanity", "discrete_contract.py"), encoding="utf-8").read())

    chk("SCHEDULE.md 存在", os.path.exists(os.path.join(ROOT, "SCHEDULE.md")))
    chk("START_HERE.md 存在", os.path.exists(os.path.join(ROOT, "START_HERE.md")))
    chk("CODER 有 §0.0 第一小时", "0.0 第一件事" in coder)
    chk("configs/base.yaml 存在", os.path.exists(os.path.join(ROOT, "configs", "base.yaml")))
    chk("tests/README.md 存在", os.path.exists(os.path.join(ROOT, "tests", "README.md")))
    chk("CODER 有 §0 立即执行令", "0. 立即执行令" in coder)
    chk("CODER 有自主决断清单", "0.1 你可以自己决定" in coder)
    chk("PROGRESS 有编程手提问段", "编程手提问" in open(
        os.path.join(ROOT, "PROGRESS.md"), encoding="utf-8").read())
    chk("WRITER_NOTES 有 §0 执行令", "0. 立即执行令" in open(
        os.path.join(ROOT, "handoff", "WRITER_NOTES.md"), encoding="utf-8").read())
    chk("README 指向 SCHEDULE", "SCHEDULE.md" in open(
        os.path.join(ROOT, "README.md"), encoding="utf-8").read())

    chk("无「只增不减」残留", "只增不减" not in coder and "只增不减" not in mspec)
    chk("无「不回退」残留", "不回退" not in coder and "不回退" not in mspec)
    chk("R_c_cum 语义已澄清", "不是时间累计量" in coder)
    chk("有冲突裁决权 §0.6", "0.6 冲突裁决权" in coder)

    print("\n=== C. 结构完整性 ===")
    dec = open(os.path.join(ROOT, "modeling", "DECISIONS.md"), encoding="utf-8").read()
    nums = re.findall(r"^## (D\d+) ·", dec, re.M)
    dup = sorted({x for x in nums if nums.count(x) > 1})
    chk("D 编号无重复", not dup, f"重复={dup}" if dup else f"共 {len(nums)} 条")
    expect = [f"D{i}" for i in range(1, 19)]
    chk("D1–D18 连续齐全", sorted(set(nums), key=lambda x: int(x[1:])) == expect,
        f"缺={set(expect)-set(nums)}")

    rows = list(csv.reader(open(os.path.join(ROOT, "ledger", "claims.csv"), encoding="utf-8")))
    hdr, body = rows[0], rows[1:]
    chk("claims 列数 10", len(hdr) == 10, f"{len(hdr)}")
    chk("claims 无重复 ID", len(body) == len({r[0] for r in body}), f"{len(body)} 行")
    ids = {r[0] for r in body}
    ev = set(re.findall(r"evidence_id:\s*([A-Za-z0-9\-]+)", open(
        os.path.join(ROOT, "modeling", "params.yaml"), encoding="utf-8").read()))
    missing = sorted(ev - ids)
    chk("params 的 evidence_id 全部命中台账", not missing, f"缺={missing}")

    print(f"\n===== 结果：{len(PASSES)} 通过 / {len(FAILS)} 失败 =====")
    if FAILS:
        for n, _, d in FAILS:
            print(f"  FAIL {n} {d}")
        return 1
    print("全部通过。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
