# R2 当前交付状态（最终检查已完成，优先读本段）

所有科学计算已结束，未留下运行中的批算。源码SHA256仍为5ff6da62fbd11a0d481f990140883a2640cef1b911370f4521598e56ef5dd2be。审查起点为GitHub code@1e32280、main@bce02d5；后续GitHub分支与附件发布见PROGRAMMING_HANDOFF_R2.md。

- 55项unittest、参考离散和67项合同检查通过；47组确定性、18组/18000次MC完整性与数值审计PASS，MC全域/中央最大相对收支残差2.10711732506752e-8。
- OAT1040、时机3000、三组两次scramble的N512 Sobol、联合不确定性3000、持久性4096、监测/预报500、高斯足迹1200均完成。核心一阶/总阶稳定性：transport6/6、storm5/6、economy8/8；二阶分别3/3、1/3、6/6，未稳定值保留。
- 17对正式图由MATLAB R2025a生成，PDF渲染接触表均已目视检查；visual_QA中所有图哈希与当前文件一致。47份独立配置导出，S2 adaptive独立YAML实际重放，场NPZ逐字节一致。
- 修复最终check_release的分组变量复用错误。verify_handoff增加从ZIP内源码实际重算源码树哈希，而不只比对元数据。
- 新增policy_rule_diagnostic.py与结果：S3 seed42第9年首选保护期q10=2.323被否，另一个同价正收益候选q10=3.614可通过。这符合合同先择优后否决，属于规则改进点；未改变主算语义。建议先筛可行候选后择优，再另行配对检验。
- 本轮检查与结果.md、PROGRESS.md、CODE_VERSION.json、REPRODUCE.md、建模手待核实事项_R2.md已更新。现场独立验证缺失、历史固定场留出失败(R²=-4.295)和其他假设均明确保留；不能声称全部科学问题已解决。
- 交接文件：dist/review_handoff_20261113_r2.zip（轻量）、dist/programming_handoff_20261113_r2.zip（含全部场），校验入口dist/HANDOFF_VERIFICATION_R2.json及各自.sha256。仅使用R2目录，不混用R1结果。

下面是已完成的历史断点，不应照其中待办重复计算。

---

# R2 历史工作断点（10:50）

生产src指纹仍5ff6da62fbd11a0d481f990140883a2640cef1b911370f4521598e56ef5dd2be，没有改src，不必重跑已算数据。Git ls-remote已再核code=1e32280、main=bce02d5，无新提交。禁止子代理，未推送。当前root=F:/数模/1/数学建模acm/数学建模acm。

新增完成：
- 发现并修复tools/analyze_sensitivity_r2.py的JSON参数排序/AB矩阵顺序错配风险，改从CSV表头读顺序，排序行索引，所有一/总/二阶指数逐项对照已保存原始指数。storm实测最大误差7.8e-16。加入二阶收敛诊断；新增2回归测试。
- 补合同高斯足迹敏感性tools/footprint_sensitivity_r2.py：三固定策略×uniform/σ1/2/5km×100同标记种子=1200次，已完成于footprint/，含events.csv和comparison.csv。主生成器仍uniform，专用驱动明确传events；峰值归一化不是等能量。新增1测试。
- 当前55项unit全部PASS（tests.log），参考离散和67合同原日志PASS；上游17 pytest重跑PASS在upstream_tests.log。
- 另修tools/run_ensembles_r2.py缓存只核src/n、不核YAML的问题，当前有效快照及SHA全部核对才可续算跳过；新增1参数改变缓存失效测试。16个已完成组真实快照检查全部一致。
- tools/summarize_supplements_r2.py已生成policy/joint/phase汇总，默认/1万/10万监测费在100种子风险相同，refined均值改善MC区间跨0，不夸大。
- check_release.py强化rep2、scramble、矩阵索引、nonfinite、补充配对种子/成本/资源及足迹检查。全局驱动增加输出目录锁，支持同一root后续缓存聚合等待。
- MATLAB新增F17足迹图，batch_design预期已改17；当前tests README54，英文图注17，REPRODUCE新增补充/足迹/包验证命令。PROGRAMMER_DECISIONS前部R1已明确历史标签。
- tools/build_release_report_r2.py现在动态读取测试数，补监测比较及二阶稳定性，前置最新PROGRESS；尚未运行最终报告。
- tools/verify_handoff.py将验证两个ZIP的外部SHA和每个内部载荷；package_handoff现在收全部R2兄弟日志。

