# 原始摘录清单（`_pdf` / `_txt` / `_gis`）

> 所有下载文件的原始副本。**不要改**，需要引用时从这里取。
> 下载时间：2026-11-09（第 5 轮检索新增 6 份全文 + 1 份浮标表 + 1 套 GIS）。

## 1. 本地确实存在的文件（`_pdf/`）

| 文件 | 大小 | 页数 | 内容 | 被引用处 |
|---|---|---|---|---|
| `usgs_ofr2015_1002.pdf` | 5.1 MB | 19 | USGS 1978–2002 Hatteras 岸线变化（含 14 条岸线数据） | E12、VAL-1 |
| `cse2013_rodanthe_buxton.pdf` | 8.8 MB | 159 | CSE 2013 Rodanthe/Buxton 可行性研究（年损失、5/10 年方案、成本、$H$ 比值） | N20、P4 背景 |
| `flynn2023_caha.pdf` | 9.9 MB | 24 | NPS/ODU 2023 CAHA 海岸科学（1998–2022 热点速率表） | E11 |
| `stauble2007_fill.pdf` | 1.3 MB | 16 | Dare County 补沙物源适应性（670 个底质样） | P3 背景 |
| `kittyhawk_2021_monitoring.pdf` | 7.8 MB | 45 | Kitty Hawk/KDH 2017 工程 2021 监测（3.3 年留存率） | N19 |
| `crc2534_erosion_2025.pdf` | 12 MB | 44 | NC DEQ 2025 侵蚀率/setback factor 更新简报（Waves–Rodanthe 上调 1–1.5） | E13 |
| `41025_climate.txt` | 278 KB | — | NDBC 41025 气候摘要（波高/风速频数表） | W9 |
| `usgs_shorelines.zip` | 1.4 MB | — | USGS 14 条岸线 + baseline + index 的 shapefile | VAL-1 |

解压后的 GIS 在 `_gis/`（已加入 `.gitignore`）；文本提取在 `_txt/`。

## 2. 已核对、但本地副本缺失的旧文件（需重下再引用）

> 第 2 轮曾下载并核对，但文件未随仓库保存；`00_数据主表.md` 的 E1–E6、N1–N4 数值已逐条核对，**不依赖本地副本**。若论文要附原文页码，请按 §4 重新下载。

| 文件 | 内容 | 状态 |
|---|---|---|
| `deq2011_erosion.pdf` | NC DEQ 2011 长期侵蚀率（125 页） | 数值已核对；本地缺失 |
| `deq2019_erosion.pdf` | NC DEQ 2019 版（190 页） | 数值已核对；本地缺失 |
| `rodanthe_erosion_map.pdf` | Rodanthe 侵蚀率等值线图 | 数值已核对；本地缺失 |
| `ncbiwa_rodanthe_2024.pdf` | NCBIWA 受威胁建筑演示 | 背景已引用；本地缺失 |
| `usgs_ofr2015_1154_noreaster.pdf` | USGS 温带风暴侵蚀评估 | 方法学参考；本地缺失 |
| `usgs_pp1827_outerbanks.pdf` | USGS PP 1827《The Outer Banks》 | W3 引用；本地缺失 |

## 3. 下载失败（记录在案）

| 目标 | 状态 | 备注 |
|---|---|---|
| `darenc.gov/.../Rodanthe Sand Needs Assessment` | **403** | ✅ 已通过代理抓取 CSE 2023 PDF 全文；N1–N4 已升级为全文 |
| `nagsheadnc.gov/.../July-2017` | **0 字节** | 站点拦截；改用 Kitty Hawk 2021 监测报告（N19）替代留存率证据 |
| NOAA 官方 sltrends 站页 | JS 渲染 | 改用 ECU LRTMP 2025 幻灯片逐字引用的 NOAA 数值（S4） |

## 4. 复现下载

```bash
# USGS 2015-1002 报告 + 岸线数据
curl -L -o usgs_ofr2015_1002.pdf https://pubs.usgs.gov/of/2015/1002/pdf/ofr2015-1002.pdf
curl -L -o usgs_shorelines.zip    https://pubs.usgs.gov/of/2015/1002/downloads/ofr2015-1002.zip

# CSE 2013 可行性报告
curl -L -o cse2013_rodanthe_buxton.pdf https://islandfreepress.org/wp-content/uploads/2025/03/DareCounty2013-12-20_UPDATEReport_REDUCED-1.pdf

# NPS Flynn 2023
curl -L -o flynn2023_caha.pdf "https://irma.nps.gov/DataStore/FileSource/Get/2298825?filename=Flynn_et_al_2023_SEG.pdf"

# NDBC 41025 气候表
curl -L -o 41025_climate.txt https://www.ndbc.noaa.gov/data/climatic/41025.txt
```

## 5. 文本提取

已用 `pypdf` 提取到 `_txt/`（`fitz` 在本机对部分 PDF 会段错误，改用 `pypdf`）：

```python
from pypdf import PdfReader
r = PdfReader("flynn2023_caha.pdf")
open("flynn2023_caha.txt","w",encoding="utf-8").write(
    "\n".join((p.extract_text() or "") for p in r.pages))
```
