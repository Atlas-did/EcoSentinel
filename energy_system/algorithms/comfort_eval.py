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
