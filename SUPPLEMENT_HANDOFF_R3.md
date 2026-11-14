# R3 补充计算交付（2026-11-14）

R2 模型冻结源码保持 `5ff6da62fbd11a0d481f990140883a2640cef1b911370f4521598e56ef5dd2be`。新增工具的指纹和运行提交见 `CODE_VERSION_R3.json`。新数值全部来自 `results/caliber_R2/` 的1000对同种子实际运行，不混用R1。

## 结果

| 指标 | 结果 |
|---|---:|
| 无风暴平均后退 A | 2.2115896952 m/yr |
| 有风暴平均后退 B | 2.3600747479 m/yr |
| 配对增量 mean(B_i-A_i) | 0.1484850527 m/yr |
| 增量MCSE | 0.0024218602 m/yr |
| 增量均值95%CI | [0.1437382067, 0.1532318987] m/yr |
| 有风暴总后退相对场均值的偏差 | +2.0087633% |
| 风暴增量 / 场均值 | 6.4179224% |
| 新运行全域/中央最大守恒残差 | 3.57395038e-8 |

`bias_vs_field` 是逐对重构 `(A_i+(B_i-A_i)-2.3136)/2.3136` 的均值；`storm_contribution_relative` 是 `(B_i-A_i)/2.3136` 的均值。原需求中0.14 m/yr与1.6%并非同一分子：0.14/2.3136约6%，故论文不能把总偏差写成风暴增量比例。

CI只含固定参数下的风暴抽样误差，不代表实测验证。后退率按未裁零的岸线位移计算。L0使用未缩放侵蚀高斯场（sigma_h=600 m），与初始滩宽的sigma_w=700 m为两个不同参数；网格场均值2.3136036605，偏差分母按需求固定2.3136。

## 论文建议替换句

> The paired no-storm / with-storm ensemble in `results/caliber_R2/` gives mean retreat rates of 2.2116 and 2.3601 m/yr, respectively. The realised storm increment is 0.1485 m/yr (6.42% of the corridor field mean), while the total with-storm retreat exceeds that field mean by 2.01%.

## 实现与复现

L0定义放在 `configs/caliber_A.yaml`、`caliber_B.yaml`，A/B逐字仅差storm_enabled。独立 `tools/caliber_r2.py` 子类返回原始rho_base，并调用冻结R2的S1平稳泊松生成分支，传入L0频率/强度。这样保留原R2的src/参数字节和缓存指纹。原仓库入口实际为 `src.exp`，本诊断的统一入口如下：

```powershell
python -m pip install -r requirements.txt
python tools/check_release.py
python tools/caliber_r2.py --n 1000 --seed 42 --workers 8
python tools/check_caliber_r2.py
python -X utf8 -m unittest discover -s tests -v
python tools/package_r3.py
python tools/verify_handoff.py dist/supplement_handoff_20261114_r3.zip --out dist/HANDOFF_VERIFICATION_R3.json
```

无 `.git` 的ZIP解压目录使用 `python tools/check_caliber_r2.py --skip-git`；仍检查冻结源码、新工具字节及全部样本统计，但明确跳过Git提交祖先校验。完整clone默认严格验证提交。

诊断：9km域、360格、dx=25m、dt=.02yr、open、15yr、无补沙、lambda=.4/yr、对数正态中位8m，无强制事件。A_det/B_det为seed42；MC种子为 `(42*1000003+i) mod 2^32`。确定性完整时空矩阵保留于ZIP，Git保留CSV/JSON/YAML轻量证据。

## 任务回执

- A：R2轻量结果已入库，保留CSV/JSON/MD/LOG及17组PNG/PDF，额外保留门禁需要的YAML重放配置。默认门禁目录已修正，支持从其它工作目录调用。
- B：1000对MC及seed42确定性对照完成；见 `results/caliber_R2/summary.json`、`paired_differences.csv`、A_mc/B_mc/runs.csv。
- C：完成 `results/release_20261113_r2/layout_quantiles.csv`，三布置各1000个配对种子的E_w P10/P50/P90。上尾很宽，不应只报告中位数。
- D：可选的新规则100配对种子敏感性未执行；不据现有best-then-veto诊断推断替代规则结果。
- E：原R2 ZIP的transport SHA、637个payload与冻结源码重算均PASS；回执 `results/release_20261113_r2/original_archive_verification.json`。R3 ZIP逐项hash另行校验。

未找到本次论文可编辑源文件；已提供替换文案，未修改论文表号。R2既有数值与审计记录不覆写为新实验结论。
