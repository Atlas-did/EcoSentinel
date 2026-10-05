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
        now_ts = time.time()
        T_out, I_solar, hour = gen.generate(now_ts, use_random_walk=True)
        humidity = gen.generate_humidity(now_ts, use_random_walk=True)

        return {
            "temperature": round(float(T_out), 1),
            "humidity": round(float(humidity), 1),
            "illuminance": round(max(0.0, float(I_solar) * 100.0 * 0.15), 1),
            "eco2": 450,
            "tvoc": 12,
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
