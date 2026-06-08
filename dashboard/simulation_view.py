"""Digital twin simulation view for the Streamlit dashboard."""

import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt
from energy_system.simulation.simulator import Simulator


def render_simulation_page() -> None:
    """Render the complete simulation mode page (digital twin comparison)."""
    st.sidebar.header("仿真参数")
    days_to_sim = st.sidebar.slider("仿真天数", min_value=1, max_value=7, value=2)

    @st.cache_data
    def _run_simulation(days: int):
        sim_base = Simulator(mode="baseline")
        sim_save = Simulator(mode="saving")
        return sim_base.run_simulation(days=days), sim_save.run_simulation(days=days)

    st.warning("当前处于仿真模式。系统正通过高斯随机游走生成环境波动数据。")
    base_data, save_data = _run_simulation(days_to_sim)

    def _get_total_kwh(history: dict) -> float:
        v = history.get("total_kwh", 0.0)
        return float(v) if isinstance(v, (int, float)) else 0.0

    base_total_kwh = _get_total_kwh(base_data)
    save_total_kwh = _get_total_kwh(save_data)

    df_base = pd.DataFrame({k: v for k, v in base_data.items() if k != "total_kwh"})
    df_save = pd.DataFrame({k: v for k, v in save_data.items() if k != "total_kwh"})
    df_save["time_h"] = df_save["time_h"].round(2)

    # Metrics row
    col1, col2, col3, col4 = st.columns(4)
    saving_rate = (base_total_kwh - save_total_kwh) / base_total_kwh * 100 if base_total_kwh > 0 else 0.0
    col1.metric("基准能耗 (kWh)", f"{base_total_kwh:.2f}")
    col2.metric("节能能耗 (kWh)", f"{save_total_kwh:.2f}", f"-{saving_rate:.1f}%")
    col3.metric("减碳量 (kgCO2)", f"{(base_total_kwh - save_total_kwh) * 0.5:.2f}")
    col4.metric("平均舒适度 (TCI)", f"{df_save['comfort'].mean():.1f}%")

    st.divider()

    # Chart 1: indoor temperature
    st.subheader("1. 室内温度对抗曲线 (Baseline vs Saving)")
    fig_temp, ax_temp = plt.subplots(figsize=(10, 4))
    ax_temp.plot(df_base["time_h"], df_base["T_in"], label="T_in (Baseline)", color="red", alpha=0.6)
    ax_temp.plot(df_save["time_h"], df_save["T_in"], label="T_in (Saving)", color="green")
    ax_temp.plot(df_save["time_h"], df_save["T_set"], label="T_set (Saving Setpoint)",
                 color="blue", linestyle="--")
    ax_temp.set_xlabel("Time (Hours)")
    ax_temp.set_ylabel("Temperature (°C)")
    ax_temp.legend()
    ax_temp.grid()
    st.pyplot(fig_temp)

    # Chart 2: external environment
    st.subheader("2. 外部真实环境参数模拟 (含高斯随机游走与噪声)")
    fig_env, ax1 = plt.subplots(figsize=(10, 3))
    ax2 = ax1.twinx()
    ax1.plot(df_save["time_h"], df_save["T_out"], color="orange", label="T_out (External Temp)")
    ax2.fill_between(df_save["time_h"], df_save["I_solar"], alpha=0.3,
                     color="yellow", label="Solar Radiation")
    ax1.set_xlabel("Time (Hours)")
    ax1.set_ylabel("Temperature (°C)", color="orange")
    ax2.set_ylabel("Radiation (W/m2)", color="olive")
    fig_env.legend(loc="upper left")
    st.pyplot(fig_env)

    # Chart 3: power consumption
    st.subheader("3. 动态系统功率消耗 (W)")
    fig_pwr, ax_pwd = plt.subplots(figsize=(10, 3))
    ax_pwd.plot(df_base["time_h"], df_base["power_total"], label="Power (Baseline)", color="silver")
    ax_pwd.plot(df_save["time_h"], df_save["power_total"], label="Power (Saving)",
                color="purple", alpha=0.8)
    ax_pwd.set_xlabel("Time (Hours)")
    ax_pwd.set_ylabel("Power Consumption (W)")
    ax_pwd.legend()
    st.pyplot(fig_pwr)
