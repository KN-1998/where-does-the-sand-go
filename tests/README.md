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