当前运行sessions（write_stdin，不是functions.wait）：
- 26665：18MC+OAT+timing。已16组MC，尚缺MC_S3_targeted和MC_S3_adaptive；OAT1040完成，timing3000仍算。日志results/release_20261113_r2_ensembles.log。
- 96990：原串行全球队列，transport×2、storm×2均完成；正在GLOBAL_economy（约960/5120），之后会进入rep2（遇目录锁等待，不会重复写）。
- 57602：并行提前跑GLOBAL_economy_rep2（约832/5120），8workers；日志..._global_economy_rep2_parallel.log。原队列之后使用缓存零重算。
- 16188：后台等待18MC和timing summary，然后build_report_tables、export_replay_configs、MATLAB17图，日志结果目录tables.log/replay_export.log/matlab_figures.log。
- 32087足迹、19197 tests54、81759上游tests均已退出0，已取exit。

待完成：
1 等计算，约每60s用户中文有意义更新，不急停进程。不要因耗时减少原定样本。
2 全球都结束后运行analyze_sensitivity_r2.py；再次build_report_tables（提前绘图前那次可能没有经济排名，因此必须再跑），export_replay_configs。
3 确认MATLAB17 PNG/PDF成功；用PIL接触表（仅QA，科学图是MATLAB）和view_image目视检查全部图。写visual_QA.json，含status PASS、17图清单/哈希、所观察问题与修复。
4 src.exp.batch --stage audit；tools/check_release.py。修复工具问题不改src。确保full/central残差<1e-6、54+67PASS。
5 tools/build_release_report_r2.py（依赖3门禁PASS），更新WORKLOG完成；再audit刷新manifest（报告脚本新增validation_status），避免清单落后。
6 生成dist/review_handoff_20261113_r2.zip --lite及programming_handoff_20261113_r2.zip全包；verify_handoff两包输出dist/HANDOFF_VERIFICATION_R2.json。不要推GitHub。
7 最终中文简述已修bug、完整计算/54测试/17MATLAB图和审计，点开本轮检查与结果.md、轻量包、REPRODUCE、建模手待核实事项。必须说历史固定速率holdout失败(R²−4.295)，缺完整现场独立验证，不能声称所有科学问题解决。

下面保留先前工作记录，过时的51/16数及session状态以本段为准。

---

# 先前R2工作断点

源码冻结 SHA256：5ff6da62fbd11a0d481f990140883a2640cef1b911370f4521598e56ef5dd2be

任务：结合 origin/code@1e32280 修复并完成本地编程交接。不要创建子代理，不要推送GitHub。正式图全用MATLAB。

已完成：上游17测试通过；对照证明collect=False使预报E_b恒零、事件向前摊；本地已实现完整独立风暴集合、观测状态、监测成本和近似后验更新；targeted动态追加；风险解析积分、自然恢复补沙删失、多段工程固定成本、MC有效快照/配对沙归因/时空分位等修复。详见 REVIEW_UPSTREAM_R2.md。

当前所有计算只写 results/release_20261113_r2/，旧结果和ZIP不覆盖。

运行中的exec sessions（functions工具 write_stdin轮询，不能wait）:
- 5724：确定性47组+fields.mat，日志 release_20261113_r2_deterministic.log（似已完成，待取exit）。
- 26665：18组MC各1000+OAT1040+timing3000，tools/run_ensembles_r2.py，10workers，日志 release_20261113_r2_ensembles.log。
- 96990：六组Sobol连续跑，transport及rep2 -> storm及rep2 -> economy及rep2；N512、8workers，第二scramble20261113；日志每组单独。后续组已支持JSONL逐点断点续算。
- 40097：joint/phase，再policy，4workers；补充实验3000 joint、4096phase、500policy。日志 _supplements.log 和 _policy_sensitivity.log。
- 80906：最新51项unittest、reference_contract、contract_verification、compileall、diffcheck，日志结果目录tests.log等；还需查看最后结果。

有一个可能已结束的诊断session52803，无科学输出依赖它。不要盲目停止python进程。

