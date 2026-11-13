# R2 编程结果复现

最新结果目录：`results/release_20261113_r2/`。R1命令/结果保存在 `REPRODUCE_R1.md` 和旧结果目录，只作追溯。先读 `REVIEW_UPSTREAM_R2.md` 与 `PROGRAMMER_DECISIONS.md` 的 R2 部分。

## 环境和入口

在解压后的项目根目录运行，Python依赖见 requirements.txt；正式绘图使用 MATLAB R2025a，只依赖基础 MATLAB。默认完整批算较久，已有全部输出时可以直接审计和看图。

```powershell
python -m pip install -r requirements.txt
python -X utf8 -m unittest discover -s tests -v
python -X utf8 modeling/sanity/discrete_contract.py
python -X utf8 tools/verify_contract.py
```

单次运行/配对归因：

```powershell
python -X utf8 -m src.exp.run_one --config configs/S2.yaml --scenario S2 --strategy adaptive --bc open --seed 42 --t-end 15 --paired-retention --out results/my_run
```

## 从头重算新版

使用新目录可保留本次交付，以下命令给出交付目录名便于逐项核对。

```powershell
python -X utf8 -m src.exp.batch --root results/release_20261113_r2 --stage deterministic
python -X utf8 tools/run_ensembles_r2.py --root results/release_20261113_r2 --workers 10
```

后一个命令会完成18组各1000次MC、17参数的OAT（52取值×20种子）、1000组相同六场事件的早/均/晚对照。仅当源码指纹、完整样本量和当前有效参数快照都相同时才跳过已完成MC组；只改YAML也会使缓存失效。尚未结束的组会重跑，不会拼接不同版本。

每个 group∈{transport,storm,economy} 分别执行：

```powershell
python -X utf8 tools/parallel_global.py --group transport --root results/release_20261113_r2/GLOBAL_transport --power 9 --workers 8
python -X utf8 tools/parallel_global.py --group transport --root results/release_20261113_r2/GLOBAL_transport_rep2 --power 9 --workers 8 --design-seed 20261113
```

将 transport 在两个位置都替换成 storm、economy。每组N=512、两个固定风暴种子；原始设计矩阵足以重算一阶/总阶/二阶估计。正式解释以稳定性诊断为准。

```powershell
python -X utf8 tools/run_supplements_r2.py --root results/release_20261113_r2 --workers 8
python -X utf8 tools/summarize_supplements_r2.py --root results/release_20261113_r2
python -X utf8 tools/footprint_sensitivity_r2.py --root results/release_20261113_r2 --workers 4
python -X utf8 tools/historical_holdout_r2.py --root results/release_20261113_r2
python -X utf8 tools/analyze_sensitivity_r2.py --root results/release_20261113_r2
python -X utf8 tools/erosion_target_diagnostic.py --root results/release_20261113_r2
python -X utf8 tools/policy_rule_diagnostic.py --root results/release_20261113_r2
python -X utf8 tools/build_report_tables.py --root results/release_20261113_r2
python -X utf8 tools/export_replay_configs.py --root results/release_20261113_r2
```

补充实验：三情景各1000次参数+风暴联合不确定性；S2五个自适应设置各100个配对种子；8×8体积/初始滩宽、两种布置、各32场风暴序列的持久性相图。

## MATLAB绘图与最终审计

确定性批算已导出 fields.mat；若重新生成，请先导出。

```powershell
python -X utf8 -m src.exp.export_mat --root results/release_20261113_r2
matlab -batch "addpath('matlab'); plot_results('results/release_20261113_r2');"
python -X utf8 -m src.exp.batch --root results/release_20261113_r2 --stage audit
python -X utf8 tools/check_release.py --root results/release_20261113_r2
```

应得到17组 MATLAB PNG/PDF、audit.json 与 completeness.json。PASS 指数值/文件完整性，不代表现场验证通过，也不保证全部 Sobol 指数收敛。F17是高斯足迹专用驱动的结果；仅修改YAML中的phi_shape并不会改变主生成器。

F1/F13/F14热图的PDF采用300 dpi图像导出，避免MATLAB矢量网格在PDF查看器中出现细白缝；其余14张保留矢量文字与曲线。可用 `tools/qa_figures_r2.py --root results/release_20261113_r2` 生成PDF渲染接触表，依赖可选的Pillow、pypdf和Poppler；数值求解不需要这些绘图核验依赖。

## 按保存的参数重放与搬迁目录

各确定性运行目录另有不含 inherit/overrides 的 `resolved_config.yaml`，在其他盘符或机器解压后可直接作为 --config 使用。内部 `results/.../configs/` 是当时自动生成的输入，可能带原机绝对路径；移动后使用上述独立快照。MC目录的 `first_realization_config.yaml` 对应第一条 runs.csv；其他实现用该行 seed 覆盖。

results.json 不含运行时间，fields.npz 为确定性字段；meta.json 的运行耗时不要求相同。源码指纹为 src 下相对路径与所有Python字节的 SHA256；原运行的 Git HEAD 记录当时基线，R2 发布版本另见 PROGRAMMING_HANDOFF_R2.md。

逐字节复现测试限于相同环境、相同原始输入与Git元数据。搬迁后用独立快照重放时，输入文件MD5和Git记录可能合理变化，应对照科学字段、指标、事件表及源码SHA，而非要求整个results.json的元数据完全相同。旧 `src/exp/plot_results.py` 不用于本轮正式图。

## 包装交接包

```powershell
python -X utf8 tools/package_handoff.py --results results/release_20261113_r2 --out dist/review_handoff_20261113_r2.zip --lite
python -X utf8 tools/package_handoff.py --results results/release_20261113_r2 --out dist/programming_handoff_20261113_r2.zip
python -X utf8 tools/verify_handoff.py dist/review_handoff_20261113_r2.zip dist/programming_handoff_20261113_r2.zip --out dist/HANDOFF_VERIFICATION_R2.json
```

压缩包旁的 .sha256 和包内 PACKAGE_MANIFEST.json 用于核验。轻量包有源码、标量/集合结果、台账、事件、图表，省略 fields.npz/fields.mat；完整包额外保存全部场。GitHub 分支和附件下载见 PROGRAMMING_HANDOFF_R2.md。

verify_handoff除逐项校验载荷外，还从ZIP内的实际Python源码重新计算源码树SHA256，与CODE_VERSION及结果版本核对，不只相信包内声明的版本号。
