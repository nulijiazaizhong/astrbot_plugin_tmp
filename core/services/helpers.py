"""core.services.helpers

跨服务复用的纯函数 / 类：
    - 头像 URL 清洗
    - 数字/字典的多字段兼容取值（不依赖业务语义）
    - 玩家权限组翻译（在原 main.py _translate_user_groups 的同源版本）
"""

from __future__ import annotations

from typing import Any, Dict, Iterable, List, Optional, Tuple

from ..utils.text_utils import translate_user_groups


def normalize_avatar_url(url: Optional[str]) -> Optional[str]:
    """移除 QQ 反引号、方括号等噪声，返回纯 URL 字符串。"""
    if not url:
        return None
    u = str(url).strip()
    for ch in ("`", '"', "'", "(", ")"):
        u = u.strip(ch)
    if u.startswith("[CQ:image,file="):
        u = u[len("[CQ:image,file="):]
    if u.endswith("]"):
        u = u[:-1]
    u = u.strip()
    return u or None


def pick_first(d: Dict[str, Any], *keys: str, default: Any = None) -> Any:
    """在 dict 上按多个候选键找出首个非 None 值。"""
    cur: Any = d
    for key in keys:
        if not isinstance(cur, dict):
            return default
        cur = cur.get(key)
    return cur if cur is not None else default


def pick_any(d: Dict[str, Any], *keys: str) -> Any:
    """在 dict 上按多个候选键找出首个真值（跳过空字符串 / 0 / None）。"""
    if not isinstance(d, dict):
        return None
    for key in keys:
        v = d.get(key)
        if v not in (None, "", 0):
            return v
    return None


def get_steam_id_from_player_info(player_info: Dict[str, Any]) -> Optional[str]:
    """抽取 SteamID64 字符串（多个备选字段）。"""
    if not isinstance(player_info, dict):
        return None
    for k in (
        "steamID64",
        "steamId",
        "steam_id",
        "steamID",
        "id64",
    ):
        v = player_info.get(k)
        if v:
            return str(v)
    return None


def to_int(value: Any, default: int = 0) -> int:
    """把任意类型转 int；失败回退 default。"""
    if value is None:
        return default
    if isinstance(value, bool):
        return int(value)
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(value)
    s = str(value).strip()
    if not s:
        return default
    try:
        return int(float(s))
    except Exception:
        return default


def format_ban_info(bans: Iterable[Dict[str, Any]]) -> Tuple[int, List[Dict[str, Any]]]:
    """按照 ``(active / 时间)`` 排序并返回 ``(总数, 已排序)``。"""
    items: List[Dict[str, Any]] = [b for b in bans if isinstance(b, dict)]
    items.sort(
        key=lambda b: (
            1 if b.get("active") else 0,
            b.get("timeAdded") or b.get("time_added") or "",
        ),
        reverse=False,
    )
    return len(items), items


# Re-export
__all__ = [
    "normalize_avatar_url",
    "pick_first",
    "pick_any",
    "get_steam_id_from_player_info",
    "to_int",
    "format_ban_info",
    "translate_user_groups",
]
