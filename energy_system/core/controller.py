"""Rule-based controller with hysteresis and anti-short-cycle protection.

Provides the edge-level deterministic control logic that operates independently
of AI. AI outputs are advisory-only by default; this controller makes the final
execution decision (via relay actuation in main.py).

Architecture:
    HysteresisStateMachine — encapsulated on/off state with min run/stop times
    RuleBasedController   — temperature setpoint lookup + lighting policy
"""

from __future__ import annotations

from dataclasses import dataclass

from energy_system.config import settings


# ── Control action result ────────────────────────────────────────────
@dataclass
class ControlAction:
    """Output of one controller evaluation cycle."""
    power_ac: float = 0.0       # AC power in watts (0 = off)
    is_heating: bool = False    # True = heating mode, False = cooling
    power_light: float = 0.0    # Lighting power in watts
    t_set: float = 24.0         # Current temperature setpoint


# ── Hysteresis state machine ─────────────────────────────────────────
class HysteresisStateMachine:
    """Encapsulates anti-short-cycle hysteresis for a binary on/off actuator.

    Prevents "chattering" (rapid on-off cycling) that damages compressors
    and relays by enforcing minimum run time and minimum stop time.
    """

    def __init__(
        self,
        min_run_time_s: float = 900.0,   # 15 minutes
        min_stop_time_s: float = 600.0,  # 10 minutes
    ):
        self.min_run_time_s = float(min_run_time_s)
        self.min_stop_time_s = float(min_stop_time_s)
        self.running = False
        self.last_switch_time = -99999.0
        #: 被防抖（min_run / min_stop）**拦下**的切换请求次数。
        #: 出处：rl-testbed 的 F2 思路（硬约束应可计数，而不是只写在权重里）—— "防抖在 3 天里拦下 N 次
        #: 切换请求"是一个可验证的可靠性论据。
        #: ⚠️ 语义：**每个被拦下的请求计 1**；同一段持续阻塞会逐步累加，因此它同时反映"阻塞了多久"，
        #: 而不是"发生了多少次独立事件"。
        self.blocked_switch_requests = 0

    def sync_from_hardware(self, running: bool, current_time_s: float = 0.0) -> None:
        """Restore state from actual hardware relay status after app restart."""
        self.running = bool(running)
        self.last_switch_time = float(current_time_s)

    def can_start(self, current_time_s: float) -> bool:
        """Check if enough time has elapsed since last stop to allow start."""
        return (current_time_s - self.last_switch_time) >= self.min_stop_time_s

    def can_stop(self, current_time_s: float) -> bool:
        """Check if enough time has elapsed since last start to allow stop."""
        return (current_time_s - self.last_switch_time) >= self.min_run_time_s

    def start(self, current_time_s: float) -> None:
        """Record a start event."""
        self.running = True
        self.last_switch_time = float(current_time_s)

    def stop(self, current_time_s: float) -> None:
        """Record a stop event."""
        self.running = False
        self.last_switch_time = float(current_time_s)


