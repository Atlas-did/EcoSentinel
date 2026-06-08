"""
Smart Hardware Monitoring Dashboard - Streamlit Entry Point.

Architecture:
    dashboard.py (this file)          - layout orchestration + sidebar
    dashboard/data_loader.py          - log reading, power estimation
    dashboard/hardware_status.py      - sensor presence inference + display
    dashboard/realtime_view.py        - real-time sensor/metric display
    dashboard/energy_view.py          - energy, solar, SOC, comparison
    dashboard/ai_pool.py              - AI candidate pool + resilience status
    dashboard/simulation_view.py      - digital twin simulation page

Usage:
    streamlit run dashboard.py
"""

import json
import time
from pathlib import Path

import streamlit as st

from energy_system.config.config_loader import load_app_config
from energy_system.power.energy_accounting import BatterySOC

from dashboard.data_loader import (
    estimate_channel_power_w,
    read_last_jsonl,
    read_tail_jsonl,
)
from dashboard.energy_view import (
    render_energy_comparison,
    render_energy_module,
    render_soc_module,
)
from dashboard.hardware_status import render_hardware_status
from dashboard.realtime_view import (
    render_actuator_status,
    render_ai_module,
    render_comfort_metric,
    render_control_status,
    render_power_metrics,
    render_realtime_power_chart,
    render_sensor_metrics,
    render_solar_metrics,
)
from dashboard.ai_pool import render_resilience_status
from dashboard.simulation_view import render_simulation_page


# -- page config ----------------------------------------------------------
st.set_page_config(page_title="Smart HW Monitoring - Energy Saving Competition", layout="wide")
APP_ROOT = Path(__file__).resolve().parent


# -- helpers -------------------------------------------------------------
def _schedule_autorefresh(interval_s: float, key: str = "capture_autorefresh") -> bool:
    """Schedule Streamlit auto-refresh without blocking the script thread."""
    interval_ms = max(250, int(float(interval_s) * 1000.0))
    native = getattr(st, "autorefresh", None) or getattr(st, "experimental_autorefresh", None)
    if callable(native):
        native(interval=interval_ms, key=key)
        return True
    try:
        from streamlit_autorefresh import st_autorefresh  # type: ignore
        st_autorefresh(interval=interval_ms, key=key)
        return True
    except Exception:
        return False


def _is_bridge_connected(bridge) -> bool:
    conn = getattr(bridge, "connection", None)
    return bool(conn) and bool(getattr(conn, "is_open", False))


# -- page layout ---------------------------------------------------------
st.title("Smart Environmental Monitoring & AI Energy-Saving Control System")

# Mode selector
st.sidebar.header("System Config")
mode = st.sidebar.radio("Mode", ["Hardware (Real-time)", "Simulation (Digital Twin)"])
st.sidebar.divider()

cfg, cfg_warnings = load_app_config()
if cfg_warnings:
    with st.sidebar.expander("Config Warnings", expanded=False):
        for w in cfg_warnings:
            st.warning(w)


