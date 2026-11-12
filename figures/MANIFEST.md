# figures/ — F1–F8 说明

> 生成：`python -m viz.plots`（300 dpi PNG，黑白可辨：线型 + 标记 + 阴影）。
> 每张图内已标注坐标轴单位与数据类型（MODEL / MODEL-SCENARIO / ASSUME / OBS）。

| 图 | 文件 | 数据来源 | 内容 / 读法 |
|---|---|---|---|
| F1 | `F1_w_xt.png` | `results/E1/uniform/fields.npz` | $w(x,t)$ 时空图；白线为 $w=20$ m；补沙脉冲随扩散摊平、约 9 yr 中心跌破阈值 |
| F2 | `F2_w_t_positions.png` | `E0/S1_deterministic`、`E1/uniform` | 热点中心 / 热点边缘 / 缓冲区 3 个位置的 $w(t)$；基线 vs 补沙；虚线为管理阈值 |
| F3 | `F3_sand_destinations.png` | `E1/uniform/destinations.csv` | 补沙去向（9 km 内留存 / 出域 / 永久离岸）；15 yr 留存 91.4%，离岸 7.3% |
| F4 | `F4_T_first_fail_hist.png` | `E2/*_mc/mc_results.csv` | 1000 次 MC 的 $T_{\text{first,fail}}^w$ 与 $^b$ 直方图；图例给出删失比例 |
| F5 | `F5_placement_bars.png` | `E1/summary.json` | 三布置的 $T_{\text{safe,cum}}^w$ 与保护岸线·年（同方量 1e6 m³） |
| F6 | `F6_oat_tornado.png` | `E5/summary.json` | OAT 对 $E_w$ 的 tornado（S2，once；风暴组固定 $\rho_e$ 缩放） |
| F7 | `F7_phase_diagram.png` | `E7/phase.csv` | $V$–$w_{\min}$ 相图（uniform / hotspot），白虚线为 $\mathcal V_{\text{thr}}$ |
| F8 | `F8_c0_strategies.png` | `E4/c0_scan_S2/c0_scan.json` | $c_0\in[0,10]$M 对 $E_w$ 与成本的影响（仅 `marginal_plus_fixed`；无交叉点） |

## 需要一并披露的图外信息

- F2 **没有观测时间序列**，只能标 MODEL；观测只有长期速率（见 `results/validation/T9_report.md`）。
- F4 的 S2/S3 在 ~1.36 yr 处有质量点（慢性侵蚀决定的首次失守），风暴只把约 10–20% 的实现提前。
- F7 关闭了风暴（确定性相图），与 E0–E4 的随机情景不是同一口径。
- F8 的 $E_b$ 在所有 $c_0$ 下为 0（S2 + 2.45e6 m³ 已消除建筑风险），因此左图用 $E_w$。
