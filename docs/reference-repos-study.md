# 评审 §6 参考仓库：该套用什么、不该套用什么

> 来源：《EcoSentinel 技术评审与演进路线图》**§6 同源参考项目与技术借鉴**（L813–897）+ §7 扩展方向。
> 本文记录**我实际下载并读过的仓库**与**逐条对照结论**；没读过的只标注"未核实"，不替它背书。

## 1. 评审列出的全部项目（按它的五类）

| 类 | 项目 |
|---|---|
| 6.1 基准环境 | EnergyPlus(NREL) · **Sinergym** `ugr-sail/sinergym` · Energym `bsl546/energym` · BOPTEST `ibpsa/project1-boptest` · CityLearn `citylearn-project/CityLearn` · Beobench `david-woelfle/beobench` · FlexDRL `LBNL-ETA/FlexDRL` · rl-testbed-for-energyplus `IBM/rl-testbed-for-energyplus` |
| 6.2 热模型与辨识 | **rcmodel** `BFourcin/rcmodel` · rc-building(GitLab) · **GEKKO** `BYU-PRISM/GEKKO` · Open Energy Monitor |
| 6.3 舒适度 | **pythermalcomfort** `CenterForTheBuiltEnvironment/pythermalcomfort` · ASHRAE 55-2020 / ISO 7730 |
| 6.4 节能量核算 | **IPMVP**（Option A/B/C/D） · ASHRAE Guideline 14 |
| 6.5 硬件/边缘/可视化 | ESPHome + Home Assistant · ThingsBoard · Grafana + InfluxDB · `splatura/ESP32_Data_Logging_Webserver` · `Lemings/ESP32EnergyMonitor` |

## 2. 我实际下载并读过的（5 个 / 工具 1 个）

| 仓库 | 怎么拿的 | 读到了什么 |
|---|---|---|
| `pythermalcomfort` | 浅克隆（245 文件） | 用 ISO 7730 实算 PMV/PPD ⇒ 见 `docs/pmv-ppd-study.md` |
| `sinergym` | **稀疏克隆**（`--filter=blob:none --sparse`，只取 `config/utils/envs`） | 明文舒适区/设定值：`__init__.py:100-101` `range_comfort_summer=(23.0,26.0)`；`utils/controllers.py:44` `setpoints_summer=(23.0,26.0)` |
| `rcmodel` | 浅克隆（29 文件） | 3R2C 建模流程；`physical/room.py:18` 明写 `capacitance = 0 # Dummy Value, is changed during optimisation process` |
| `ESP32_Data_Logging_Webserver` | 浅克隆（5 文件） | 用的是 **同一个** `Adafruit_INA219` 驱动 + 一个 41.9 KB 单文件 .ino |
| 工具 `uv` | 本机已有 | 无 pip 的 venv 里也能 `uv run --with <pkg> python …` 做临时实验 |

## 3. 已落地的套用

1. **舒适度口径**（6.3）：把"自创 TCI"与 ISO 7730 对齐的实测证据写进 `docs/pmv-ppd-study.md`；
   两条**独立**来源（ISO 7730 数值解 23–26.5 ℃ / Sinergym 23–26 ℃）收敛，而项目 TCI 的可行带是 24–28 ℃
   ⇒ **偏暖约 1–1.5 ℃**。建议夏季舒适区取 **23–26 ℃**、设定值取 25 ℃。**待用户决策**（未改代码）。
2. **外部一致性**（6.1）：Sinergym 只作**配置级**参照（未跑 EnergyPlus）——这与评审"不要一上来就迁"的建议一致。

## 4. 我建议怎么套用（附对照证据）

### 4.1 rcmodel → 把"手拍常数"换成"辨识参数"（**最值得做的一条**）

- 现状（实测）：`core/thermal_model.py` 是**集中式 1R1C**，`C_air=25000 J/K`、`UA=U_WALL·A_WALL=1800 W/K`
  全部来自 `config/settings.py` 的**手拍值**；我们现在只能标"演示级、未标定"。
- rcmodel 的价值不在代码，而在**流程**：它的电容是"占位值、在优化中被拟合"的 ⇒ 用**实测数据拟合 R/C**，
  论文/材料里就能写"参数经 X 小时实测辨识（R²=…）"，而不是"取自演示级简化值"。
- 它还提示一个**结构性**问题：3R2C 把**墙体热容**作为独立节点；我们只有空气热容 ⇒ 无法复现真实建筑的
  **慢动态**（这正是当前"空调一动温度就立刻到位"的根源之一）。
- **建议**：先做"1R1C 参数辨识"（低风险，只要一段实测温度/功率序列）；确有需要再升到 2 状态模型。
- **不建议**整体引入该包：它带 `torch`/`shapely` 做平面几何，我们不需要那部分。

### 4.2 INA219 参考仓库 → **价值有限（如实说）**

- 实测：我们固件**已经**用的是同一个 Adafruit 驱动（`config.h:41-45` 的 `__has_include` 守卫 + `HAVE_INA219`），
  而且**已经是双通道**（`config.h:137-139`：主路 + 太阳能支路 `INA219_ADDR_SOLAR=0x41`）。
- 所以它对我们**没有可直接搬的代码**；真正有用的是 §6.5 提到的**校准方法**（openenergymonitor 的 burden/分流
  电阻与校准流程）。**待办**：核对固件里是否已有校准系数与实测标定步骤——我这次**只核实了驱动与地址**，
  **没有**核实校准系数是否存在，故不在此下结论。

### 4.3 IPMVP Option C / ASO → **零依赖、收益最大**（我建议列为下一步）

评审 §6.4 说得对：现在是"两次不同模式的仿真对比"，**接近 Option D 但模型未校准**，严格说不成立。
低成本做法（不需要任何新依赖）：
1. **ASO 交替实验**：仿真里隔天/隔周交替开关节能策略 ⇒ "关"的时段当 baseline、"开"的时段当报告期；
2. **回归 baseline**：以室外温度为自变量（线性/变点/多项式）拟合 baseline 能耗；
3. 对外写法改成"**17.6%（IPMVP Option C，3 天仿真，未覆盖全工况）**"，并给不确定度。
   （评审原话：哪怕只做这一处改写，"可信度都会提升一个数量级"。）

## 5. 明确**暂不套用**（附理由，避免被"看起来很强"的仓库带跑）

| 项目 | 为什么不现在做 |
|---|---|
| EnergyPlus / Energym / BOPTEST / Beobench | 安装重（EnergyPlus 本机装极痛苦，Beobench 要 Docker）；评审自己也建议"不要一上来就迁" |
| CityLearn | KPI/评分卡设计值得抄（能耗+碳+服务三维），但整个环境我们是**下一个候选**，不是现在 |
| FlexDRL / IBM rl-testbed-for-energyplus | 研究向、场景差异大（数据中心/多建筑），对竞赛交付边际收益低 |
| ESPHome + Home Assistant / ThingsBoard / Grafana | 重平台；评审明确说"竞赛项目手搓固件反而是加分项"，只在**能耗可视化交互**上借鉴 |
| GEKKO（MHE/MPC） | 方向完全正确，但前提是**先有可辨识的实测数据**；排在 4.1 之后 |

## 6. 未核实声明

`rc-building`(GitLab)、`Lemings/ESP32EnergyMonitor`、`CityLearn`、GEKKO 本体我**没有下载阅读**，
上面关于它们的判断来自评审原文与它们的公开定位，不构成我自己的核实结论。
