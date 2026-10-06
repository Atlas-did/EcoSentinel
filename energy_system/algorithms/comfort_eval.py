def calc_TCI(temp, humidity=None, season="summer"):
    """简化版温度舒适度指数 (TCI)。

    公式：TCI = 1 - |实际温度 - 最佳温度| / 允许波动范围
    输出范围：0.0 ~ 1.0

    湿度耦合修正：湿度 > 70% 时，有效体感温度 +1°C
    （高湿环境下人体散热受阻，体感更热）
    """
    if season == "summer":
        opt_temp = 26.0
        delta_allow = 2.0
    else:
        opt_temp = 23.0
        delta_allow = 3.0

    # 湿度耦合：当湿度较高时，会增加体感温度，采用平滑比例而非硬阈值 +1°C
    effective_temp = float(temp)
    if humidity is not None and humidity > 70.0:
        # 每超过 70% 增加体感温度，比例缩放以避免过大修正
        extra = min(2.0, (float(humidity) - 70.0) / 20.0)
        effective_temp += extra

    tci = 1.0 - abs(effective_temp - opt_temp) / delta_allow
    return max(0.0, min(1.0, tci))


def calc_humidity_score(humidity):
    """湿度舒适度评分（40%~60% 最舒适）。

    输出范围：0.0 ~ 1.0

    采用非线性（幂次）衰减：偏离舒适区越远，惩罚越重，
    避免线性模型在极端湿度下掩盖严重性。
    """
    if humidity is None:
        # 缺失湿度时返回中性评分（避免把未知视为极差）
        return 0.6
    if 40.0 <= humidity <= 60.0:
        return 1.0
    if humidity < 40.0:
        deviation = (40.0 - humidity) / 40.0  # 归一化到 [0, 1]
        return max(0.0, 1.0 - deviation ** 1.5)
    # humidity > 60.0
    deviation = (humidity - 60.0) / 40.0
    return max(0.0, 1.0 - deviation ** 1.5)


def calc_LUR(illuminance, target=300.0):
    """
    光照利用率 (LUR)
    公式：LUR = min(1.0, 实际自然光照 / 目标所需光照)
    """
    return min(1.0, illuminance / target)


def evaluate_comfort(temp, humidity, illuminance=None, season="summer", temp_weight: float = 0.6, hum_weight: float = 0.4):
    """综合舒适度计算。

    - `temp_weight` 与 `hum_weight` 可用于快速调参（保持向后兼容，默认 0.6 / 0.4）。
    - 当 `humidity` 缺失时使用中性湿度评分以避免误判。
    - 可选光照眩光惩罚：照度 > 800 lux 时舒适度 × 0.9
    """
    # 保持权重和为 1 的推荐用法
    tw = float(temp_weight)
    hw = float(hum_weight)
    if tw + hw <= 0:
        tw, hw = 0.6, 0.4

    tci = calc_TCI(temp, humidity, season)
    h_score = calc_humidity_score(humidity)

    comfort = (tw * tci + hw * h_score) / (tw + hw)

    # 光照眩光惩罚
    if illuminance is not None and illuminance > 800.0:
        comfort *= 0.9

    return float(max(0.0, min(1.0, comfort)))


# ── IPMVP 原生舒适度口径：舒适带内时间占比 ──────────────────────────────────
#
# 依据（**队友审计补充，已逐行核实**）：
#   * IPMVP Core Concepts 对 comfort 的原生定义就是 "percentage of time in comfort band"；
#   * Sinergym 的"舒适度"不是 0–1 打分，而是**带外惩罚**：
#       sinergym/utils/rewards.py:163
#       return [max(temp_range[0] - T, 0, T - temp_range[1]) for T in temp_values]
#     带内恒为 0、出带才增长 ⇒ 在它那里舒适是**约束**，不是目标
#     （rewards.py:85 self.W_energy = energy_weight）。
#
# 而本仓库的 `calc_TCI` 是 `1 - |T - 26| / 2` —— 它是"打分"，与上面两者**都不同类**：
# 24 °C 落在 26±2 的带外 ⇒ 得 0 分。因此 `evaluate_comfort` 的均值（如 49.3%）
# **不该叫"舒适度 %"**，也不能与文献同表比较。对外报告应给本函数的取值。
COMFORT_BAND_LOW_C = 23.0   # 两个独立来源一致：ISO 7730 数值解(PMV∈±0.5)≈23–26.5 ℃；
COMFORT_BAND_HIGH_C = 26.0  # Sinergym range_comfort_summer=(23.0,26.0) 与 setpoints_summer 同值。


def time_in_band_share(temps, low: float = COMFORT_BAND_LOW_C, high: float = COMFORT_BAND_HIGH_C) -> float:
    """落在舒适带 `[low, high]` 内的时间占比（IPMVP 原生 comfort 口径）。

    约定：① 边界**包含**（`T == low` 或 `T == high` 计入带内）；
    ② `low > high` 视为调用错误（抛 `ValueError`），避免"带写反了还静默给 0"；
    ③ `None` / `NaN` **不计入分母**；一个有效样本都没有时返回 `0.0`（不产生 NaN）。
    """
    if low > high:
        raise ValueError(f"舒适带上下界反了：low={low} > high={high}")
    valid = [float(t) for t in temps if t is not None and float(t) == float(t)]
    if not valid:
        return 0.0
    inside = sum(1 for t in valid if low <= t <= high)
    return inside / len(valid)
