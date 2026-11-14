# R2 caliber diagnostic

A/B 的唯一配置差别为 storm_enabled；不用 no_storm.yaml，因为它继承 S1 的目标速率扣风暴缩放，无法提供要求的未缩放慢性场。

复现：在仓库根目录执行 `python tools/caliber_r2.py --n 1000 --seed 42 --workers 8`。L0_diag 定义放在 caliber_A/B.yaml 中，工具子类只覆盖 _rho 返回原始 rho_base；事件用冻结 S1 平稳泊松生成器传入 L0 频率/强度，无强制事件。src/ 与 modeling/params.yaml 保持 R2 字节不变；source_sha256 对应 CODE_VERSION.json，diagnostic_sha256 单独标识新增工具。

9 km 域、360 格、dx=25 m、dt=0.02 yr、open、15 yr、无补沙。lambda=0.4/yr，中位8 m，sigma_ln=ln(25/8)/1.645（约0.6927，沿用 R2 的95分位近似）。rho 场为1.7[1+1.2 exp(-x²/(2*600²))]；分母按要求使用2.3136 m/yr，另报 field_mean_rho_grid 实际网格均值。侵蚀热点 sigma_h=600 m 与初始滩宽 sigma_w=700 m 为原R2不同参数。

MC 每个配对种子分别实际运行 A/B，不复用无风暴输出；原始样本在 A_mc/B_mc/runs.csv。贡献与偏差从 paired_differences.csv 的逐对差计算。后退率采用原始 y（耗尽后允许负滩宽），不将滩宽裁零；CI95 仅反映固定参数下风暴采样误差。bias_vs_field=mean[(A_i+(B_i-A_i)-2.3136)/2.3136] 为有风暴总后退相对场均值的偏差，与R3所举R1约1.6%的口径一致；storm_contribution_relative=mean[(B_i-A_i)/2.3136] 单独报告增量贡献占比。二者不可混用。
