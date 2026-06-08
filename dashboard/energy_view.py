"""Energy, solar, SOC, and savings display components for the Streamlit dashboard."""

import json
import time
import streamlit as st
from pathlib import Path
from dashboard.data_loader import read_daily_summary


def render_energy_module(sensor_data: dict, cfg, app_root) -> None:
    """Render energy storage, solar, SOC, and cost savings module."""
    default_label = (getattr(cfg, "run_label", None) or "saving").strip() or "saving"

    st.subheader("🔋 储能与能源模块（负载/太阳能）")
    e1, e2, e3, e4 = st.columns(4)
    ewh = sensor_data.get("energy_wh")
    swh = sensor_data.get("solar_energy_wh")
    net = None
    if isinstance(ewh, (int, float)) and isinstance(swh, (int, float)):
        net = float(ewh) - float(swh)
    e1.metric("进程累计负载 (Wh)", f"{float(ewh):.2f}" if isinstance(ewh, (int, float)) else "--")
    e2.metric("进程累计太阳能 (Wh)", f"{float(swh):.2f}" if isinstance(swh, (int, float)) else "--")
    e3.metric("进程累计净值 (Wh)", f"{net:.2f}" if isinstance(net, (int, float)) else "--")
    pwr = sensor_data.get("power_w")
    e4.metric("当前负载功率 (W)", f"{float(pwr):.2f}" if isinstance(pwr, (int, float)) else "--")

    # Daily summary from file
    today = time.strftime("%Y-%m-%d", time.localtime())
    daily_path = app_root / "logs" / f"daily_energy_{default_label}_{today}.json"
    daily_obj = read_daily_summary(daily_path)

    if isinstance(daily_obj, dict):
        d1, d2, d3, d4 = st.columns(4)
        d1.metric("当日负载 (Wh)", str(daily_obj.get("load_energy_wh", "--")))
        d2.metric("当日太阳能 (Wh)", str(daily_obj.get("solar_energy_wh", "--")))
        d3.metric("当日净值 (Wh)", str(daily_obj.get("net_energy_wh", "--")))
        d4.metric("日汇总更新时间", str(daily_obj.get("updated_at", "--")))
    else:
        st.caption("未检测到日汇总文件（main.py 运行后会生成）。")


def render_soc_module(sensor_data: dict, st_session_state: dict,
                      daily_obj: dict | None, electricity_price_cny: float) -> None:
    """Render Battery SOC and solar revenue estimation."""
    st.subheader("🔋 Phase 2：SOC 与光伏收益")
    p1, p2, p3 = st.columns(3)

    soc_pct = sensor_data.get("soc_percent") if isinstance(sensor_data, dict) else None
    if not isinstance(soc_pct, (int, float)):
        soc_pct = st_session_state.get("soc_percent")

    today_solar_wh = None
    if isinstance(daily_obj, dict):
        v = daily_obj.get("solar_energy_wh")
        if isinstance(v, (int, float)):
            today_solar_wh = float(v)
    if today_solar_wh is None:
        sv = sensor_data.get("solar_energy_wh") if isinstance(sensor_data, dict) else None
        if isinstance(sv, (int, float)):
            today_solar_wh = float(sv)

    cost_saved_cny = None
    if isinstance(today_solar_wh, (int, float)):
        cost_saved_cny = (float(today_solar_wh) / 1000.0) * electricity_price_cny

    p1.metric("电池 SOC", f"{float(soc_pct):.1f}%" if isinstance(soc_pct, (int, float)) else "--")
    p2.metric("今日光伏发电量",
              f"{float(today_solar_wh):.2f} Wh" if isinstance(today_solar_wh, (int, float)) else "--")
    p3.metric("储能节省电费(估算)",
              f"¥{float(cost_saved_cny):.2f}" if isinstance(cost_saved_cny, (int, float)) else "--")
    st.caption(
        f"估算口径：节省电费 = 今日光伏发电量(kWh) × 电价({electricity_price_cny:.2f} 元/kWh)"
    )


def render_energy_comparison(app_root) -> None:
    """Render baseline vs saving energy comparison from log files."""
    from energy_system.utils.file_io import read_jsonl
    import pandas as pd
    import matplotlib.pyplot as plt

    st.divider()
    st.subheader("📉 A 方案：系统能耗/节能对比（基于日志）")
    st.caption(
        "分别运行两次 main.py：RUN_LABEL=baseline 与 RUN_LABEL=saving。"
        "看板会自动对比 logs/ 下两份日志。"
    )

    base_rows = read_jsonl(app_root / "logs" / "hardware_baseline.jsonl")
    save_rows = read_jsonl(app_root / "logs" / "hardware_saving.jsonl")

    col1, col2, col3 = st.columns(3)
    if base_rows and save_rows:
        base_kwh = float(base_rows[-1].get("energy_wh") or 0.0) / 1000.0
        save_kwh = float(save_rows[-1].get("energy_wh") or 0.0) / 1000.0
        saving_rate = (base_kwh - save_kwh) / base_kwh * 100 if base_kwh > 0 else 0.0

        col1.metric("基准能耗 (kWh)", f"{base_kwh:.3f}")
        col2.metric("节能能耗 (kWh)", f"{save_kwh:.3f}", f"-{saving_rate:.1f}%")
        col3.metric("节省电量 (kWh)", f"{max(0.0, base_kwh - save_kwh):.3f}")

        def _to_df(rows, label):
            df = pd.DataFrame(rows)
            df["label"] = label
            df["idx"] = range(len(df))
            return df

        df_all = pd.concat([_to_df(base_rows, "baseline"), _to_df(save_rows, "saving")],
                           ignore_index=True)
        if "power_w" not in df_all.columns:
            df_all["power_w"] = None
        df_all = df_all.dropna(subset=["power_w"])

        if not df_all.empty:
            fig, ax = plt.subplots(figsize=(10, 3))
            for label, g in df_all.groupby("label"):
                ax.plot(g["idx"], g["power_w"], label=label)
            ax.set_xlabel("Sample Index")
            ax.set_ylabel("Power (W)")
            ax.grid(True)
            ax.legend()
            st.pyplot(fig)
        else:
            st.info("日志里缺少 power_w：请确认 INA219 已接入且固件回传 pwr_mw 或 bus_v/current_ma。")
    else:
        col1.metric("基准能耗 (kWh)", "--")
        col2.metric("节能能耗 (kWh)", "--")
        col3.metric("节能率", "--")
        st.info("未检测到两份日志：需要 logs/hardware_baseline.jsonl 与 logs/hardware_saving.jsonl。")
