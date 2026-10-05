"""遥测指标的**单一真值**（M1）。

问题：指标名以字符串字面量散落在 Python dict 键、前端 dataKey、固件 JSON 字段里
（实测 `temperature` 出现在 31 个文件、`illuminance` 28 个、`humidity` 25 个…），
于是"加一个指标"要改十几处、改错键名也不报错（静默多出一个字段）。

本模块把指标的**键名、单位、来源、缺失语义**收在一处；其余各层引用它。
跨语言那一侧（前端 TS 接口、固件 JSON 字段、API pydantic schema）由
`tests/contract/test_metrics_registry.py` 断言与注册表一致 —— 不靠人去记。
"""

from __future__ import annotations

from dataclasses import dataclass

#: 缺失值的处理约定（写入前由调用方遵守，注册表负责声明）
MISSING_NAN = "nan"  # 用 NaN 表示"读不到"，绝不伪造一个像样的正常值
MISSING_OMIT = "omit"  # 该指标不适用时直接不写这个键
MISSING_ZERO = "zero"  # 计数/累加类，缺省即 0


@dataclass(frozen=True)
class MetricSpec:
    """一个遥测指标的规格。``key`` 是线上/落盘字段名，也是唯一真值。"""

    key: str
    unit: str
    kind: str  # "sensor" | "derived" | "actuator" | "state"
    missing: str
    description: str


def _spec(key, unit, kind, missing, description):
    return MetricSpec(key, unit, kind, missing, description)


#: 原始传感器读数（由固件/串口给出）
SENSOR_METRICS: tuple[MetricSpec, ...] = (
    _spec("temperature", "degC", "sensor", MISSING_NAN, "空气温度"),
    _spec("humidity", "%RH", "sensor", MISSING_NAN, "相对湿度"),
    _spec("illuminance", "lux", "sensor", MISSING_NAN, "照度"),
    _spec("eco2", "ppm", "sensor", MISSING_NAN, "等效二氧化碳浓度"),
    _spec("tvoc", "ppb", "sensor", MISSING_NAN, "总挥发性有机物"),
    _spec("bus_v", "V", "sensor", MISSING_NAN, "直流母线电压"),
    _spec("current_ma", "mA", "sensor", MISSING_NAN, "负载电流"),
    _spec("power_w", "W", "sensor", MISSING_NAN, "负载功率"),
    _spec("solar_bus_v", "V", "sensor", MISSING_NAN, "太阳能侧母线电压"),
    _spec("solar_current_ma", "mA", "sensor", MISSING_NAN, "太阳能侧电流"),
    _spec("solar_power_w", "W", "sensor", MISSING_NAN, "太阳能侧功率"),
)

#: 由富化层计算出的派生指标
DERIVED_METRICS: tuple[MetricSpec, ...] = (
    _spec("comfort_score", "ratio", "derived", MISSING_NAN, "舒适度评分 0..1"),
    _spec("energy_wh", "Wh", "derived", MISSING_ZERO, "累计用电量"),
    _spec("solar_energy_wh", "Wh", "derived", MISSING_ZERO, "累计太阳能电量"),
    _spec("soc_percent", "%", "derived", MISSING_NAN, "电池荷电状态"),
    _spec("baseline_power", "W", "derived", MISSING_OMIT, "基准功率（后端逐点暂未提供）"),
    _spec("saving_power", "W", "derived", MISSING_OMIT, "节省功率（后端逐点暂未提供）"),
)

#: 状态/执行器类字段（同样属于线上协议，一并登记以便契约测试覆盖）
STATE_METRICS: tuple[MetricSpec, ...] = (
    _spec("schema_version", "n/a", "state", MISSING_OMIT, "线上的 schema 版本"),
    _spec("timestamp", "iso8601", "state", MISSING_OMIT, "采样时间戳"),
    _spec("time", "iso8601", "state", MISSING_OMIT, "图表点时间轴（ChartPoint 用 time）"),
    _spec("relays", "bool[]", "state", MISSING_OMIT, "四路继电器状态"),
    _spec("curtain_steps", "steps", "state", MISSING_OMIT, "窗帘步进位置"),
    _spec("safe_mode", "bool", "state", MISSING_OMIT, "是否处于安全模式"),
    _spec("safe_reason", "str", "state", MISSING_OMIT, "进入安全模式的原因"),
    _spec("errors", "str[]", "state", MISSING_ZERO, "本轮采样错误标记"),
)

