"""MQTT-based node client for distributed campus deployment.

 Mirrors SerialBridge interface so main.py can switch with minimal changes.

 Install dependency:
   pip install paho-mqtt

 Default free public broker: broker.emqx.io (no auth required for demo)
"""

import json
import logging
import time
from typing import Any

try:
    import paho.mqtt.client as mqtt  # type: ignore
except Exception:  # pragma: no cover
    mqtt = None


class MQTTNodeClient:
    """MQTT node client — push-based sensor reception + command publishing.

    Interface compatibility with SerialBridge:
      - connect() -> bool
      - read_sensors() -> dict | None
      - send_command(cmd: str) -> dict
      - get_health() -> dict
      - close()
    """

    def __init__(
        self,
        node_id: str = "classroom_demo",
        broker: str = "broker.emqx.io",
        port: int = 1883,
        timeout_s: float = 5.0,
    ) -> None:
        self.node_id = node_id
        self.broker = broker
        self.port = port
        self.timeout = timeout_s
        self.logger = logging.getLogger("MQTTNodeClient")

        self._client: Any = None
        self._connected = False
        self._last_sample: dict[str, Any] | None = None
        self._last_sample_ts: float = 0.0

        # Health stats (same keys as SerialBridge for dashboard reuse)
        self.connect_attempts = 0
        self.connect_successes = 0
        self.connect_failures = 0
        self.read_attempts = 0
        self.read_errors = 0
        self.parse_errors = 0
        self.last_error: str | None = None
        self.last_connect_ts: float | None = None
        self.last_valid_sample_ts: float | None = None

        self._topic_sensors = f"{node_id}/sensors"
        self._topic_cmd = f"{node_id}/cmd"

    # ---- MQTT callbacks ----

    def _on_connect(self, client: Any, userdata: Any, flags: Any, rc: int) -> None:
        if rc == 0:
            self._connected = True
            self.connect_successes += 1
            self.logger.info(f"MQTT connected to {self.broker}:{self.port}")
            client.subscribe(self._topic_sensors)
        else:
            self._connected = False
            self.connect_failures += 1
            self.last_error = f"MQTT connect failed, rc={rc}"
            self.logger.error(self.last_error)

    def _on_message(self, client: Any, userdata: Any, msg: Any) -> None:
        try:
            payload = msg.payload.decode("utf-8")
            obj = json.loads(payload)
            if isinstance(obj, dict):
                self._last_sample = obj
                self._last_sample_ts = time.time()
                self.last_valid_sample_ts = time.time()
        except Exception as e:
            self.parse_errors += 1
            self.logger.warning(f"MQTT parse error: {e}")

    def _on_disconnect(self, client: Any, userdata: Any, rc: int) -> None:
        self._connected = False
        if rc != 0:
            self.logger.warning(f"MQTT unexpected disconnect, rc={rc}")

    # ---- Public API (SerialBridge-compatible) ----

    def connect(self) -> bool:
        """Connect to MQTT broker and start network loop."""
        if mqtt is None:
            self.last_error = "paho-mqtt not installed (pip install paho-mqtt)"
            self.logger.error(self.last_error)
            return False

        self.connect_attempts += 1
        try:
            # paho-mqtt v1.x compatibility
            self._client = mqtt.Client()
            self._client.on_connect = self._on_connect
            self._client.on_message = self._on_message
            self._client.on_disconnect = self._on_disconnect

            self._client.connect(self.broker, self.port, keepalive=60)
            self._client.loop_start()
            self.last_connect_ts = time.time()

            # Briefly wait for handshake
            deadline = time.monotonic() + 2.0
            while time.monotonic() < deadline and not self._connected:
                time.sleep(0.05)
            return self._connected
        except Exception as e:
            self.connect_failures += 1
            self.last_error = str(e)
            self.logger.error(f"MQTT connection error: {e}")
            return False

    def read_sensors(self) -> dict[str, Any] | None:
        """Return the latest sensor sample received via MQTT.

        MQTT is push-based: the firmware publishes every ~5 s.
        This method consumes the cached sample (one-shot).
        """
        self.read_attempts += 1
        if not self._connected or self._client is None:
            self.read_errors += 1
            return None
        sample = self._last_sample
        self._last_sample = None
        return sample

    def send_command(self, cmd: str) -> dict[str, Any]:
        """Publish a raw command string to the node's cmd topic."""
        if not self._connected or self._client is None:
            return {"ok": False, "error": "not_connected"}
        try:
            self._client.publish(self._topic_cmd, cmd)
            self.logger.info(f"MQTT TX: {cmd}")
            return {"ok": True, "msg": "published"}
        except Exception as e:
            self.last_error = str(e)
            return {"ok": False, "error": str(e)}

    def get_health(self) -> dict[str, Any]:
        return {
            "broker": self.broker,
            "port": self.port,
            "node_id": self.node_id,
            "connected": self._connected,
            "topic_sensors": self._topic_sensors,
            "topic_cmd": self._topic_cmd,
            "connect_attempts": self.connect_attempts,
            "connect_successes": self.connect_successes,
            "connect_failures": self.connect_failures,
            "read_attempts": self.read_attempts,
            "read_errors": self.read_errors,
            "parse_errors": self.parse_errors,
            "last_connect_ts": self.last_connect_ts,
            "last_valid_sample_ts": self.last_valid_sample_ts,
            "last_error": self.last_error,
            "mode": "mqtt",
        }

    def close(self) -> None:
        if self._client:
            try:
                self._client.loop_stop()
                self._client.disconnect()
            except Exception:
                pass
        self._connected = False