下一步：
1 等批算完成，及时中文commentary（约每60s），检查日志有无异常。源代码若再改，全部指纹会失效，避免无必要修改。
2 tools/analyze_sensitivity_r2.py生成嵌套64/128/256/512+独立scramble诊断；原始异常指数不裁剪。tools/build_report_tables.py和tools/export_replay_configs.py生成汇总和可搬迁快照。
3 matlab -batch "addpath('matlab'); plot_results('results/release_20261113_r2');"，预期16 PNG/PDF，逐图或接触表目视检查。matlab在PATH，实际D:/Program Files/MATLAB/R2025a/bin/matlab.exe。
4 src.exp.batch --stage audit；tools/check_release.py 动态读batch_design，预期47/18k/1040/3000/全球3×2×N512/补充3000+4096+500/16图。审计PASS只数值完整，不是经验验证和Sobol全收敛。
5 更新 本轮检查与结果.md、PROGRESS.md、tests/README.md 和论文结果使用说明，所有数字从R2读；保留R1历史。检查标准脚本和codehash。补充约54%测点误触发表是ASSUME统计例子。
6 tools/package_handoff.py --results results/release_20261113_r2 --out dist/review_handoff_20261113_r2.zip --lite；全包programming_handoff_20261113_r2.zip。验证SHA及包内manifest，最终中文简要给关键问题、修复和可点文件链接。没有真实剖面/建筑物监测数据，不能说独立现场验证完成。

不再需要skill（纯编程/标准MATLAB科学图）。文件和powershell允许无审批，勿传sandbox_permissions。脚本用python -X utf8。

## 10:24附近的补充状态
- 冻结源码仍为5ff6da62...；此后仅改tools、matlab、文档、tests（测试数已51），未改src，不需要重跑已算数据。
- 确定性session5724已退出0，47组全部为最新源指纹，fields.mat已导出；最新tests session80906退出0，51项+参考离散+67合同均通过。
- MATLAB环境session77206已退出0，matlab_environment.log显示25.1.0.2943329 R2025a，LICENSE_OK=1。
- global session96990已完成transport和transport_rep2，现在storm约2304/4096，随后storm_rep2、economy、economy_rep2；后面经济组每点12个求解，比前两组更费时。保留进程，未遇错误。
- MC session26665已完成S1/S2/S3的none，S1/S2/S3 once、S1/S2 repeat；其余仍在跑，最后还会OAT和timing。
- supplement session40097 first stage约7000/7096，将写joint3000+phase4096，再自动policy500。没有异常。
- 新增了真实资料的受限时间留出 tools/historical_holdout_r2.py，已执行并生成history/holdout_fit.json+holdout_predictions.csv。训练LRR78_1989均值侵蚀0.2702，测试LRR89_2002均值4.5793；固定高斯净速率场holdout RMSE4.7845，R²−4.295，失败，幅度落到0宽度不可识别。两期共用1989岸线，只是简化速率场检验，不直接否定完整PDE，也不构成完整独立验证。必须保留失败结论。
- tools/erosion_target_diagnostic.py已执行：baseline各1000，实际干滩宽后退均值1.5106/2.6279/3.1077，对名义目标1.7/3/4偏低11.1/12.4/22.3%，不能把目标值写成已实现。未改合同公式。
- 正式MATLAB已改F10为两面板：上原两段重叠分布，下新时间留出散点。F13共享色标动态取p90上限防止颜色截断。预期仍16对图。
- 新增 tools/build_release_report_r2.py：在audit/completeness/visual_QA均PASS后，读取真实R2汇总生成最终本轮检查与结果.md、validation_status.json和版本环境。它明确数值PASS但历史固定速率holdout失败和完整现场验证缺失。
- tools/export_replay_configs.py生成可搬迁的独立完整快照，避免自动生成inputs里原机绝对inherit路径；必须在check_release前运行。
- 正式图注PAPER_FIGURE_CAPTIONS_R2.md，模型数据限制VALIDATION_GAPS.md，建模手事项建模手待核实事项_R2.md，英文/中文边界都有。
- 出现短剩余窗口时adaptive的保护期q10只构成删失下界，<3不能保证3年会转评估，不等于观测到3年内失守；terminal-horizon偏差已记录，未改变src行为。不要为低影响日志分类重新冻结/重跑。
- 还需在最终结果上生成sensitivity_convergence.csv/json、mc_comparison.csv、portable snapshots，再MATLAB16图并目视检查，写visual_QA.json，audit/check_release，最终report和ZIP。inspect all logs for failures; don't claim full model independently validated.
