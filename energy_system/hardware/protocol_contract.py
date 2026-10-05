"""串口协议清单的加载器（M5）：让主机行为**由清单驱动**，而不是各自写字面量。

清单位置：``protocol/eco_protocol.yaml``（仓库根）。找不到时回退到下面的默认值并告警 ——
边缘部署时不应该因为少一个文件就直接崩。
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from energy_system.utils.logger import setup_logger

logger = setup_logger("ProtocolContract")

MANIFEST_PATH = Path(__file__).resolve().parents[2] / "protocol" / "eco_protocol.yaml"

#: 清单缺失时的兜底（与清单里的值保持一致；改动请同时改两处并由契约测试守住）
DEFAULT_MAX_FRAME_BYTES = 4096
DEFAULT_BAUDRATE = 115200

_CACHE: dict[str, Any] | None = None


def load_manifest() -> dict[str, Any]:
    """读取并缓存协议清单；失败则返回空 dict（调用方用默认值）。"""
    global _CACHE
    if _CACHE is not None:
        return _CACHE
    try:
        import yaml

        _CACHE = yaml.safe_load(MANIFEST_PATH.read_text(encoding="utf-8")) or {}
    except Exception as exc:  # 文件缺失 / YAML 坏了都不该让边缘侧停摆
        logger.warning(f"协议清单不可用（{exc}）；使用内置默认值")
        _CACHE = {}
    return _CACHE


def max_frame_bytes() -> int:
    """单帧最大字节数：超过即丢弃（保护主机解析器不被异常刷屏拖垮）。"""
    transport = load_manifest().get("transport") or {}
    return int(transport.get("max_frame_bytes", DEFAULT_MAX_FRAME_BYTES))


def baudrate() -> int:
    transport = load_manifest().get("transport") or {}
    return int(transport.get("baudrate", DEFAULT_BAUDRATE))
