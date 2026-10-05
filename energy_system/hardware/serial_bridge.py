import json
import time
import logging
from typing import Any

try:
    from serial.tools import list_ports  # type: ignore
except Exception:  # pragma: no cover
    list_ports = None

try:
    import serial  # type: ignore
except Exception:  # pragma: no cover
    serial = None

from energy_system.hardware.protocol_contract import max_frame_bytes

#: 单帧上限由协议清单(protocol/eco_protocol.yaml)驱动 —— 见 tests/contract/test_serial_protocol.py
MAX_FRAME_BYTES = max_frame_bytes()


def parse_sensor_line(line: str) -> dict[str, Any] | None:
    line = (line or "").strip()
    if not line:
        return None
    # 超长帧直接丢弃：固件异常刷屏时保护解析器（此前主机侧没有任何上限）
    if len(line) > MAX_FRAME_BYTES:
        return None
    # 固件可能回传错误标记（例如 DHT 读数 NaN）
    if line.startswith("DHT_"):
        return None
    if not (line.startswith("{") and line.endswith("}")):
        return None
    try:
        obj = json.loads(line)
        return obj if isinstance(obj, dict) else None
    except Exception:
        return None


def _classify_message(obj: dict[str, Any]) -> str:
    """Classify parsed JSON dict into 'sensor' | 'ack' | 'unknown'.

    Firmware may proactively push sensor JSON while we are waiting for command ACK.
    This classifier helps route messages to the right caller.
    """
    # ACK / status-like payloads
    if any(k in obj for k in ("status", "ok", "type", "error", "message")):
        return "ack"

    # Sensor payloads (most common keys)
    if any(k in obj for k in ("temperature", "humidity", "illuminance", "relays", "curtain_steps")):
        return "sensor"
    if any(k in obj for k in ("bus_v", "current_ma", "pwr_mw", "solar_bus_v", "solar_current_ma", "solar_pwr_mw")):
        return "sensor"

    return "unknown"

