"""core.services.footprint_service

服务器足迹业务：包含服务器 ID 别名、playerHistory 调用、footprint 回退。
"""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple

from ..api import VtcmClient
from ..utils.exceptions import (
    ApiResponseException,
    NetworkException,
    ServiceUnavailableException,
)
from ..utils.constants import PROMODS_SERVER_IDS


# Trucky/原 main.py 中维护的服务器别名 → TMP gameServer slug
SERVER_ALIAS = {
    "s1": "sim1",
    "s2": "sim2",
    "p": "eupromods1",
    "a": "arc1",
    "promods": "eupromods1",
    "promods1": "eupromods1",
    "sim1": "sim1",
    "sim2": "sim2",
    "arc1": "arc1",
}

# 简称 → 数字 server id / label
SERVER_ID_MAP = {
    "sim1": 2,
    "sim2": 41,
    "eupromods1": 50,
    "arc1": 7,
}
SERVER_LABEL_MAP = {
    "sim1": "SIM1",
    "sim2": "SIM2",
    "eupromods1": "ProMods",
    "arc1": "Arc",
}


class FootprintService:
    """足迹业务：封装历史轨迹数据拉取与过滤/归一化。"""

    def __init__(self, vtcm: VtcmClient) -> None:
        self._vtcm = vtcm

    @staticmethod
    def resolve_server(server_token: str) -> str:
        """把用户输入的简称（``s1``/``promods`` 等）映射到 ``sim1`` / ``eupromods1`` 等。"""
        key = (server_token or "").strip().lower()
        return SERVER_ALIAS.get(key, key)

    @staticmethod
    def server_label(server_key: str) -> str:
        return SERVER_LABEL_MAP.get(server_key, server_key.upper())

    @staticmethod
    def map_type(server_key: str) -> str:
        return "promods" if server_key in ("eupromods1", "promods", "promods1") else "ets"

    @staticmethod
    def candidate_server_ids(server_key: str, online_status: Dict[str, Any]) -> List[str]:
        """合并多个来源（fullmap、trucky、配置表）得到候选 server id 列表。"""
        ids: List[str] = []
        for k in ("serverId", "serverDetailsId", "apiServerId"):
            v = online_status.get(k)
            if v is None:
                continue
            s = str(v).strip()
            if s:
                ids.append(s)
        mapped = SERVER_ID_MAP.get(server_key)
        if mapped is not None:
            ids.append(str(mapped))
        seen, uniq = set(), []
        for sid in ids:
            if sid in seen:
                continue
            seen.add(sid)
            uniq.append(sid)
        return uniq

    @staticmethod
    def day_range() -> Tuple[str, str, datetime]:
        """返回 (start, end, now_local)。"""
        now = datetime.now()
        start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        end = now.replace(hour=23, minute=59, second=59, microsecond=0)
        return start.strftime("%Y-%m-%d %H:%M:%S"), end.strftime("%Y-%m-%d %H:%M:%S"), now

    async def fetch_history(
        self,
        tmp_id: str,
        server_ids: List[str],
        start: str,
        end: str,
    ) -> Tuple[List[Dict[str, Any]], Tuple[str, str]]:
        """按 ``server_ids`` 顺序拉取 playerHistory；首条非空即返回。

        Returns:
            ``(points, (start, end))``；``points`` 可能为空列表。
        """
        candidates = list(server_ids) + [""]
        seen = set()
        for sid in candidates:
            s = str(sid or "").strip()
            if s in seen:
                continue
            seen.add(s)
            points = await self._get_player_history(tmp_id, s or None, start, end)
            if points:
                return points, (start, end)
        return [], (start, end)

    async def fetch_history_extended(
        self,
        tmp_id: str,
        server_ids: List[str],
        now_local: datetime,
        days: int = 7,
    ) -> Tuple[List[Dict[str, Any]], Tuple[str, str]]:
        start = (now_local - timedelta(days=days)).strftime("%Y-%m-%d %H:%M:%S")
        end = now_local.strftime("%Y-%m-%d %H:%M:%S")
        candidates = list(server_ids) + [""]
        seen = set()
        for sid in candidates:
            s = str(sid or "").strip()
            if s in seen:
                continue
            seen.add(s)
            points = await self._get_player_history(tmp_id, s or None, start, end)
            if points:
                return points, (start, end)
        return [], (start, end)

    async def _get_player_history(
        self,
        tmp_id: str,
        server_id: Optional[str],
        start: str,
        end: str,
    ) -> List[Dict[str, Any]]:
        try:
            return await self._vtcm.get_player_history(tmp_id, start, end, server_id)
        except (NetworkException, ApiResponseException, ServiceUnavailableException):
            return []

    @staticmethod
    def filter_by_server(
        points: List[Dict[str, Any]],
        server_key: str,
        server_ids: List[str],
    ) -> List[Dict[str, Any]]:
        """按 server_id 过滤。"""
        if not points:
            return []
        has_server_id = any(
            str(p.get("serverId") or p.get("server_id") or p.get("server") or "").strip()
            for p in points
            if isinstance(p, dict)
        )
        if not has_server_id:
            return points
        if server_key in ("eupromods1", "promods", "promods1"):
            promods_str = {str(i) for i in PROMODS_SERVER_IDS}
            return [
                p for p in points
                if str(p.get("serverId") or p.get("server_id") or p.get("server"))
                in promods_str
            ]
        mapped = SERVER_ID_MAP.get(server_key)
        if mapped is not None:
            target = str(mapped)
            return [
                p for p in points
                if str(p.get("serverId") or p.get("server_id") or p.get("server")) == target
            ]
        if server_ids:
            target_set = {str(i) for i in server_ids}
            return [
                p for p in points
                if str(p.get("serverId") or p.get("server_id") or p.get("server"))
                in target_set
            ]
        return points

    @staticmethod
    def normalize_history_points(
        points: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        """将 API 返回的点归一化为 ``{axisX, axisY, serverId, heading, ts}``。"""
        out: List[Dict[str, Any]] = []
        for p in points:
            if not isinstance(p, dict):
                continue
            axis_x = (
                p.get("axisX")
                or p.get("axis_x")
                or p.get("posX")
                or p.get("x")
            )
            axis_y = (
                p.get("axisY")
                or p.get("axis_y")
                or p.get("posY")
                or p.get("y")
            )
            if axis_x is None or axis_y is None:
                continue
            try:
                x = float(axis_x)
                y = float(axis_y)
            except Exception:
                continue
            try:
                server_id = int(p.get("serverId") or p.get("server_id") or p.get("server") or 0)
            except Exception:
                server_id = 0
            heading = float(p.get("heading") or p.get("headingRad") or 0) or 0
            ts = int(p.get("ts") or p.get("timestamp") or 0)
            out.append({
                "axisX": x,
                "axisY": y,
                "serverId": server_id,
                "heading": heading,
                "ts": ts,
            })
        return out

    @staticmethod
    def to_km(value: Any) -> Optional[float]:
        """将里程字段（米/公里）统一转换为 km。"""
        try:
            v = float(value)
            if v > 10000:
                v = v / 1000.0
            return round(v, 2)
        except Exception:
            return None


__all__ = ["FootprintService"]