# ── Rule-based controller ────────────────────────────────────────────
class RuleBasedController:
    """Time-of-use temperature control with hysteresis + daylight-responsive lighting.

    Mode 'baseline': constant 24°C setpoint, lights always on during 9-18.
    Mode 'saving':  tiered setpoints (pre-cool 22°C → work 24°C → night 28°C),
                    lights triggered by lux threshold.
    """

    # ── Scheduling constants ─────────────────────────────────────────
    SCHEDULE = {
        "baseline": {  # 24°C all day
            (0, 24): 24.0,
        },
        "saving": {
            (7, 9): 22.0,   # pre-cool during off-peak
            (9, 18): 24.0,  # regular work hours
            (18, 22): 26.0,  # evening
            (22, 24): 28.0,  # night
            (0, 7): 28.0,   # late night
        },
    }

    def __init__(self, mode: str = "baseline", control_law: str = "bangbang",
                 ua_w_per_k: float | None = None, q_ac_max_w: float | None = None):
        """control_law: "bangbang"（默认 = 既有行为）| "feedforward"（《deep-audit》§1.5 的修法）。

        前馈律需要围护结构 UA ⇒ 由 Simulator 传入 `ua_w_per_k`（取自已构造的 ThermalModel），
        这样参数覆盖（realistic）时控制律与模型用同一套参数，而不是 settings 的默认值。
        """
        if control_law not in ("bangbang", "feedforward"):
            raise ValueError(f"未知控制律 {control_law!r}；可选 bangbang | feedforward")
        self.mode = mode
        self.control_law = control_law
        self.ua_w_per_k = (
            float(ua_w_per_k) if ua_w_per_k is not None else float(settings.U_WALL * settings.A_WALL)
        )
        self.q_ac_max_w = float(q_ac_max_w) if q_ac_max_w is not None else float(settings.Q_AC_MAX)
        self.ac_state = HysteresisStateMachine(
            min_run_time_s=15 * 60,
            min_stop_time_s=10 * 60,
        )
        self.ac_heating = False

    def sync_from_hardware(
        self,
        ac_running: bool | None = None,
        ac_heating: bool | None = None,
        current_time_s: float = 0.0,
    ) -> None:
        """Sync internal state with hardware relay state after restart."""
        if ac_running is not None:
            self.ac_state.sync_from_hardware(bool(ac_running), current_time_s)
        if ac_heating is not None:
            self.ac_heating = bool(ac_heating)

    @property
    def ac_running(self) -> bool:
        return self.ac_state.running

    @property
    def short_cycle_blocks(self) -> int:
        """被防抖拦下的切换请求数（见 `HysteresisStateMachine.blocked_switch_requests` 的语义说明）。"""
        return int(self.ac_state.blocked_switch_requests)

    # ── Setpoint lookup ──────────────────────────────────────────────
    def get_temperature_setpoint(self, hour: int) -> float:
        """Return the target temperature for the given hour."""
        schedule = self.SCHEDULE.get(self.mode, self.SCHEDULE["saving"])
        h = int(hour) % 24
        for (start, end), t_set in schedule.items():
            if start <= h < end or (start > end and (h >= start or h < end)):
                return float(t_set)
        return 24.0  # fallback

    # ── Lighting policy ──────────────────────────────────────────────
    def _compute_lighting(self, hour: int, indoor_lux: float | None,
                          I_solar: float = 0.0) -> float:
        """Determine lighting power based on mode, time, and illumination."""
        if self.mode == "baseline":
            return settings.POWER_LIGHT_MAX if 9 <= hour < 18 else settings.POWER_LIGHT_STANDBY

        # Saving mode: daylight-responsive
        lux = (
            float(indoor_lux) if isinstance(indoor_lux, (int, float))
            else self._estimate_indoor_lux_from_solar(I_solar)
        )
        if lux > float(settings.COMFORT_ILLUMINANCE_MIN):
            return settings.POWER_LIGHT_MAX * 0.2  # dim to 20%
        return settings.POWER_LIGHT_MAX if 9 <= hour < 18 else settings.POWER_LIGHT_STANDBY

    @staticmethod
    def _estimate_indoor_lux_from_solar(I_solar: float) -> float:
        """Rough indoor lux estimate from solar irradiance (W/m^2)."""
        return max(0.0, float(I_solar)) * 100.0 * 0.15

    #: 前馈律的比例修正增益 [W/K]（**小**修正；主导项是前馈）
    FEEDFORWARD_KP_W_PER_K = 400.0

    def _feedforward_power(self, T_in: float, T_set: float,
                           T_out: float | None) -> tuple[float, bool]:
        """稳态前馈 + 小比例修正 → (电功率 [W], 是否制热)。

        前馈：维持设定值所需的稳态热流 `Q_ss = UA·(T_out − T_set) + Q_gains`（正 = 需制冷），
        其中 `Q_gains` 取**办公时段满内热**（人员+设备+照明）作为保守上界；电功率 = |Q| / COP。
        修正：`Kp·(T_in − T_set)`。限幅 `[0, q_ac_max_w]`，**无 30% 地板**。
        `T_out is None` 时前馈项置 0（退化为纯比例）——**不假装知道室外温度**。

        ⚠️ 单位命名不一致（我读代码时发现，如实记录）：`settings.Q_AC_MAX` 的注释是
        "额定制冷量 [W]"（热），但旧律与 ThermalModel 都把它当**电功率**用
        （`Q_ac = power_ac × COP`）。这里沿用"电功率上限"的既有语义以保持可比，
        但**注释与命名值得单独修正** —— 这正是让深度核查把 3500×3 算成"10500 W 冷量"的同一个 slip。
        """
        gains = settings.Q_PEOPLE + settings.Q_EQUIP + settings.POWER_LIGHT_MAX
        q_ss = 0.0 if T_out is None else self.ua_w_per_k * (float(T_out) - float(T_set)) + gains
        q_cmd = q_ss + self.FEEDFORWARD_KP_W_PER_K * (T_in - T_set)   # 正 = 需制冷
        is_heating = q_cmd < 0.0
        cop = settings.COP_HEATING if is_heating else settings.COP_COOLING
        return min(self.q_ac_max_w, abs(q_cmd) / cop), is_heating

    # ── Main control evaluation ─────────────────────────────────────
    def compute_action(
        self,
        T_in: float,
        I_solar: float = 0.0,
        hour: int = 12,
        *,
        current_time_s: float = 0.0,
        indoor_lux: float | None = None,
        T_out: float | None = None,
    ) -> ControlAction:
        """Evaluate control action for one cycle.

        Args:
            T_in: Current indoor temperature (°C).
            I_solar: Solar irradiance (W/m^2), used for lux fallback.
            hour: Current hour (0-23).
            current_time_s: Elapsed seconds since controller start (for hysteresis).
            indoor_lux: Measured indoor illuminance (lux), preferred over I_solar.

        Returns:
            ControlAction with AC power, heating flag, light power, and setpoint.
        """
        # ── 对照组："什么也不做" ──────────────────────────────────────────
        # 出处：BOPTEST 的空动作 baseline（`examples/python/controllers/baseline.py:29-31` 返回 `u={}`），
        # 但**语义在本仓不同**：BOPTEST 的模型自带 PI thermostat，空动作 = "把控制权交还建筑本体"；
        # 我们的 1R1C 模型**没有任何自带控制器**，所以"什么也不做"只能是**空调与照明都不动作**，
        # 只保留不可控的内热/设备热（由 simulator 的 power_equip 项体现）。
        # `t_set` 记为当前室温：它表示"没有目标温度"，而不是"目标=室温"。
        if self.mode == "do_nothing":
            return ControlAction(
                power_ac=0.0,
                is_heating=False,
                power_light=0.0,
                t_set=float(T_in),
            )

        T_set = self.get_temperature_setpoint(hour)
        upper_limit = T_set + 0.5
        lower_limit = T_set - 0.5

        # -- AC decision with hysteresis --
        # 语义与原实现逐位等价，只是把"想切换"与"是否被防抖允许"分开，从而能计数被拦下的请求。
        if self.ac_state.running:
            wants_stop = (self.ac_heating and T_in >= T_set) or (
                not self.ac_heating and T_in <= T_set
            )
            if wants_stop:
                if self.ac_state.can_stop(current_time_s):
                    self.ac_state.stop(current_time_s)
                else:
                    self.ac_state.blocked_switch_requests += 1
        else:
            if T_in > upper_limit:
                if self.ac_state.can_start(current_time_s):
                    self.ac_state.start(current_time_s)
                    self.ac_heating = False
                else:
                    self.ac_state.blocked_switch_requests += 1
            elif T_in < lower_limit:
                if self.ac_state.can_start(current_time_s):
                    self.ac_state.start(current_time_s)
                    self.ac_heating = True
                else:
                    self.ac_state.blocked_switch_requests += 1

        # -- AC power computation --
        # 前馈律（可选）：稳态前馈 + 小比例修正，**没有 30% 功率地板**。
        # 出处：《docs/deep-audit-report.md》§1.5 问题①②——30% 地板等价于"一开机就过冲到稳态"，
        # 比例带 3 K 在 θ≈0 的世界里毫无意义；一旦设备够大，旧律立刻变成 ±13 K 无阻尼振荡。
        if self.control_law == "feedforward" and self.ac_state.running:
            power_ac, want_heating = self._feedforward_power(float(T_in), T_set, T_out)
            self.ac_heating = want_heating
        else:
            power_ac = 0.0
            if self.ac_state.running:
                delta = max(0.0, float(T_in) - T_set) if not self.ac_heating \
                        else max(0.0, T_set - float(T_in))
                power_ratio = min(1.0, delta / 3.0)
                power_ac = self.q_ac_max_w * max(0.3, power_ratio)

        # -- Lighting --
        power_light = self._compute_lighting(hour, indoor_lux, I_solar)

        return ControlAction(
            power_ac=power_ac,
            is_heating=self.ac_heating,
            power_light=power_light,
            t_set=T_set,
        )
