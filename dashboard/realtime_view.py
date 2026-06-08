"""Real-time sensor data display components for the Streamlit dashboard.

Renders the main monitoring view: sensor metrics, relay status, power/energy,
comfort score, and AI control module status.
"""

import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt
from dashboard.data_loader import estimate_channel_power_w


def render_sensor_metrics(sensor_data: dict, connected: bool) -> None:
    """Render the main sensor reading metrics row (temp, humidity, lux, eCO2)."""
    st.subheader("📡 硬件实时观测数据")
    data_ts = sensor_data.get("timestamp") if isinstance(sensor_data, dict) else None
    source = "串口" if connected else "日志"
    st.caption(f"数据来源：{source} | timestamp：{data_ts or '--'}")

    colA, colB, colC, colD = st.columns(4)
    temp_c = sensor_data.get("temperature")
    hum_pct = sensor_data.get("humidity")
    lux = sensor_data.get("illuminance")
    eco2 = sensor_data.get("eco2")

    colA.metric("环境温度", f"{temp_c:.1f} °C" if isinstance(temp_c, (int, float)) else "--")
    colB.metric("相对湿度", f"{hum_pct:.0f} %" if isinstance(hum_pct, (int, float)) else "--")
    colC.metric("光照强度", f"{lux:.0f} Lux" if isinstance(lux, (int, float)) else "--")
    colD.metric("eCO2 浓度", f"{eco2} ppm" if eco2 is not None else "--")

    # Sensorless / failed-sensor hint
    if all(v is None for v in (temp_c, hum_pct, lux, eco2)):
        errs = sensor_data.get("errors") if isinstance(sensor_data, dict) else None
        bh = sensor_data.get("bridge_health") if isinstance(sensor_data, dict) else None
        hint = "硬件在线，但传感器读数为空（未接传感器或读失败）。"
        if isinstance(bh, dict) and bh.get("connected") is True:
            hint += f" 串口已连接，read_attempts={bh.get('read_attempts')}。"
        st.info(hint)
        if errs:
            st.warning(f"固件错误：{errs}")


def render_actuator_status(sensor_data: dict) -> None:
    """Render relay and curtain actuator status."""
    relays = sensor_data.get("relays") if isinstance(sensor_data, dict) else None
    curtain_steps = sensor_data.get("curtain_steps") if isinstance(sensor_data, dict) else None
    if relays is not None or curtain_steps is not None:
        r1, r2, r3 = st.columns(3)
        r1.metric("继电器状态", str(relays) if relays is not None else "--")
        r2.metric("窗帘步数", str(curtain_steps) if curtain_steps is not None else "--")
        r3.metric("错误字段", "有" if sensor_data.get("errors") else "无")


def render_power_metrics(sensor_data: dict) -> None:
    """Render INA219 power monitoring metrics (bus voltage, current, power)."""
    bus_v = sensor_data.get("bus_v")
    current_ma = sensor_data.get("current_ma")
    pwr_mw = sensor_data.get("pwr_mw")

    st.subheader("⚡ 储能与多能互补监测 (INA219)")
    c1, c2, c3 = st.columns(3)
    c1.metric("母线电压", f"{bus_v:.2f} V" if isinstance(bus_v, (int, float)) else "--")
    c2.metric("电流", f"{current_ma:.0f} mA" if isinstance(current_ma, (int, float)) else "--")
    c3.metric("功率", f"{pwr_mw/1000:.2f} W" if isinstance(pwr_mw, (int, float)) else "--")


def render_solar_metrics(sensor_data: dict) -> None:
    """Render solar input monitoring metrics."""
    solar_bus_v = sensor_data.get("solar_bus_v")
    solar_current_ma = sensor_data.get("solar_current_ma")
    solar_pwr_mw = sensor_data.get("solar_pwr_mw")

    st.subheader("☀️ 太阳能输入监测 (INA219#2，可选)")
    s1, s2, s3 = st.columns(3)
    s1.metric("太阳能电压", f"{solar_bus_v:.2f} V" if isinstance(solar_bus_v, (int, float)) else "--")
    s2.metric("太阳能电流", f"{solar_current_ma:.0f} mA" if isinstance(solar_current_ma, (int, float)) else "--")
    s3.metric("太阳能功率", f"{solar_pwr_mw/1000:.2f} W" if isinstance(solar_pwr_mw, (int, float)) else "--")


def render_comfort_metric(sensor_data: dict) -> None:
    """Render human comfort score."""
    st.subheader("🧍 人体舒适度模块")
    cs = sensor_data.get("comfort_score")
    st.metric("舒适度评分", f"{float(cs):.2f}" if isinstance(cs, (int, float)) else "--")


def render_control_status(cfg, sensor_data: dict) -> None:
    """Render control module status (rule control, safe mode, etc.)."""
    st.subheader("🎛️ 智能调控模块（状态）")
    cA, cB, cC, cD = st.columns(4)
    cA.metric("规则控制", "开启" if bool(getattr(cfg.control, "enable_rule_control", False)) else "关闭")
    cB.metric("最小动作间隔(s)", str(getattr(cfg.control, "actuate_min_interval_s", "--")))
    cC.metric("safe_mode", str(sensor_data.get("safe_mode")))
    cD.metric("safe_reason", str(sensor_data.get("safe_reason") or "--"))


def render_ai_module(cfg) -> None:
    """Render AI module placeholder / enabled indicator."""
    st.subheader("🤖 AI 辅助模块")
    if not bool(getattr(cfg.ai, "enabled", False)):
        st.info("AI 当前默认关闭（后续再启用与调试）。")
    else:
        st.caption("AI 已启用：详细候选池与反馈闭环见下方 AI 聚合区块。")


def render_realtime_power_chart(capture_rows: list[dict]) -> None:
    """Render real-time acquisition power curve from captured samples."""
    if not capture_rows:
        return
    df_cap = pd.DataFrame(capture_rows)
    if "power_w" in df_cap.columns:
        df_cap = df_cap.dropna(subset=["power_w"])
    if df_cap.empty:
        return

    st.subheader("📈 实时采集功率曲线")
    fig_rt, ax_rt = plt.subplots(figsize=(10, 3))
    ax_rt.plot(range(len(df_cap)), df_cap["power_w"], color="purple", label="load")

    if "solar_power_w" in df_cap.columns and df_cap["solar_power_w"].notna().any():
        ax_rt.plot(range(len(df_cap)), df_cap["solar_power_w"].ffill(),
                   color="green", label="solar")
    ax_rt.set_xlabel("Sample Index")
    ax_rt.set_ylabel("Power (W)")
    ax_rt.grid(True)
    ax_rt.legend()
    st.pyplot(fig_rt)
