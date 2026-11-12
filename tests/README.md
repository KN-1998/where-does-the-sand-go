# tests/ — 编程手的验收测试

> 判据全部来自 `handoff/CODER_SPEC.md` §5 与 `modeling/MODEL_SPEC.md`。
> **不要改判据**；要改先走 §0.2 的上报流程。

## 命名约定

| 文件 | 覆盖 |
|---|---|
| `test_mass.py` | T1（闭合）、T3（零源项/衰减）、T13（侵蚀后回填） |
| `test_erf.py` | T2（对 erf 收敛，光滑高斯初值） |
| `test_refine.py` | T4（dx=50 vs 25，指标差 <2%） |
| `test_storm.py` | T6（回滩比 0.87）、T10（事件在步边界/终点） |
| `test_floor.py` | T11（V 下限、y 不截断、R_c 当前亏空） |
| `test_metrics.py` | T12（f_w(0)=0.3000、f_b(0)=0、删失语义） |
| `test_bc.py` | T7（边界通量 vs 半解析） |
| `test_repro.py` | T8（同 seed 两次结果逐字节相同） |

## 起点

把 `modeling/sanity/discrete_contract.py` 里的 `chk(...)` 改成 `assert`，
按上面拆到对应文件即可。它已经覆盖 T1/T3/T11/T13 四条。

## 硬要求

- 每条测试**必须有明确的 assert**，失败时进程退出码非 0；
- 打印实测值（`residual`、误差、格数），方便对拍；
- 不要在测试里读网络、不要依赖时间戳。

---

## 已落地（2026-11-12，编程手）

`python -m pytest tests -v -s` → **17 passed**（约 4 s）。日志：`results/validation/pytest.log`。
实际文件与覆盖：

| 文件 | 覆盖 | 实测（2026-11-12） |
|---|---|---|
| `test_mass.py` | T1、T3a/b/c、T13 | T1 $4.5\times10^{-9}$；T3a $2.0\times10^{-13}$；T3b $3.5\times10^{-14}$；T3c $1.2\times10^{-15}$；T13 $1.4\times10^{-14}$、$R_c$ 下降、$D_{\max}$ 单调 |
| `test_erf.py` | T2、T3(b′ 开边界对 erf) | 比 2.04 / 2.02；L2 相对 $6.4\times10^{-4}$ |
| `test_refine.py` | T4、T5 | $dx=50$ vs 25：$E_w$ 0.01%、$T_{\text{first,fail}}^w$ 0.07%、$R_{ret}(15)$ 0.04%；T5 6.16/7.34/7.38（+0.2%/+0.1%/+0.3%） |
| `test_storm.py` | T6、T10 | 0.869622（= $k/(k+\lambda)$）；事件在 1.00/1.01/5.00 各注入 1 次、注入量误差 0 |
| `test_floor.py` | T11 | $y_{\min}=-96$（未裁剪）；$V_{\text{book}}\ge V_{\min}$；$R_c$ 与台账一致；$risk_w/risk_b$ 按公式 |
| `test_metrics.py` | T12、T12b（恢复时长与删失） | $f_w(0)=0.3036$（连续重构；逐格值为 0.3000，二者都在 ±0.005 内）、$f_b(0)=0$；$T_{\text{recovery}}$ 中位 0.44 yr、$n=140$；删失语义互斥 |
| `test_bc.py` | T7 | open 外流 0.01%（相对已知损失）；zeroflux 严格 0 |
| `test_repro.py` | T8 | `results.json` 逐字节相同、`fields.npz` md5 相同 |

> T12 的说明：合同给的“离散值 0.3000（60 格）”与解析 0.3036 都落在 ±0.005 容差内；
> 本实现在**聚合指标**上用格心间分段线性重构（连续、无 1 格量化），逐点 `risk_w/risk_b`
> 仍是布尔指示量。判据未改。`test_handoff` 无；T9 是诊断不是通过/失败测试，见
> `results/validation/T9_report.md`。