#: 别名字典：历史/前端命名 → 注册表规范键。
#: `temp` 是前端 ChartPoint 用的历史名，等价于 `temperature`（同一物理量，只登记一处）。
ALIASES: dict[str, str] = {
    "temp": "temperature",
}

METRICS: dict[str, MetricSpec] = {
    spec.key: spec for spec in (*SENSOR_METRICS, *DERIVED_METRICS, *STATE_METRICS)
}

#: 前端/固件里允许出现、但**不是**遥测指标的字段（ChartPoint 的轴、UI 专用键等）
NON_METRIC_FIELDS: frozenset[str] = frozenset()


def canonical_key(name: str) -> str:
    """别名 → 注册表规范键（未知名字原样返回，便于报错时看清是什么）。"""
    return ALIASES.get(name, name)


def is_known(name: str) -> bool:
    return canonical_key(name) in METRICS


def metric_keys(kind: str | None = None) -> tuple[str, ...]:
    """全部指标键；可按 kind 过滤（"sensor" / "derived" / "state"）。"""
    return tuple(
        spec.key for spec in METRICS.values() if kind is None or spec.kind == kind
    )


def unit_of(name: str) -> str:
    """指标单位；未知指标直接抛错（不要悄悄返回空字符串）。"""
    key = canonical_key(name)
    if key not in METRICS:
        raise KeyError(f"未登记的指标 {name!r}；请在 domain/telemetry.py 注册")
    return METRICS[key].unit


def set_metric(sensor_data: dict, name: str, value: object) -> None:
    """按规范键写入一个指标。

    这是"涟漪"真正的收敛点：键名拼错时**立刻报错**，而不是静默多出一个字段
    （旧代码 `sensor_data["comfort_scope"] = ...` 会一路无声地流到日志与 API）。
    """
    key = canonical_key(name)
    if key not in METRICS:
        raise KeyError(f"未登记的指标 {name!r}；请在 domain/telemetry.py 注册")
    sensor_data[key] = value


def snapshot_subset(data: dict) -> dict:
    """只挑出已登记的指标键（用于跨层传递时显式化接口面）。"""
    return {k: v for k, v in data.items() if k in METRICS}


@dataclass(frozen=True)
class WireField:
    """固件/串口侧的字段名 → 规范指标 + 换算系数。

    过去这套映射**隐式**藏在 ``EnergyAccumulator`` 的关键字默认值里
    （``pwr_mw_key="pwr_mw"`` + 内部 ``/1000.0``）：单位与命名都对，但没人能从一处看清，
    也没人阻止它与固件漂移。这里把它显式登记，并由契约测试锁住实现。
    """

    wire_key: str  # 固件/串口用的名字
    canonical: str  # 注册表规范键
    scale: float  # 规范单位 = 线上值 × scale
    note: str


#: 固件传感器帧里、名字与规范键不同的字段（同名的无需登记）
WIRE_FIELDS: tuple[WireField, ...] = (
    WireField("pwr_mw", "power_w", 0.001, "固件以毫瓦上报负载功率"),
    WireField("solar_pwr_mw", "solar_power_w", 0.001, "固件以毫瓦上报太阳能功率"),
)

#: 固件传感器帧里与规范键**同名**的字段（登记以声明它们是线上契约的一部分）
WIRE_SAME_NAME: tuple[str, ...] = (
    "temperature",
    "humidity",
    "illuminance",
    "eco2",
    "tvoc",
    "bus_v",
    "current_ma",
    "solar_bus_v",
    "solar_current_ma",
    "relays",
    "curtain_steps",
    "errors",
)


def wire_field(name: str) -> WireField | None:
    for field in WIRE_FIELDS:
        if field.wire_key == name:
            return field
    return None


def is_known_wire(name: str) -> bool:
    """线上字段是否已登记（含同名与需换算两类）。"""
    return name in WIRE_SAME_NAME or wire_field(name) is not None


