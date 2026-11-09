# 原始摘录清单（`_pdf` / `_txt`）

> 所有下载文件的原始副本。**不要改**，需要引用时从这里取。
> 下载时间：2026-11-09。

| 文件 | 大小 | 页数 | 内容 | 在哪个文件里被引用 |
|---|---|---|---|---|
| `deq2011_erosion.pdf` | 30.3 MB | 125 | NC DEQ 2011 长期平均年侵蚀率研究（法定 setback 依据） | `01_岸线侵蚀速率/DEQ_2011_2019_摘录.md` |
| `deq2019_erosion.pdf` | 23.3 MB | 190 | NC DEQ 2019 版（更新到 2016 岸线） | 同上 |
| `rodanthe_erosion_map.pdf` | 1.9 MB | 1 | Rodanthe 侵蚀率等值线图（标注 2.0–14.0 ft/yr） | `00_数据主表.md` E 系列 |
| `ncbiwa_rodanthe_2024.pdf` | 3.5 MB | 15 | NCBIWA 演示：Rodanthe 受威胁建筑（含 DCM "imminently threatened" 判据） | 风险背景 |
| `usgs_ofr2015_1154_noreaster.pdf` | 10.4 MB | 41 | USGS 全国温带风暴侵蚀评估（方法学参考） | `03_波浪与风暴` |
| `usgs_pp1827_outerbanks.pdf` | 53.8 MB | — | USGS Professional Paper 1827《The Outer Banks of North Carolina》 | `03_波浪与风暴` W3 |

文本提取版在 `_txt/`（UTF-8），可直接 grep。

---

## 下载失败（记录在案）

| 目标 | 状态 | 备注 |
|---|---|---|
| `darenc.gov/.../Rodanthe Sand Needs Assessment` | **403** | ✅ 2026-11-09 已通过代理抓取到 CSE 2023 PDF 全文；`00_数据主表.md` N1–N4 已升级为 **全文** |
| `coastalreview.org` 各文章 | **403**（Cloudflare） | 只能用搜索引擎摘要 |
| NOAA 官方 sltrends 站页 | JS 渲染，取不到数 | 改用 sealevel.info 的 NOAA 汇总表 |

---

## 复现下载

```powershell
# 需要浏览器 UA，否则 DEQ 会 403
$ua='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/124.0 Safari/537.36'
Invoke-WebRequest 'https://www.deq.nc.gov/coastal-management/documents/oceanfront-long-term-average-annual-erosion-rate-and-setbacks-2019/download' -OutFile deq2019_erosion.pdf -UserAgent $ua
```

文本提取（PyMuPDF）：

```python
import pymupdf
doc = pymupdf.open("deq2019_erosion.pdf")
open("deq2019_erosion.txt","w",encoding="utf-8").write(
    "".join(f"\n===== PAGE {i+1} =====\n"+p.get_text() for i,p in enumerate(doc)))
```
