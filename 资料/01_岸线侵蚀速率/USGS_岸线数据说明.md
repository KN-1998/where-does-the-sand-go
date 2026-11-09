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

**属性字段**：`Id`（记录号）、`DATE_`（MM/DD/YYYY）、`UNCERT`（**DBF 字段为 1.6 m**；但报告 Table 2 与元数据给 **4.5–4.8 m**，见下）、`Shape_Leng`。

> **⚠ 三个不确定度数值（审查 P1）**：DBF 的 `UNCERT=1.6 m`；报告 Table 2 的 HWL 项 4.5 m、总 RSS **4.8 m**；元数据 `Horizontal_Positional_Accuracy_Value=4.8`。1.6 m 与"仅地理配准+数字化"的量级接近，可能漏了 HWL 项。**主量级用 4.5–4.8 m**，1.6 只作字段原值披露。

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

> **更省时的第一条路（2026-11-09 新增）**：`_gis/hatteras_transects/Hatteras_Transects.dbf` 已有 **1308 条现成 transect**，字段含 `LRR78_2002`、`LRR89_2002`、`LRR78_1989`、`DAS_km`、`StartX/StartY`（**UTM18N NAD83 米**，不是经纬度）。先用它做本地速率核对，不必从零布 transect。
>
> 我用 Rodanthe 5 km 窗口（UTM northing ≈ 3,937,500–3,942,500，DAS ≈ 20.8 km）算得：
> **LRR78_2002 均值 −3.43 m/yr（中位 −3.43，100% 侵蚀）；LRR89_2002 均值 −4.58 m/yr（中位 −5.04）**，n=101。
> 这说明 Rodanthe 段的真实速率**高于全岛平均 −1.5**，也高于我们早先的 $\rho_c=2.3$——**走廊参数可能偏低，Q-40 需重新标定**。
> 这些是**预计算 LRR**，不是我从岸线重建的交点；用于初筛足够，正式验证仍应说明其方法与不确定度。

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
- **岸线指标不同**：USGS 用湿/干线（HWL）；DEQ **2011 版也用 wet-dry line + endpoint 方法**，但不同更新版可能改用 lidar/MHW。不能笼统写"DEQ 是 MHW/lidar"；也不能假设固定偏移，必须逐版核对方法。系统偏差约几米，对速率影响较小，但要在论文里说明。
- **不确定度 4.5–4.8 m（不是 1.6 m）**：单条岸线的位置噪声；斜率的独立 OLS 标准误应按
  $$\mathrm{SE}(b)=\frac{\sigma_{\text{position}}}{\sqrt{\sum_i(t_i-\bar t)^2}}$$
  计算，不能简单用 $\sigma/\sqrt{n}/\Delta t$。14 个不等间隔日期、$\sigma=4.6$ m 时，单条 transect 的 SE 约 0.3–0.5 m/yr；空间平均还要考虑相邻 transect 相关，官方报告用了有效独立样本数。
- **2002 年后的变化**：这份数据到 2002 为止；2027–2042 的预测不能用它直接验证，只能验证"模型在历史期的行为"。
