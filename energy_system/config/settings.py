# ============================================
# 建筑热工参数（基于《公共建筑节能设计标准》GB50189-2015 的简化模型）
# 注意：以下参数为"演示级"简化，用于快速验证控制算法逻辑，
#       非真实建筑实测值。实际部署需根据围护结构热工性能重新标定。
# ============================================

TIME_STEP = 300  # 仿真时步 [s]，对应 5 分钟控制周期

# 舒适区设定（ASHRAE 55-2020 简化）
COMFORT_TEMP_MIN_WINTER = 20.0
COMFORT_TEMP_MAX_WINTER = 26.0
COMFORT_TEMP_MIN_SUMMER = 24.0
COMFORT_TEMP_MAX_SUMMER = 28.0
COMFORT_HUMIDITY_MIN = 40.0
COMFORT_HUMIDITY_MAX = 60.0
COMFORT_ILLUMINANCE_MIN = 300.0   # [lux]，办公区最低照度（GB50034-2013）
COMFORT_ILLUMINANCE_MAX = 750.0   # [lux]，舒适上限

# 碳排放因子（中国区域电网 2022 年平均，来源：生态环境部）
CARBON_FACTOR = 0.5708  # [kgCO2/kWh]
CARBON_FACTOR_SOURCE = "生态环境部 中国区域电网 2022 平均"
CARBON_FACTOR_VERSION = "2022"

# 默认电价（用于看板与日汇总估算），可被运行时配置覆盖
PRICE_CNY_PER_KWH = 0.80  # 元 / kWh
PRICE_SOURCE = "demo_default"

# 电池默认参数（仅作演示用，可通过环境变量或 config 覆盖）
BATTERY_CAPACITY_MAH_DEFAULT = 10000

# 建筑热容与围护结构（演示用简化值）
# C_AIR = **等效**热容（含空气+家具+内墙+地板），不是纯空气热容。
# 纯空气口径：50m²×3m≈150m³ ⇒ ≈1.8e5 J/K；含家具/内墙的等效值通常 1.5e6~3e6 J/K（队友第二轮审计
# 给出该量级，我未实测）。当前 2.5e4 是**演示级**值 ⇒ τ=C_AIR/UA≈14s ≪ 步长 300s
# （exp(-300/14)≈4e-10）⇒ **本模型无热惯性**，分时/预冷策略的时序价值无法体现（见 README）。
# 标定需实机数据：docs/hardware-runbook.md + scripts/identify_rc.py。
C_AIR = 25000.0       # 等效空气热容 [J/K]

#: 建筑面积 [m²] —— **仅用于报告归一化**（对应 BOPTEST 的 area 归一，kpi_calculator.py:356-360），
#: **不进入热模型**。取值来源：本文件**已有**的假设"50m² 办公室"（见上方 C_AIR 注释与下方
#: POWER_LIGHT_MAX 注释"50m² × 24W/m²"）—— 不是新引入的参数。
FLOOR_AREA_M2 = 50.0

# U_WALL 为"综合传热系数"，含墙体传导+通风渗透+窗缝漏风
# 非纯墙体 U 值；老旧建筑实测综合 U 值可达 8~15 W/m²K
U_WALL = 12.0         # 综合等效传热系数 [W/m²K]
A_WALL = 150.0        # 围护结构面积 [m²]

ALPHA_SOLAR = 0.7     # 太阳辐射得热系数（含玻璃透射+内表面吸收）
A_WINDOW = 5.0        # 采光窗面积 [m²]

Q_PEOPLE = 150.0      # 人员散热 [W]，假设 3 人 × 50W/人
Q_EQUIP = 400.0       # 设备散热 [W]，PC+显示器+路由器等

# 空调性能参数（分体式空调典型值）
COP_COOLING = 3.0     # 制冷能效比（EER），国标 3.0 为 1 级能效门槛
COP_HEATING = 2.8     # 制热能效比（COP），热泵典型值
Q_AC_MAX = 3500.0     # 额定制冷量 [W]，对应 1.5 匹家用空调

# 照明功率（LED 办公照明，20~30 W/m²）
POWER_LIGHT_MAX = 1200.0      # 全开功率 [W]，50m² × 24W/m²
POWER_LIGHT_STANDBY = 100.0   # 夜间/节能模式维持功率 [W]
