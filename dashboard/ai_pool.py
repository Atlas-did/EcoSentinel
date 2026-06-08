"""AI candidate pool and self-healing status display for the Streamlit dashboard."""

import streamlit as st
import pandas as pd
from pathlib import Path
from energy_system.utils.file_io import read_jsonl


def render_resilience_status(app_root) -> None:
    """Render self-healing / resilience status from log data."""
    st.divider()
    st.subheader("🛡️ 自恢复状态（基于 main.py 日志）")
    run_label = st.selectbox("选择日志标签", ["saving", "baseline"], index=0)
    rows = read_jsonl(app_root / "logs" / f"hardware_{run_label}.jsonl", max_lines=500)

    if not rows:
        st.info("暂无 main.py 日志：先运行 main.py 才会生成 logs/hardware_<label>.jsonl")
        return

    last = rows[-1]
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("safe_mode", str(last.get("safe_mode")))
    c2.metric("safe_reason", str(last.get("safe_reason") or "--"))
    c3.metric("AI reject", ",".join(last.get("ai_reject_reasons") or []) or "--")
    res = last.get("resilience") or {}
    res_state = res.get("state") or res.get("resilience_state") or "--"
    res_incident = res.get("incident_id") or "--"
    res_last_action = res.get("last_action") or "--"
    c4.metric("resilience", f"{res_state} / {res_last_action}")

    with st.expander("最近一条健康详情", expanded=False):
        st.json({
            "bridge_health": last.get("bridge_health"),
            "ai_accepted_commands": last.get("ai_accepted_commands"),
            "ai_rejected_commands": last.get("ai_rejected_commands"),
            "resilience": {
                "state": res_state,
                "incident_id": res_incident,
                "last_action": res_last_action,
                "last_action_reason": res.get("last_action_reason"),
            },
        })

    _render_ai_candidate_aggregation(rows)


def _render_ai_candidate_aggregation(rows: list[dict]) -> None:
    """Render AI candidate pool aggregation table from log rows."""
    st.subheader("🧠 AI 反馈闭环（候选池聚合）")
    df_ai = pd.DataFrame(rows)
    if df_ai.empty:
        st.info("日志为空，暂无 AI 反馈数据。")
        return

    # Ensure required columns exist
    for col in ["ai_candidate_id", "ai_source", "ai_latency_ms", "ai_score",
                "ai_cloud_error", "ai_accepted_commands"]:
        if col not in df_ai.columns:
            df_ai[col] = None

    def _accepted_to_bool(v) -> bool:
        if isinstance(v, list):
            return len(v) > 0
        return bool(v)

    df_ai["ai_success"] = df_ai["ai_accepted_commands"].apply(_accepted_to_bool)

    df_pool = df_ai.dropna(subset=["ai_candidate_id"]).copy()
    if df_pool.empty:
        st.info("暂无 candidate 维度数据：请运行启用 AI 的 main.py，并确保写入 ai_candidate_id 字段。")
        return

    df_pool["ai_latency_ms"] = pd.to_numeric(df_pool["ai_latency_ms"], errors="coerce")
    df_pool["ai_score"] = pd.to_numeric(df_pool["ai_score"], errors="coerce")
    df_pool["ai_cloud_error"] = df_pool["ai_cloud_error"].fillna("")
    df_pool["cloud_ok"] = ((df_pool["ai_source"] == "cloud") &
                           (df_pool["ai_cloud_error"].astype(str) == ""))
    df_pool["cloud_fail"] = ((df_pool["ai_source"] == "cloud") &
                             (df_pool["ai_cloud_error"].astype(str) != ""))
    df_pool["local_used"] = df_pool["ai_source"] == "local_fallback"

    agg = (
        df_pool.groupby("ai_candidate_id", dropna=False)
        .agg(
            samples=("ai_candidate_id", "count"),
            success_rate=("ai_success", "mean"),
            avg_latency_ms=("ai_latency_ms", "mean"),
            avg_score=("ai_score", "mean"),
            cloud_ok=("cloud_ok", "sum"),
            cloud_fail=("cloud_fail", "sum"),
            local_used=("local_used", "sum"),
        )
        .reset_index()
    )
    agg["success_rate"] = (agg["success_rate"] * 100.0).round(1)
    agg["avg_latency_ms"] = agg["avg_latency_ms"].round(1)
    agg["avg_score"] = agg["avg_score"].round(3)
    agg = agg.sort_values(["samples", "avg_score"], ascending=[False, False])

    st.dataframe(agg, use_container_width=True, hide_index=True)

    # Recent tuning event
    tuning_event = None
    if "ai_tuning_event" in df_ai.columns:
        ev_series = df_ai["ai_tuning_event"].dropna()
        if not ev_series.empty:
            tuning_event = ev_series.iloc[-1]
    if tuning_event is not None:
        with st.expander("最近一次 tuning_event", expanded=False):
            st.json(tuning_event)
