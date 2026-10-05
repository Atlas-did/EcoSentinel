import math

from energy_system.config import settings

class ThermalModel:
    def __init__(self):
        self.dt = settings.TIME_STEP
        # 内部发热参数
        self.Q_people = settings.Q_PEOPLE
        self.Q_equip = settings.Q_EQUIP
        self.C_air = settings.C_AIR
        self.U_wall = settings.U_WALL
        self.A_wall = settings.A_WALL
        self.alpha_solar = settings.ALPHA_SOLAR
        self.A_window = settings.A_WINDOW

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
