import math

from energy_system.config import settings

class ThermalModel:
    """一阶 RC 模型。支持**可选参数覆盖**，用于在不改默认值的前提下跑反事实场景。

    出处：《docs/deep-audit-report.md》第 5 章要求先在"真实量级"参数下验证控制律，
    而用户批准的边界是**绝不改默认值** ⇒ 故走 `params=` 覆盖，默认 `None` ⇒ 行为逐位不变
    （由 tests/contract/test_simulation_baseline.py 的 golden 持续守护）。
    """

    #: 允许覆盖的参数键 → 实例属性名（其余仍读 settings）
    OVERRIDABLE_ATTRS = {
        "C_AIR": "C_air",
        "U_WALL": "U_wall",
        "A_WALL": "A_wall",
        "ALPHA_SOLAR": "alpha_solar",
        "A_WINDOW": "A_window",
        "Q_PEOPLE": "Q_people",
        "Q_EQUIP": "Q_equip",
        "TIME_STEP": "dt",
    }

    def __init__(self, params: dict | None = None):
        self.dt = settings.TIME_STEP
        # 内部发热参数
        self.Q_people = settings.Q_PEOPLE
        self.Q_equip = settings.Q_EQUIP
        self.C_air = settings.C_AIR
        self.U_wall = settings.U_WALL
        self.A_wall = settings.A_WALL
        self.alpha_solar = settings.ALPHA_SOLAR
        self.A_window = settings.A_WINDOW

        if params:
            unknown = set(params) - set(self.OVERRIDABLE_ATTRS)
            if unknown:
                raise KeyError(
                    f"不支持的参数覆盖：{sorted(unknown)}；可选 {sorted(self.OVERRIDABLE_ATTRS)}"
                )
            for key, value in params.items():
                if not isinstance(value, (int, float)) or float(value) <= 0.0:
                    raise ValueError(f"{key} 必须为正数，实得 {value!r}")
                setattr(self, self.OVERRIDABLE_ATTRS[key], float(value))

    def step(self, T_in_old, T_out, I_solar, hour, power_ac_w, is_heating):
        """
        核心物理约束：采用线性一阶差分格式，基于固定 dt=300 推进状态
        """
        # 1. 围护结构传热 (负值代表向外流失)
        Q_envelope = self.U_wall * self.A_wall * (T_out - T_in_old)
        
        # 2. 太阳短波辐射得热
        Q_solar = self.alpha_solar * I_solar * self.A_window
        
        # 3. 内部发热
        if 9 <= hour < 18:
            Q_internal = self.Q_people + self.Q_equip
        else:
            Q_internal = 50.0  # 夜间待机极低废热
            
        # 4. 空调换热贡献
        Q_ac = 0.0
        if power_ac_w > 0:
            if is_heating:
                Q_ac = power_ac_w * settings.COP_HEATING
            else:
                Q_ac = -power_ac_w * settings.COP_COOLING

        # 热平衡一阶线性 ODE 的**精确解**（解析积分）：
        #     C·dT/dt = UA·(T_out − T) + Q_const,   Q_const = Q_solar + Q_internal + Q_ac
        #     稳态 T_inf = (UA·T_out + Q_const) / UA
        #     解   T(t+dt) = T_inf + (T − T_inf)·exp(−UA·dt/C)
        # 旧实现是显式欧拉 dT = (ΣQ/C)·dt：当 dt > 2C/UA 时**必然发散**。
        # 本仓当前参数 C_AIR=25000 J/K、UA=U_WALL·A_WALL=1800 W/K ⇒ 2τ≈27.8s ≪ dt=300s，
        # 旧实现实测一步就把 24°C 推到 249°C（连制冷/制热的符号都翻了）。
        # 数学性质断言见 tests/unit/test_thermal_model.py（先红后绿）。
        Total_Q = Q_envelope + Q_solar + Q_internal + Q_ac

        UA = self.U_wall * self.A_wall
        Q_const = Q_solar + Q_internal + Q_ac
        if UA > 0.0:
            T_inf = (UA * T_out + Q_const) / UA
            T_in_new = T_inf + (T_in_old - T_inf) * math.exp(-UA * self.dt / self.C_air)
        else:
            # 无围护结构传热时退化为纯热容加热（不再有稳定性问题）
            T_in_new = T_in_old + (Q_const / self.C_air) * self.dt
        
        return T_in_new, {
            "Q_total": Total_Q,
            "Q_env": Q_envelope,
            "Q_solar": Q_solar,
            "Q_internal": Q_internal,
            "Q_ac": Q_ac
        }
