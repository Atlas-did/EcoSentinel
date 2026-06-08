from energy_system.config import settings


def calc_EER(cooling_load_wh, power_wh):
    """
    能耗效率比 (EER)

    说明：要求传入同单位能量（Wh）。当 `power_wh` <= 0 时无法计算返回 None（上层可据此做诊断）。
    返回值为浮点数，可能大于 1。保留负值语义以便上层检测异常情况。
    """
    try:
        p = float(power_wh)
        c = float(cooling_load_wh)
    except Exception:
        return None

    if p <= 0.0:
        return None

    return float(c / p)

def calc_BEC(rated_power_w, run_time_s):
    """
    行为节能贡献 (BEC) 对应的基准能耗累加，纯线性叠加。
    基准耗电量 = 额定功率 * 运行时长秒 / 3600 / 1000 (单位 kWh)
    """
    return (rated_power_w * run_time_s) / 3600000.0

def calc_carbon_reduction(energy_saved_kwh):
    """
    碳减排核算
    """
    carbon_factor = getattr(settings, "CARBON_FACTOR", 0.5708)
    return energy_saved_kwh * carbon_factor

def calculate_savings(baseline_kwh, actual_kwh):
    """
    计算相对基准的节能率和碳减排
    """
    saved_energy = float(baseline_kwh) - float(actual_kwh)
    saving_rate = (saved_energy / baseline_kwh) * 100.0 if baseline_kwh and float(baseline_kwh) > 0 else None
    carbon_reduced = calc_carbon_reduction(saved_energy)
    return {
        "baseline_energy_kwh": baseline_kwh,
        "actual_energy_kwh": actual_kwh,
        "energy_saved_kwh": saved_energy,
        "saving_rate_percent": saving_rate,
        "carbon_reduced_kg": carbon_reduced,
        "is_effective": saved_energy > 0,
    }
