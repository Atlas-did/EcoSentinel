from energy_system.config import settings
from energy_system.core.thermal_model import ThermalModel
from energy_system.core.controller import RuleBasedController
from energy_system.simulation.data_generator import EnvironmentGenerator
from energy_system.algorithms.comfort_eval import evaluate_comfort
from typing import Any

class Simulator:
    def __init__(self, mode="baseline"):
        self.mode = mode
        self.dt = settings.TIME_STEP
        self.model = ThermalModel()
        self.controller = RuleBasedController(mode=mode)
        # 每个 Simulator 实例持有独立随机游走状态，避免互相干扰
        self.env_gen = EnvironmentGenerator(seed=42)
        
    def run_simulation(self, days=3):
        total_time_s = days * 24 * 3600
        
        # 初始截面
        T_in_current = 20.0
        
        history: dict[str, Any] = {
            "time_h": [],
            "T_out": [],
            "I_solar": [],
            "humidity": [],
            "T_in": [],
            "T_set": [],
            "power_total": [],
            "comfort": []
        }
        
        total_energy_j = 0.0
        
        # 强制步进(时距固定为 dt=300)
        for t in range(0, total_time_s, self.dt):
            # 1. 外部虚拟工况捕获
            T_out, I_solar, hour = self.env_gen.generate(t, use_random_walk=True)
            humidity = self.env_gen.generate_humidity(t, use_random_walk=True)
            indoor_lux = max(0.0, float(I_solar)) * 100.0 * 0.15

            # 2. 控制器求取干预项
            action = self.controller.compute_action(
                T_in_current,
                I_solar,
                hour,
                current_time_s=t,
                indoor_lux=indoor_lux,
            )
            T_in_new, _ = self.model.step(
                T_in_current, T_out, I_solar, hour, action.power_ac, action.is_heating
            )
            
            # 4. 指标统计聚合
            # 当前周期内耗电积累 = 电功率 * dt
            power_equip = settings.Q_EQUIP if 9 <= hour < 18 else 50.0
            power_total = action.power_ac + action.power_light + power_equip
            total_energy_j += power_total * self.dt

            comfort = evaluate_comfort(T_in_new, humidity)

            # 5. 落盘切片
            history["time_h"].append(t / 3600.0)
            history["T_out"].append(T_out)
            history["I_solar"].append(I_solar)
            history["humidity"].append(humidity)
            history["T_in"].append(T_in_new)
            history["T_set"].append(action.t_set)
            history["power_total"].append(power_total)
            history["comfort"].append(comfort)
            
            # 前推赋值
            T_in_current = T_in_new
            
        history["total_kwh"] = total_energy_j / 3600000.0
        return history
