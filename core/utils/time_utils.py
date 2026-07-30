"""时间格式化工具。

TruckersMP API 多使用 ISO 8601 UTC 时间戳，本模块负责做
可读化展示与 UTC+8 时区转换。
"""

from __future__ import annotations
from datetime import datetime, timedelta
from typing import Optional


def format_timestamp_to_readable(timestamp_str: Optional[str]) -> str:
    """将 TruckersMP API 返回的 UTC 时间戳转换为可读 ISO 8601 字符串。

    Args:
        timestamp_str: 如 ``"2024-05-28T14:30:00.000Z"``

    Returns:
        ``"YYYY-MM-DD HH:MM:SS"``；无法解析时回退原值。
    """
    if not timestamp_str:
        return "未知"
    try:
        clean = timestamp_str.replace("T", " ").split(".")[0].replace("Z", "")
        dt_utc = datetime.strptime(clean, "%Y-%m-%d %H:%M:%S")
        return dt_utc.strftime("%Y-%m-%d %H:%M:%S")
    except Exception:
        return timestamp_str.split("T")[0] if "T" in timestamp_str else (timestamp_str or "未知")


def format_timestamp_to_beijing(timestamp_str: Optional[str]) -> str:
    """将 UTC 时间戳转换为 UTC+8 的可读字符串，并兼容多种格式。

    Args:
        timestamp_str: ISO 8601 / 简单字符串 / ``"never"`` (代表永久封禁)。

    Returns:
        ``"YYYY-MM-DD HH:MM:SS"``，对 ``"never"`` 直接返回"永久封禁"。
    """
    if not timestamp_str:
        return "未知"

    s = str(timestamp_str).strip()
    if s.lower().startswith("never"):
        return "永久封禁"

    try:
        clean = s.replace("T", " ").split(".")[0].replace("Z", "")
        dt_utc = datetime.strptime(clean, "%Y-%m-%d %H:%M:%S")
        dt_bj = dt_utc + timedelta(hours=8)
        return dt_bj.strftime("%Y-%m-%d %H:%M:%S")
    except Exception:
        try:
            iso = s.replace("Z", "+00:00")
            dt = datetime.fromisoformat(iso)
            return (dt + timedelta(hours=8)).strftime("%Y-%m-%d %H:%M:%S")
        except Exception:
            return s


__all__ = ["format_timestamp_to_readable", "format_timestamp_to_beijing"]
