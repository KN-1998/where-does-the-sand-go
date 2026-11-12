# feedback/ — 编程手反馈与交接

> 2026-11-13，编程手 R1。两份主文档分别面向**建模手**与**主编程手**，另有一份存疑/重跑清单。

| 文件 | 读者 | 用途 |
|---|---|---|
| [`TO_MODELER.md`](TO_MODELER.md) | 建模手 | 合同符合性、9 条 `[自决]` 待裁决、结果与文档预期的 4 处不一致、数据请求、论文可用/不可用表述、数字溯源 |
| [`TO_CHIEF_CODER.md`](TO_CHIEF_CODER.md) | 主编程手 | 仓库/分支状态、架构与调用链、12 条必须保持的不变量、扩展指南、测试门禁、性能、技术债、8 个坑、接手清单 |
| [`RE_RUN_AND_OPEN_ISSUES.md`](RE_RUN_AND_OPEN_ISSUES.md) | 两位 | **所有存疑/需要重跑的点**：主动补跑、裁决触发矩阵、已确认不需重跑、数值存疑点、重跑纪律 |

## 相关入口

- 结果总表：[`../results/SUMMARY.md`](../results/SUMMARY.md)
- 审计报告：[`../results/validation/AUDIT.md`](../results/validation/AUDIT.md)
- 复现说明：[`../REPRODUCE.md`](../REPRODUCE.md)
- 进度台账：[`../PROGRESS.md`](../PROGRESS.md)

## 一键复核

```powershell
python -m exp.check_all     # 原型 + 17 测试 + 67 合同 + 2268 审计
```
