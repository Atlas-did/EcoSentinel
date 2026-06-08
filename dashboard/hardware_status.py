"""Hardware status inference and display for the Streamlit dashboard.

Infers which sensors are present/missing/unstable from log data and renders
the hardware module status grid.
"""

import streamlit as st
from dashboard.data_loader import read_tail_jsonl, read_last_jsonl


def infer_hardware(rows: list[dict], n: int = 30) -> dict:
    """Infer hardware presence based on last N rows.

    Returns per-module status: ok | missing | unstable | unknown
    """
    window = [r for r in rows[-int(n):] if isinstance(r, dict)]
    if not window:
        return {
            "dht22": "unknown", "bh1750": "unknown", "sgp30": "unknown",
            "ina219_load": "unknown", "ina219_solar": "unknown", "errors": [],
        }

    def _any_non_null(keys: list[str]) -> bool:
        for r in window:
            for k in keys:
                if k in r and r.get(k) is not None:
                    return True
        return False

    def _ever_has_key(keys: list[str]) -> bool:
        return any(any(k in r for k in keys) for r in window)

    def _status(keys: list[str]) -> str:
        has_val = _any_non_null(keys)
        ever_key = _ever_has_key(keys)
        if has_val:
            if any((k in r and r.get(k) is None) for r in window for k in keys):
                return "unstable"
            return "ok"
        return "missing"

    errs: list[str] = []
    for r in window:
        ev = r.get("errors")
        if isinstance(ev, list):
            errs.extend([str(x) for x in ev])
        if r.get("sample_type") == "error":
            e2 = r.get("error")
            if e2:
                errs.append(str(e2))

    return {
        "dht22": _status(["temperature", "humidity"]),
        "bh1750": _status(["illuminance"]),
        "sgp30": _status(["eco2", "tvoc"]),
        "ina219_load": _status(["bus_v", "current_ma", "pwr_mw", "power_w"]),
        "ina219_solar": _status(["solar_bus_v", "solar_current_ma", "solar_pwr_mw", "solar_power_w"]),
        "errors": sorted(set([e for e in errs if e])),
    }


def _badge_label(v: str) -> str:
    return {
        "ok": "已接入",
        "missing": "未检测到",
        "unstable": "不稳定",
        "unknown": "未知",
    }.get(v, str(v))


def render_hardware_status(cfg, app_root, default_label: str) -> None:
    """Render the hardware module presence/absence status grid."""
    st.subheader("🧩 硬件模块：已接入/缺失提示")
    infer_n = int(
        st.sidebar.slider(
            "硬件缺失判定窗口 N（连续 N 条）",
            min_value=5, max_value=120, value=30, step=5,
        )
    )

    hw_log = app_root / "logs" / f"hardware_{default_label}.jsonl"
    tail_rows = read_tail_jsonl(hw_log, max_rows=120)
    inferred = infer_hardware(tail_rows, n=infer_n)
    st.caption(f"推断口径：连续 {infer_n} 条为 null/缺 key + errors。")

    # Optional state truth (if present): overrides inference
    state_log = app_root / "logs" / f"hardware_state_{default_label}.jsonl"
    state_last = read_last_jsonl(str(state_log))
    if isinstance(state_last, dict):
        if "bh1750_ok" in state_last:
            inferred["bh1750"] = "ok" if state_last.get("bh1750_ok") else "missing"
        if "ina219_ok" in state_last:
            inferred["ina219_load"] = "ok" if state_last.get("ina219_ok") else "missing"
        if "ina219_solar_ok" in state_last:
            inferred["ina219_solar"] = "ok" if state_last.get("ina219_solar_ok") else "missing"
        if "sgp30_present" in state_last:
            inferred["sgp30"] = "ok" if state_last.get("sgp30_present") else "missing"

    h1, h2, h3, h4, h5 = st.columns(5)
    h1.metric("DHT22", _badge_label(inferred.get("dht22", "unknown")))
    h2.metric("BH1750", _badge_label(inferred.get("bh1750", "unknown")))
    h3.metric("SGP30", _badge_label(inferred.get("sgp30", "unknown")))
    h4.metric("INA219(负载)", _badge_label(inferred.get("ina219_load", "unknown")))
    h5.metric("INA219(太阳能)", _badge_label(inferred.get("ina219_solar", "unknown")))
    if inferred.get("errors"):
        st.caption(f"errors: {inferred.get('errors')}")
