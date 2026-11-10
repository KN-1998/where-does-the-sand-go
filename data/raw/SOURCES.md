# data/raw/SOURCES.md — 原始数据来源登记

> 大体积原始文件不入 git；本文件只登记来源、下载方式与本地落点。
> 全部数值与出处的逐条台账见 `资料/00_数据主表.md` 与 `ledger/claims.csv`。

| 数据 | 来源 | 本地落点 | 备注 |
|---|---|---|---|
| USGS OFR 2015-1002 历史岸线（1978–2002） | https://pubs.usgs.gov/of/2015/1002/ | `资料/06_原始摘录/_gis/` | shapefile + transect DBF；已提取 14 条岸线 |
| NC DEQ 2011/2019 侵蚀速率报告 | NC DEQ | `资料/06_原始摘录/_pdf/deq2011_erosion.pdf`、`deq2019_erosion.pdf` | 逐段速率表尚未数字化 |
| NOAA Duck Pier 8651370 相对海平面 | NOAA CO-OPS | `资料/02_海平面与潮位/` | 4.88±0.56 mm/yr（1978–2023） |
| NDBC 41025 波浪气候摘要 | https://www.ndbc.noaa.gov/data/climatic/41025.txt | `资料/06_原始摘录/_txt/41025_climate.txt` | 外海 Hs≈1.26 m，不等于近岸 Hb |
| CSE Rodanthe/Buxton 补沙与沙源 | CSE 2013/2023 | `资料/06_原始摘录/_pdf/` | 3.2M cy 本地沙源、3.8M cy 五年需求 |
| 2026 Buxton/Avon 工程成本 | Outer Banks Voice 报道 | `ledger/claims.csv` N17/N18 | all-in 26.8–27.6 \$/m³ |

## 下载与校验建议

- 下载后记录 URL、访问日期、文件 SHA-256；
- 放入 `data/raw/` 或 `资料/06_原始摘录/` 对应子目录；
- 不要修改原始文件；清洗脚本输出到 `data/processed/`。
