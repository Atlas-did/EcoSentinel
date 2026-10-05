"""Data acquisition coordinator for EnergySystemApp.

Handles reading sensor data from hardware (SerialBridge), or from a **mock
generator injected by the composition root** when hardware is unavailable.

Note: this module deliberately does **not** import the simulation layer. It used to
lazily import ``simulation.data_generator`` inside a method, which created a package
cycle (core -> simulation -> core). The generator is now passed in — see
``application/runtime.py`` (the composition root) and ``tests/contract/test_layering.py``.
"""

import logging
import time
from datetime import datetime
from typing import Any

logger = logging.getLogger("DataAcquisition")


class DataAcquisition:
    """Coordinates sensor data reading from hardware or simulation."""

    def __init__(
        self,
        use_hardware: bool = False,
        serial_bridge: Any = None,
        mock_generator: Any = None,
    ) -> None:
        self.use_hardware = use_hardware
        self.serial_bridge = serial_bridge
        self._mock_generator = mock_generator
        self._env_gen = None  # lazy init for mock mode

    def _get_mock_generator(self) -> Any:
        """Return the injected mock generator (None when none was provided)."""
        if self._env_gen is None:
            self._env_gen = self._mock_generator
        return self._env_gen

    def read(self) -> dict | None:
        """Fetch one sensor sample.

        Returns:
            A dict of sensor data, or None if no data is available.
        """
        if self.use_hardware:
            return self._read_hardware()
        else:
            return self._read_mock()

    def _read_hardware(self) -> dict | None:
        bridge = self.serial_bridge
        if not bridge:
            return None
        try:
            return bridge.read_sensors()
        except Exception as e:
            logger.warning(f"Sensor read failed: {e}")
            return None

    def _read_mock(self) -> dict | None:
        """Generate mock data from the injected generator.

        The generator produces time-correlated random-walk values instead of
        hardcoded constants, which makes the dashboard realistic when no hardware
        is attached. When nothing was injected we return None (= "no sample"), so
        the caller's no-data path runs instead of fabricating readings.
        """
        gen = self._get_mock_generator()
        if gen is None:
            logger.warning(
                "No mock generator injected; returning no sample. "
                "Inject simulation.data_generator.EnvironmentGenerator at the composition root."
            )
            return None
        # mock 的昼夜/在室率必须按**本地**小时：EnvironmentGenerator 内部按 (t/3600)%24 取小时，
        # 直接传 time.time()（UTC epoch）会把上海的白天算成凌晨（相差 8 小时，昼夜策略全反）。
        local_offset = time.altzone if time.localtime().tm_isdst else time.timezone
        now_ts = time.time() - local_offset
        T_out, I_solar, hour = gen.generate(now_ts, use_random_walk=True)
        humidity = gen.generate_humidity(now_ts, use_random_walk=True)

        # 室内温度 = 室外 + 内热造成的稳态温差，温差用**本仓已有参数**推导（不臆造）：
        #   ΔT = Q_internal / (U_WALL·A_WALL)  ⇒ 白天 550/1800 ≈ 0.31 K、夜间 50/1800 ≈ 0.03 K
        # 这是稳态近似；需要动态过程请走 ThermalModel（已改为解析指数积分）。
        from energy_system.config import settings as _settings

        ua = _settings.U_WALL * _settings.A_WALL
        q_internal = (_settings.Q_PEOPLE + _settings.Q_EQUIP) if 9 <= hour < 18 else 50.0
        t_indoor = T_out + (q_internal / ua if ua > 0 else 0.0)

        # 电参量（**仅 mock**，合成演示值而非实测）：接硬件时由 INA219 提供，
        # 没有它们 EnergyAccumulator 无法累积 energy_wh（评审 P1 第 3 条）。
        illuminance = max(0.0, float(I_solar) * 100.0 * 0.15)
        bus_v = 12.0
        load_w = 40.0 + illuminance / 100.0
        current_ma = round(load_w / bus_v * 1000.0, 1)
        pwr_mw = round(load_w * 1000.0, 1)

        return {
            "temperature": round(float(t_indoor), 1),
            "humidity": round(float(humidity), 1),
            "illuminance": round(illuminance, 1),
            "eco2": 450,
            "tvoc": 12,
            "bus_v": bus_v,
            "current_ma": current_ma,
            "pwr_mw": pwr_mw,
            "timestamp": datetime.now().isoformat(),
        }


def no_data_heartbeat_fields(
    safe_reason: str | None,
    resilience: Any,
    bridge_health: dict | None = None,
) -> dict:
    """Build a compact heartbeat row for logging when no sensor data is available."""
    return {
        "timestamp": datetime.now().isoformat(),
        "safe_mode": True,
        "safe_reason": safe_reason or "no_sample_yet",
        "bridge_health": bridge_health,
        "resilience": {
            "state": getattr(resilience, "breaker_state", None),
            "incident_id": getattr(resilience, "last_incident_id", None),
            "last_action": getattr(resilience, "last_action", None),
            "last_action_reason": getattr(resilience, "last_action_reason", None),
        },
    }
