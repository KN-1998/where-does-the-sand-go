# USGS Hatteras 岸线数据（1978–2002）使用说明

> 来源：USGS Open-File Report 2015-1002，*Quantification of Shoreline Change Along Hatteras Island, North Carolina—Oregon Inlet to Cape Hatteras, 1978–2002, and Associated Vector Shoreline Data*。
> 下载：`资料/06_原始摘录/_pdf/usgs_shorelines.zip`（1.4 MB），解压到 `资料/06_原始摘录/_gis/`。
> 用途：**Q3 的独立验证集**（VAL-1）；不是 $\rho_e$ 的标定数据。

---

## 1. 数据内容

| 文件 | 内容 |
|---|---|
| `Hatteras_Shorelines_1978_2002.shp` | **14 条 HWL 岸线**（PolyLine），1987–2002，WGS84 经纬度 |
| `Hatteras_Baseline.shp` | 2 条参考基线（DSAS 的 transect 起点） |
| `Hatteras_Index.shp` | 6 个分区多边形（Buxton、Cape Hatteras、Little Kinnakeet 等） |

**属性字段**：`Id`（记录号）、`DATE_`（MM/DD/YYYY）、`UNCERT`（位置不确定度，全为 **1.6 m**）、`Shape_Leng`。

**覆盖范围**：经度 −75.545 至 −75.460，纬度 35.215 至 35.778（Oregon Inlet 至 Cape Hatteras），Rodanthe 在其中。

**14 个时刻**：
1978-12-02、1979-09-20、1984-09-19、1985-08-23、1987-07-10、1989-07-30、1991-10-19、1992-10-02、1993-09-02、1995-10-18、1996-10-14、1997-10-12、1998-10-02、2002-10-18。

> 注意：文件名叫 "1978–2002"，但最早的岸线是 1978-12-02，最晚 2002-10-18；中间有 1980–1983、1986、1988、1990、1994、1999–2001 的空缺。**回归时用实际日期，不要按等间隔处理。**

---

## 2. 官方统计（报告 Table 3，1978–2002）

| 区域 | Transects | 侵蚀比例 | 平均 (m/yr) | Max | Min |
|---|---|---|---|---|---|
| Hatteras Island | 1217 | 83% | **−1.5±0.2** | +2.9 | −7.9 |
| Oregon Inlet | 23 | 100% | −15.4±9.7 | −4.3 | −76.6 |
| Cape Hatteras | 64 | 27% | +6.1±3.8 | +19.4 | −8.1 |
| 全研究区 | 1304 | 80% | −1.4±0.3 | +19.4 | −76.6 |

- **Rodanthe 的高侵蚀出现在 1989–2002 子期**（报告 fig. 5），但报告没有给出 Rodanthe 单段的均值——需要自己按 transect 算。
- Oregon Inlet 的 −76.6 m/yr 是 inlet 迁移造成的，**不要**混入 Rodanthe 段。

---

## 3. 怎么用（给编程手）

1. 以 `Hatteras_Baseline.shp` 为参考线，在 Rodanthe 段（约 lat 35.57–35.64）每 **50–100 m** 布一条 shore-normal transect。
2. 对每条 transect，求它与 14 条岸线的交点，得到 $y_i(t_k)$（沿岸坐标 → 离岸距离）。
3. 对每条 transect 做线性回归，得 LRR（m/yr）；再与 DEQ 的段平均、与模型的"无补沙基线"对比。
4. 报告时区分：
   - **USGS LRR**（1978–2002，HWL，航片）；
   - **DEQ 法定速率**（长期，blocked，17 点平滑）；
   - **模型基线**（$\rho_e(x)$，2027–2042 情景）。
   三者口径不同，**不能直接说"模型验证了 DEQ"**，只能说"在同一量级/同一带内"。

> **不要**用"按固定纬度截取最东侧交点"的临时做法（agent 只用于确认数据可用）：它在 35.575/35.585 会跳到另一条岸线分支，给出 +0.8/+0.3 m/yr 的假结果。必须用 baseline + 正交 transect。

---

## 4. 已知坑

- **多段 polyline**：每条岸线有多个 part（35 个左右），直接按点序插值会跨 part 连线；必须按 part 分别处理。
- **HWL ≠ MHW**：USGS 用的是湿/干线（HWL），比 MHW 略向陆；与 DEQ 的 MHW/lidar 口径不同，系统偏差约几米，不影响速率。
- **不确定度 1.6 m**：单条岸线的位置噪声；14 个时刻回归的速率标准误约 $1.6/\sqrt{14}/\Delta t$，量级 0.1–0.2 m/yr。
- **2002 年后的变化**：这份数据到 2002 为止；2027–2042 的预测不能用它直接验证，只能验证"模型在历史期的行为"。