# =====================================================================
# HARDWARE MODE
# =====================================================================
if mode == "Hardware (Real-time)":
    from energy_system.hardware.serial_bridge import SerialBridge
    try:
        from serial.tools import list_ports as _serial_list_ports  # type: ignore
    except Exception:
        _serial_list_ports = None

    # ---- Serial port sidebar ----
    st.sidebar.subheader("Serial Port")
    port = st.sidebar.text_input("ESP32 COM Port", value=cfg.serial.port)

    detected_ports: list[str] = []
    if _serial_list_ports is not None:
        try:
            detected_ports = [p.device for p in _serial_list_ports.comports()]
        except Exception:
            detected_ports = []
    if detected_ports:
        st.sidebar.caption(f"Detected: {', '.join(detected_ports)}")
        if port not in detected_ports:
            st.sidebar.warning("Port not in detected list.")
    else:
        st.sidebar.error("No serial ports detected. Check USB cable/driver/board power.")

    baud = st.sidebar.number_input(
        "Baudrate", min_value=9600, max_value=921600, value=int(cfg.serial.baudrate), step=9600
    )

    @st.cache_resource
    def _get_bridge(port_name: str, baudrate: int):
        return SerialBridge(port=port_name, baudrate=int(baudrate), timeout=2)

    connect_clicked = st.sidebar.button("Connect/Reconnect")
    if connect_clicked:
        st.cache_resource.clear()

    bridge = _get_bridge(port, int(baud))
    if connect_clicked:
        try:
            ok = bridge.connect()
        except Exception as e:
            ok = False
            st.sidebar.error(f"Connection error: {e}")
        st.session_state["bridge_connected"] = bool(ok)

    connected = _is_bridge_connected(bridge)
    if connected:
        st.sidebar.success(f"Connected: {port} @ {int(baud)}")
    else:
        st.sidebar.warning("Not connected: click Connect/Reconnect")

    st.sidebar.info("Sensors: DHT22, BH1750, SGP30, INA219 (optional)")

    # ---- Port Manager (COM contention diagnostics) ----
    with st.sidebar.expander("Port Manager (diagnose COM conflicts)", expanded=False):
        st.caption(
            "Windows COM ports are exclusive resources. "
            "Recommendation: keep dashboard disconnected and let main.py own the port; "
            "dashboard reads data from logs."
        )
        try:
            from energy_system.utils.process_manager_windows import (
                find_port_contenders,
                find_com_owner_via_handle,
                stop_processes,
            )
        except Exception:
            find_port_contenders = None
            find_com_owner_via_handle = None
            stop_processes = None

        if find_port_contenders is None:
            st.info("Port Manager available on Windows + PowerShell only.")
        else:
            st.markdown("**Exact Query (optional)**")
            st.caption(
                "For exact COM-owning PID, install Sysinternals handle.exe "
                "and place it at ./tools/handle.exe or in PATH."
            )
            if st.button("Exact Lookup (handle.exe)", key="pm_exact") and callable(find_com_owner_via_handle):
                st.session_state["pm_exact_rows"] = find_com_owner_via_handle(port)

            owners = st.session_state.get("pm_exact_rows") or []
            if owners:
                st.success("Processes holding COM handle:")
                st.dataframe(owners, use_container_width=True, hide_index=True)
            else:
                st.info("No exact owners detected (or handle.exe not installed).")

            st.divider()
            st.markdown("**Heuristic Scan (no extra tools)**")
            if st.button("Scan Contenders", key="pm_scan") or ("pm_rows" not in st.session_state):
                st.session_state["pm_rows"] = [
                    {"pid": p.pid, "name": p.name, "cmd": p.command_line,
                     "created": p.creation_date or ""}
                    for p in find_port_contenders(port)
                ]
            rows = st.session_state.get("pm_rows") or []
            if not rows:
                st.success("No likely contenders found.")
            else:
                st.warning("Processes that may conflict (not all actually hold COM):")
                st.dataframe(rows, use_container_width=True, hide_index=True)
                pids = [int(r.get("pid")) for r in rows if isinstance(r, dict)
                        if isinstance(r.get("pid"), int)]
                kill_pids = st.multiselect("Select PIDs to kill", options=pids, default=[])
                confirm = st.checkbox("I confirm I want to kill selected processes", value=False)
                if st.button("Kill Selected PIDs", key="pm_kill"):
                    if not confirm:
                        st.error("Check the confirmation box first.")
                    elif not kill_pids:
                        st.info("No PIDs selected.")
                    else:
                        ok = bool(stop_processes(kill_pids)) if stop_processes else False
                        if ok:
                            st.success("Kill command sent. Re-scan to confirm.")
                        else:
                            st.error("Kill failed (permission denied or PID already exited).")

    # ---- Battery / capture config ----
    st.sidebar.subheader("Battery Estimation")
    soc_capacity_mah = float(st.sidebar.number_input(
        "Battery Capacity (mAh)", min_value=500, max_value=100000, value=10000, step=500
    ))
    soc_initial_percent = float(st.sidebar.number_input(
        "Initial SOC (%)", min_value=0, max_value=100, value=80, step=1
    ))
    electricity_price_cny = float(st.sidebar.number_input(
        "Electricity Price (CNY/kWh)", min_value=0.0, max_value=10.0, value=0.80, step=0.05
    ))

    soc_model = st.session_state.get("battery_soc_model")
    soc_model_sig = (soc_capacity_mah, soc_initial_percent)
    if soc_model is None or st.session_state.get("battery_soc_sig") != soc_model_sig:
        st.session_state["battery_soc_model"] = BatterySOC(
            capacity_mah=soc_capacity_mah,
            initial_soc_percent=soc_initial_percent,
            current_key="solar_current_ma",
        )
        st.session_state["battery_soc_sig"] = soc_model_sig

    # ---- Capture control ----
    st.sidebar.subheader("Capture Control")
    interval_s = st.sidebar.number_input(
        "Capture Interval (s)", min_value=0.5, max_value=30.0, value=2.0, step=0.5
    )
    c_start, c_stop, c_clear = st.sidebar.columns(3)
    if c_start.button("Start"):
        st.session_state["capture_running"] = True
    if c_stop.button("Stop"):
        st.session_state["capture_running"] = False
    if c_clear.button("Clear"):
        st.session_state["capture_rows"] = []
        model = st.session_state.get("battery_soc_model")
        if isinstance(model, BatterySOC):
            model.reset(soc_percent=soc_initial_percent)

    for key in ("capture_running", "capture_rows"):
        if key not in st.session_state:
            st.session_state[key] = True if key == "capture_running" else []

    if st.session_state["capture_running"]:
        st.sidebar.success("Capturing...")
        if not _is_bridge_connected(bridge):
            bridge.connect()
        sample = bridge.read_sensors() or {}
        if sample:
            sample["_ts"] = time.time()
            sample["power_w"] = estimate_channel_power_w(sample)
            sample["solar_power_w"] = estimate_channel_power_w(sample, prefix="solar_")
            model = st.session_state.get("battery_soc_model")
            if isinstance(model, BatterySOC):
                soc_stats = model.update_from_sample(sample, ts=sample["_ts"])
                sample["soc_percent"] = soc_stats.soc_percent
                st.session_state["soc_percent"] = soc_stats.soc_percent
            rows = st.session_state.get("capture_rows", [])
            rows.append(sample)
            st.session_state["capture_rows"] = rows[-300:]
            st.session_state["last_sensors"] = sample
        auto_ok = _schedule_autorefresh(float(interval_s), key="capture_autorefresh")
        if not auto_ok:
            st.sidebar.caption("Auto-refresh not supported; use Refresh button.")
    else:
        st.sidebar.info("Stopped")

    # ---- Refresh button ----
    if st.sidebar.button("Refresh Once"):
        st.session_state["last_refresh_at"] = time.time()
        if _is_bridge_connected(bridge):
            st.session_state["last_sensors"] = bridge.read_sensors()
        else:
            default_label = (getattr(cfg, "run_label", None) or "saving").strip() or "saving"
            log_path = APP_ROOT / "logs" / f"hardware_{default_label}.jsonl"
            st.session_state["last_sensors"] = read_last_jsonl(str(log_path))

        refreshed = st.session_state.get("last_sensors")
        if isinstance(refreshed, dict):
            model = st.session_state.get("battery_soc_model")
            if isinstance(model, BatterySOC):
                soc_stats = model.update_from_sample(refreshed, ts=time.time())
                refreshed.setdefault("soc_percent", soc_stats.soc_percent)
                st.session_state["soc_percent"] = soc_stats.soc_percent

        rerun_fn = getattr(st, "rerun", None) or getattr(st, "experimental_rerun", None)
        if callable(rerun_fn):
            rerun_fn()

    # ---- Data display ----
    sensor_data = st.session_state.get("last_sensors")
    if not sensor_data:
        if not connected:
            default_label = (getattr(cfg, "run_label", None) or "saving").strip() or "saving"
            log_path = APP_ROOT / "logs" / f"hardware_{default_label}.jsonl"
            sensor_data = read_last_jsonl(str(log_path))
            if sensor_data:
                st.session_state["last_sensors"] = sensor_data

    if isinstance(sensor_data, dict):
        if sensor_data.get("soc_percent") is None:
            fallback_soc = st.session_state.get("soc_percent")
            if isinstance(fallback_soc, (int, float)):
                sensor_data["soc_percent"] = float(fallback_soc)

    last_refresh_at = st.session_state.get("last_refresh_at")
    if isinstance(last_refresh_at, (int, float)):
        st.sidebar.caption(f"Last refresh: {time.strftime('%H:%M:%S', time.localtime(last_refresh_at))}")

    if not sensor_data:
        st.warning(
            "No hardware data yet. Click Refresh in sidebar, "
            "or verify main.py is writing to logs/hardware_saving.jsonl."
        )
    else:
        with st.expander("Connection Health (SerialBridge)", expanded=False):
            st.json(bridge.get_health() if connected else {"connected": False})

        render_sensor_metrics(sensor_data, connected)
        render_actuator_status(sensor_data)

        default_label = (getattr(cfg, "run_label", None) or "saving").strip() or "saving"
        render_hardware_status(cfg, APP_ROOT, default_label)

        render_energy_module(sensor_data, cfg, APP_ROOT)

        today_str = time.strftime("%Y-%m-%d")
        daily_path = APP_ROOT / "logs" / f"daily_energy_{default_label}_{today_str}.json"
        daily_obj = None
        try:
            if daily_path.exists():
                daily_obj = json.loads(daily_path.read_text(encoding="utf-8"))
        except Exception:
            pass
        render_soc_module(sensor_data, st.session_state, daily_obj, electricity_price_cny)

        render_control_status(cfg, sensor_data)
        render_comfort_metric(sensor_data)
        render_ai_module(cfg)
        render_power_metrics(sensor_data)
        render_solar_metrics(sensor_data)

        st.subheader("AI Smart Advisor")
        st.caption(
            "AI reasoning and commands are logged by main.py and read by dashboard. "
            "Showing current sensor data below."
        )
        render_realtime_power_chart(st.session_state.get("capture_rows", []))

    # Energy comparison (always shown)
    render_energy_comparison(APP_ROOT)

    # Resilience + AI pool
    render_resilience_status(APP_ROOT)

# =====================================================================
# SIMULATION MODE
# =====================================================================
else:
    render_simulation_page()
