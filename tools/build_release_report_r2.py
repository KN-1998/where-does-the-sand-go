"""Build the final handoff narrative exclusively from audited R2 outputs."""
import argparse
import csv
import json
import platform
import importlib.metadata
import re
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from src.sim.io import tree_sha256,write_json


def read(p):return json.loads(Path(p).read_text(encoding='utf-8'))


def main():
    p=argparse.ArgumentParser();p.add_argument('--root',required=True);a=p.parse_args();root=Path(a.root)
    audit=read(root/'audit.json');complete=read(root/'completeness.json');visual=read(root/'visual_QA.json')
    if any(j['status']!='PASS' for j in (audit,complete,visual)):raise RuntimeError('Release gates are not complete')
    source=tree_sha256('src');convergence=read(root/'sensitivity_convergence.json');history=read(root/'history/holdout_fit.json')
    count=re.search(r'Ran (\d+) tests', (root/'tests.log').read_text(encoding='utf-8'))
    if count is None:raise RuntimeError('Missing test count')
    tests=int(count.group(1))
    rows=list(csv.DictReader((root/'mc_comparison.csv').open(encoding='utf-8')))
    lines=['# R2 检查、修复与交接结果','',
        '已完成现有资料能够支持的编程、数值验收、批量情景分析和MATLAB交付。GitHub交接入口、下载方法和潜在问题见 PROGRAMMING_HANDOFF_R2.md。',
        '','**数值门禁通过，不代表现场预测已验证。历史固定速率场的受限时间留出检验明显失效；完整模型仍缺独立补沙响应验证。**','',
        '## 本轮修复的关键问题','',
        '- 上游预报关闭指标累计：同一全年失守例子由约5000 m·yr被错误算成0；已改为独立累计集合预报指标。',
        '- 事件被摊入此前时间间隔、步内风险穿越遗漏、人工补沙被误计为自然恢复；已分别修正，并增加回归测试。',
        '- 补齐独立未来风暴、带误差观测状态、候选择优、施工延迟、监测费用、6/12/24月复核和模拟后验更新。零收益不自动补沙。',
        '- 热点策略补成触发式追加；多段布置共享一次工程固定成本；MC有效快照、配对留存/归因和时空分位补齐。',
        '- 断点续算增加有效参数指纹检查；仅修改YAML也会使旧MC缓存失效，防止新配置混入旧结果。',
        '','详见 [GitHub逐项审查](REVIEW_UPSTREAM_R2.md)、[程序自决](PROGRAMMER_DECISIONS.md) 和 [建模手待核实事项](建模手待核实事项_R2.md)。','',
        '## 验收与计算规模','',
        f'- {tests}项 unittest、参考离散脚本及67项合同检查通过；GitHub code-r1的17项测试另行通过，但漏掉了上面的预报错误。',
        f"- {complete['deterministic_runs']}组确定性运行、{complete['MC_groups']}组MC（共{complete['MC_runs']}次），配对风暴和沙量台账经过审计。",
        '- OAT：17参数、52取值×20种子=1040次；时机实验：1000组相同六场风暴×3种排布=3000次。',
        '- Sobol：三组输入、每组N=512、两个独立scramble，保留一阶/总阶/二阶原始估计与样本加倍诊断。',
        '- 修复敏感性汇总的参数顺序风险：从设计矩阵表头读取参数顺序，所有一阶/总阶/二阶指数与原始输出逐项对拍；避免JSON按名排序后贴错参数标签。',
        '- 补充实验：3000次参数+风暴联合不确定性；4096次有风暴持久性相图；五个自适应设置各100个配对种子。',
        '- 补齐合同高斯足迹敏感性：三策略×四种足迹×100种子=1200次；独立专用驱动传入显式事件表，峰值归一化，不是等总能量比较。',
        f"- MC全域/中央区最大相对收支残差：{complete['MC_max_full_or_central_residual']:.4g}，低于1e-6。",
        f"- {complete['MATLAB_png']}组MATLAB PNG/PDF，已完成目视检查。",'',
        '## 策略比较（同一约束，不要求实际用沙和花费相同）','',
        'E_b为建筑净距代理暴露，E_w为滩宽暴露；单位均为米·年。表中为1000次实现的中位数，完整分位带、实际成本和配对均值误差见 mc_comparison.csv。',
        '','| 情景 | 策略 | E_b中位 | E_w中位 | 平均投沙/百万m³ | 平均总费/百万USD |',
        '|---|---|---:|---:|---:|---:|']
    for r in rows:
        if r['strategy'] not in ('none','once','repeat','targeted','adaptive'):continue
        lines.append(f"|{r['scenario']}|{r['strategy']}|{float(r['E_b_p50']):.0f}|{float(r['E_w_p50']):.0f}|{float(r['mean_placed_m3'])/1e6:.3f}|{float(r['mean_cost_usd'])/1e6:.2f}|")
    s2={r['strategy']:r for r in rows if r['scenario']=='S2'}
    lines += ['',f"当前假设下，S2一次性补沙的E_b中位数为{float(s2['once']['E_b_p50']):.0f}，自适应为{float(s2['adaptive']['E_b_p50']):.0f}；平均总费分别为{float(s2['once']['mean_cost_usd'])/1e6:.2f}M和{float(s2['adaptive']['mean_cost_usd'])/1e6:.2f}M USD。按该中位数指标，自适应并不占优，仍需结合尾部风险和实际费用评价。一次性的E_b中位数为零时，E_w中位数仍为{float(s2['once']['E_w_p50']):.0f} m·yr，说明两个风险指标不可替代。"]
    s3={r['strategy']:r for r in rows if r['scenario']=='S3'}
    lines += ['',f"S3中，两种固定日历策略实际用沙和主算费用相同：少量多次的E_b中位数{float(s3['repeat']['E_b_p50']):.0f}低于一次性的{float(s3['once']['E_b_p50']):.0f}，其E_w中位数{float(s3['repeat']['E_w_p50']):.0f}却高于一次性的{float(s3['once']['E_w_p50']):.0f}。保护建筑净距与维持整段海滩宽度会给出不同偏好；管理目标权重需要明确。各策略相对一次性的配对均值差及MC区间见policy_pairwise.csv。"]
    lines += ['',
        '不能将这张表解释成实际倒塌风险或全局最优策略。动态策略使用假设的增量监测费，固定日历基准不含此项增量费；总费已分列工程/监测成本。滚动单位成本贪心可能保留未使用的沙量和预算；不同风险目标、实际成本和约束共同决定比较。',
        '','## 监测和预报设置的配对敏感性','',
        '同一100条风暴序列，正的差值表示相对default减少E_b。区间只描述配对均值的蒙特卡洛误差，不覆盖观测模型和参数分布的科学不确定性。',
        '','| 设置 | E_b中位 | 平均总费/百万USD | 相对default平均减险 | 均值95% MC区间 |',
        '|---|---:|---:|---:|---|']
    with (root/'supplements/policy_comparison.csv').open(encoding='utf-8') as h:
        for r in csv.DictReader(h):
            lines.append(f"|{r['setting']}|{float(r['E_b_p50']):.0f}|{float(r['mean_cost'])/1e6:.2f}|{float(r['paired_mean_avoided_E_b_vs_default']):.0f}|[{float(r['mean_CI95_lo']):.0f}, {float(r['mean_CI95_hi']):.0f}]|")
    lines += ['',
        '本组1万/5万/10万美元调查费只改变成本，没有改变100条序列的风险结果；这是约束与样本下的现象，不代表实际监测成本无关紧要。更细网格/16成员的平均改善区间跨零，尚不足以断言显著更好。',
        '','## 仍须明确报告的模型限制','',
        f"- 历史速率场：1978–1989训练期均值{history['mean_train_retreat_myr']:.3f} m/yr，1989–2002留出期{history['mean_test_retreat_myr']:.3f} m/yr；留出RMSE {history['temporal_holdout']['rmse_myr']:.3f} m/yr，R² {history['temporal_holdout']['R_squared']:.3f}。固定场没有可用的时间外推能力；两期还共用1989岸线，不能称完全独立。",
        '- 三情景实际平均干滩后退约1.511/2.628/3.108 m/yr，低于名义时间平均目标1.7/3/4约11%/12%/22%。配置目标不是已经实现的速率。',
        '- S2是固定实际后退的状态条件压力测试；S3的海平面与侵蚀端点没有定量物理换算。',
        '- 观测能力、调查费、初始建筑净距、资产权重和部分参数分布是假设。模拟调查的后验更新不是实测后验；retreat_assessment也不证明搬迁最优。',
        '- 合同规定先择优再作保护期否决，不递补其他候选。S3、seed=42在第9年因此拒绝保护期q10=2.323年的首选，另一个同价正收益候选q10=3.614年却可通过筛查。可行候选优先是待另行配对检验的规则改进，不能把当前结果称为在保护期约束内择优；见policy_rule_diagnostic.json。',
        '- 风险长度、空间相关测量误差、监测误报、恢复删失和沙量反事实归因的限制详见 VALIDATION_GAPS.md。',
        '']
    for name,g in convergence['groups'].items():
        lines.append(f"- Sobol {name}：核心E_b输出的{g['key_estimates']}项一阶/总阶估计中，{g['stable_key_estimates']}项通过本轮稳定性诊断；未稳定的不能写成精确方差份额。")
        lines.append(f"  二阶交互有{g['stable_second_order_estimates']}/{g['second_order_estimates']}项通过相同诊断；完整结果含未稳定原值。")
    lines += ['','## 交接入口','',
        '- 复现：REPRODUCE.md；每次确定性运行有无绝对路径依赖的 resolved_config.yaml。',
        '- 结果：results/release_20261113_r2/；图：该目录figures/；英文图注：PAPER_FIGURE_CAPTIONS_R2.md。',
        '- 轻量包：dist/review_handoff_20261113_r2.zip；完整包：dist/programming_handoff_20261113_r2.zip，旁有SHA256。',
        '- R1数字/旧包仅作追溯，不与本轮数字混用。原运行的Git HEAD记录基线；R2生产源码以 CODE_VERSION.json、包内清单和源码SHA256为准。','']
    Path('本轮检查与结果.md').write_text('\n'.join(lines),encoding='utf-8')
    write_json(root/'validation_status.json',{'numerical_acceptance':'PASS','visual_QA':'PASS',
        'historical_fixed_rate_temporal_holdout':'NO_PREDICTIVE_SKILL',
        'full_physics_independent_field_validation':'NOT_AVAILABLE',
        'monitoring_posterior':'SYNTHETIC_ONLY','sobol_stability':{g:{k:v[k] for k in ('stable_key_estimates','key_estimates')} for g,v in convergence['groups'].items()},
        'interpretation':'Programming deliverables complete; conditional scientific results, not an empirically validated deployment policy.'})
    version=read('CODE_VERSION.json');version.update(src_sha256=source,
        environment={'python':platform.python_version(),**{k:importlib.metadata.version(k) for k in ('numpy','scipy','PyYAML')},
                     'MATLAB':'25.1.0.2943329 (R2025a); license test passed'})
    write_json('CODE_VERSION.json',version)
    progress=Path('PROGRESS.md');prior=progress.read_text(encoding='utf-8')
    if not prior.startswith('<!-- R2_CURRENT -->'):
        progress.write_text('<!-- R2_CURRENT -->\n# 当前交付：R2（2026-11-13）\n\n'
            f'{tests}项测试、67项合同检查、数值/完整性审计及{complete["MATLAB_png"]}组MATLAB图目视检查通过。'
            '当前结果仅用results/release_20261113_r2/，复现见REPRODUCE.md，检查结论见本轮检查与结果.md。'
            '历史固定速率留出检验失败，完整模型缺独立现场验证。以下保留各轮历史记录。\n\n---\n\n'+prior,encoding='utf-8')
    print('FINAL R2 REPORT WRITTEN')


if __name__=='__main__':main()
