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

        # 热平衡微分一阶近似： dT = (Sum(Q) / C) * dt
        Total_Q = Q_envelope + Q_solar + Q_internal + Q_ac
        dT = (Total_Q / self.C_air) * self.dt
        
        T_in_new = T_in_old + dT
        
        return T_in_new, {
            "Q_total": Total_Q,
            "Q_env": Q_envelope,
            "Q_solar": Q_solar,
            "Q_internal": Q_internal,
            "Q_ac": Q_ac
        }
