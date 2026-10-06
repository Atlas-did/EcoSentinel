from energy_system.config import settings
from energy_system.core.thermal_model import ThermalModel
from energy_system.core.controller import RuleBasedController
from energy_system.simulation.data_generator import EnvironmentGenerator
from energy_system.algorithms.comfort_eval import evaluate_comfort
from typing import Any

class Simulator:
    def __init__(self, mode="baseline", seed: int = 42, mode_schedule=None, params=None):
        """mode_schedule(t_seconds) -> "baseline" | "saving"，用于 ASO 交替实验。

        为 None 时行为与改动前**逐位一致**（单一控制器、固定模式）——由
        tests/contract/test_simulation_baseline.py 的 golden 断言守护。
        ASO（自动系统优化交替）见 energy_system/simulation/aso_experiment.py。

        params：**可选的物理参数覆盖**（传给 ThermalModel，见其 OVERRIDABLE_ATTRS）。
        默认 None ⇒ 完全读 settings，行为不变。用于在不改默认值的前提下跑反事实场景。
        """
        self.mode = mode
        self.dt = settings.TIME_STEP
        self.model = ThermalModel(params=params)
        self.controller = RuleBasedController(mode=mode)
        # 两个控制器都建好，按调度切换（不依赖 RuleBasedController 内部是否缓存 mode）
        self.mode_schedule = mode_schedule
        self._controllers = {"baseline": self.controller, "saving": RuleBasedController(mode="saving")}
        # 每个 Simulator 实例持有独立随机游走状态，避免互相干扰
        self.env_gen = EnvironmentGenerator(seed=seed)
        
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
            "comfort": [],
            "mode": [],
        }
        
        total_energy_j = 0.0
        
        # 强制步进(时距固定为 dt=300)
        for t in range(0, total_time_s, self.dt):
            # 1. 外部虚拟工况捕获
            T_out, I_solar, hour = self.env_gen.generate(t, use_random_walk=True)
            humidity = self.env_gen.generate_humidity(t, use_random_walk=True)
            indoor_lux = max(0.0, float(I_solar)) * 100.0 * 0.15

            # 2. 控制器求取干预项（ASO 模式下按调度逐段切换控制器）
            mode_now = self.mode if self.mode_schedule is None else self.mode_schedule(t)
            controller = self._controllers.get(mode_now, self.controller)
            action = controller.compute_action(
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
            history["mode"].append(mode_now)
            
            # 前推赋值
            T_in_current = T_in_new
            
        history["total_kwh"] = total_energy_j / 3600000.0
        return history