class SerialBridge:
    def __init__(self, port: str = 'COM3', baudrate: int = 115200, timeout: float = 2.0):
        self.port = port
        self.baudrate = baudrate
        self.timeout = timeout
        self.connection = None
        self.logger = logging.getLogger("SerialBridge")
        self._last_connect_err: str | None = None

        # Remember hardware identity so we can recover from USB re-enumeration
        # (COM port temporarily disappears or changes after resets on Windows).
        self._target_vidpid: str | None = None  # e.g. "303A:1001"
        self._target_ser: str | None = None     # e.g. "94:A9:..." (may be None)

        # Windows + ESP32-S3 native USB CDC can throw ClearCommError (ERROR_BAD_COMMAND).
        # Empirically, frequent open/close can also trigger USB re-enumeration (COM port
        # disappears briefly -> FileNotFoundError). So we prefer a persistent connection
        # with: (1) read-only behavior, (2) DTR/RTS disabled, (3) auto-reconnect on error.
        self._reconnect_backoff_s = 1.0
        self._next_reconnect_ts = 0.0

        # Health stats
        self.connect_attempts = 0
        self.connect_successes = 0
        self.connect_failures = 0
        self.read_attempts = 0
        self.read_errors = 0
        self.parse_errors = 0
        self.last_error: str | None = None
        self.last_connect_ts: float | None = None
        self.last_valid_sample_ts: float | None = None

    def _list_ports(self) -> list[Any]:
        if list_ports is None:
            return []
        try:
            return list(list_ports.comports())
        except Exception:
            return []

    def _extract_ids(self, hwid: str) -> tuple[str | None, str | None]:
        """Return (vidpid, ser) parsed from pyserial hwid string."""
        hwid = str(hwid or "")
        vidpid = None
        ser = None
        # Example: "USB VID:PID=303A:1001 SER=... LOCATION=..."
        up = hwid.upper()
        if "VID:PID=" in up:
            try:
                vidpid = up.split("VID:PID=", 1)[1].split()[0]
            except Exception:
                vidpid = None
        if "SER=" in up:
            try:
                ser = hwid.split("SER=", 1)[1].split()[0]
            except Exception:
                ser = None
        return vidpid, ser

    def _resolve_port(self) -> str | None:
        """Resolve an available COM port.

        Priority:
        1) Current `self.port` if present.
        2) Match remembered VID:PID (+SER if known).
        3) Heuristic: first port with Espressif VID:PID=303A:1001.
        4) If only one port exists, use it.
        """
        ports = self._list_ports()
        if not ports:
            return None

        devices = {getattr(p, "device", None) for p in ports}
        if self.port in devices:
            return self.port

        # Match remembered ids
        if self._target_vidpid:
            for p in ports:
                hwid = getattr(p, "hwid", "")
                vidpid, ser = self._extract_ids(hwid)
                if vidpid and vidpid.upper() == self._target_vidpid.upper():
                    if self._target_ser and ser and ser == self._target_ser:
                        return getattr(p, "device", None)
                    if not self._target_ser:
                        return getattr(p, "device", None)

        # Heuristic for ESP32-S3 native USB CDC
        for p in ports:
            hwid = getattr(p, "hwid", "")
            vidpid, _ser = self._extract_ids(hwid)
            if vidpid and vidpid.upper() == "303A:1001":
                return getattr(p, "device", None)

        if len(ports) == 1:
            return getattr(ports[0], "device", None)
        return None

    def connect(self):
        self.connect_attempts += 1
        if serial is None:
            self._last_connect_err = "pyserial not installed"
            self.last_error = self._last_connect_err
            self.logger.error("SerialBridge disabled: pyserial not installed")
            return False

        # Respect backoff to avoid hammering usbser.sys when it is in a bad state
        now = time.time()
        if now < self._next_reconnect_ts:
            return False

        last_err: Exception | None = None
        for attempt in range(3):
            try:
                resolved = self._resolve_port()
                if resolved and resolved != self.port:
                    self.logger.warning(f"Serial port changed: {self.port} -> {resolved}")
                    self.port = resolved

                # Keep connect behavior close to scripts/sniff_serial.py (works best on Win+CDC)
                self.connection = serial.Serial(self.port, self.baudrate, timeout=1)

                # Learn VID/PID + SER for future re-enumeration recovery
                for p in self._list_ports():
                    if getattr(p, "device", None) == self.port:
                        vidpid, ser = self._extract_ids(getattr(p, "hwid", ""))
                        if vidpid:
                            self._target_vidpid = vidpid
                        if ser:
                            self._target_ser = ser
                        break

                # Clear any partial line from boot/reset
                try:
                    self.connection.reset_input_buffer()
                except Exception:
                    pass

                time.sleep(0.2)
                self._last_connect_err = None
                self.last_error = None
                self.last_connect_ts = time.time()
                self.connect_successes += 1
                self._reconnect_backoff_s = 1.0
                self._next_reconnect_ts = 0.0
                self.logger.info(f"Connected to ESP32 on {self.port}")
                return True
            except Exception as e:
                last_err = e
                self._last_connect_err = str(e)
                self.last_error = str(e)
                self.logger.error(f"Failed to connect (attempt {attempt + 1}/3): {e}")
                # If port disappeared, give Windows time to re-enumerate before retry
                time.sleep(1.0 * (attempt + 1))

        self.connect_failures += 1
        self._next_reconnect_ts = time.time() + self._reconnect_backoff_s
        self._reconnect_backoff_s = min(10.0, self._reconnect_backoff_s * 2)
        return False

    def _parse_sensor_line(self, line: str) -> dict[str, Any] | None:
        return parse_sensor_line(line)

    def read_sensors(self):
        if serial is None:
            self.last_error = "pyserial not installed"
            return None

        if getattr(self, "_reconnecting", False):
            return None

        if not self.connection or not self.connection.is_open:
            self.logger.info("Connection lost. Attempting auto-reconnect...")
            self._reconnecting = True
            time.sleep(1.0)
            self.connect()
            self._reconnecting = False
            if not self.connection or not self.connection.is_open:
                return None

        self.read_attempts += 1
        
        try:
            # Firmware emits about one JSON frame every ~6s; wait a bit for it.
            deadline = time.monotonic() + 8.0

            # 允许读多行：过滤掉非 JSON，直到拿到一条可用 payload。
            # 注意：固件可能回传 {"ok": false, "error": "DHT_NAN"} 之类的错误帧。
            # 这类帧对“系统在线监测/落盘”很关键，因此在此作为样本返回，让上层记录。
            while time.monotonic() < deadline:
                # Avoid extra driver calls (e.g. in_waiting). Keep it simple.
                raw = self.connection.readline()  # may throw ClearCommError
                line = raw.decode('utf-8', errors='ignore').strip()
                obj = self._parse_sensor_line(line)
                if obj is not None:
                    msg_type = _classify_message(obj)
                    if msg_type == "sensor":
                        self.last_valid_sample_ts = time.time()
                        return obj
                    if msg_type == "ack":
                        # Treat explicit error frames as samples so the app can log incidents
                        ok = obj.get("ok")
                        if ok is False or ("error" in obj and obj.get("error")):
                            self.last_valid_sample_ts = time.time()
                            obj.setdefault("sample_type", "error")
                            return obj
                        # Otherwise ignore benign ACK/status during sensor read
                        continue

                    # ignore unknown payloads during sensor read
                    continue

                if line:
                    # 有内容但解析不到 JSON，计为解析失败
                    self.parse_errors += 1
        except Exception as e:
            self.read_errors += 1
            self.last_error = str(e)
            self.logger.error(f"Error reading sensors: {e}. Forcing reset of serial handle...")
            try:
                self.connection.close()
            except Exception:
                pass
            self.connection = None  # Force reconnect on next cycle
            # Give Windows time to re-enumerate the CDC device.
            self._next_reconnect_ts = time.time() + max(2.0, self._reconnect_backoff_s)
            self._reconnect_backoff_s = min(10.0, self._reconnect_backoff_s * 2)
        return None

    def get_health(self) -> dict[str, Any]:
        return {
            "port": self.port,
            "baudrate": self.baudrate,
            "connected": bool(self.connection) and bool(getattr(self.connection, "is_open", False)),
            "connect_attempts": self.connect_attempts,
            "connect_successes": self.connect_successes,
            "connect_failures": self.connect_failures,
            "read_attempts": self.read_attempts,
            "read_errors": self.read_errors,
            "parse_errors": self.parse_errors,
            "last_connect_ts": self.last_connect_ts,
            "last_valid_sample_ts": self.last_valid_sample_ts,
            "last_error": self.last_error,
            "mode": "persistent",
        }

    def send_command(self, cmd):
        """Send a raw command string like 'RELAY 1 1' or 'CURTAIN OPEN'."""
        if serial is None:
            return {"ok": False, "error": "pyserial_not_installed"}
        if getattr(self, "_reconnecting", False) or not self.connection or not self.connection.is_open:
            return {"ok": False, "error": "not_connected"}

        try:
            # Flush stale pushed frames so command/ACK pairing is cleaner.
            try:
                self.connection.reset_input_buffer()
            except Exception:
                pass

            self.connection.write((str(cmd).strip() + "\n").encode("utf-8"))
            deadline = time.monotonic() + max(1.0, float(self.timeout))
            last_text = None

            while time.monotonic() < deadline:
                raw = self.connection.readline()
                if not raw:
                    continue
                text = raw.decode("utf-8", errors="ignore").strip()
                if not text:
                    continue
                last_text = text
                obj = parse_sensor_line(text)
                if obj is None:
                    continue

                msg_type = _classify_message(obj)
                if msg_type == "sensor":
                    # Ignore passive sensor pushes while waiting for command ACK.
                    continue

                if obj.get("ok") is True:
                    return {"ok": True, "response": obj}
                if obj.get("ok") is False or obj.get("error"):
                    return {"ok": False, "response": obj, "error": obj.get("error") or obj.get("msg")}

            return {"ok": False, "error": "timeout_waiting_for_ack", "last_text": last_text}
        except Exception as e:
            self.last_error = str(e)
            self.read_errors += 1
            self.logger.error(f"Error sending command {cmd!r}: {e}")
            try:
                self.connection.close()
            except Exception:
                pass
            self.connection = None
            # Trigger reconnect backoff so we don't hammer the driver immediately
            self._next_reconnect_ts = time.time() + max(2.0, self._reconnect_backoff_s)
            self._reconnect_backoff_s = min(10.0, self._reconnect_backoff_s * 2)
            return {"ok": False, "error": str(e)}

    def close(self):
        if self.connection:
            self.connection.close()
        self.connection = None
