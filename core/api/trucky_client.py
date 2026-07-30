"""Trucky App API 客户端。

Trucky 提供：
    - v3: 玩家在线状态 + 服务器实时位置
    - v2: 服务器热门地点实时路况
"""

from __future__ import annotations

import asyncio
from typing import Any, Dict, List

import aiohttp

from ..utils.exceptions import (
    ApiResponseException,
    NetworkException,
)
from .http_session import HttpSessionManager


# Trucky 服务器别名 -> 官方服务端 slug
TRAFFIC_SERVER_ALIAS = {
    "s1": "sim1",
    "s2": "sim2",
    "p": "eupromods1",
    "a": "arc1",
}


class TruckyClient:
    BASE_URL = "https://api.truckyapp.com"

    def __init__(self, http: HttpSessionManager) -> None:
        self._http = http

    # ------------------------------------------------------------------ #
    # 在线状态 (v3)
    # ------------------------------------------------------------------ #
    async def get_player_online(self, tmp_id: str) -> Dict[str, Any]:
        """查询玩家实时在线情况（含服务器、坐标、位置）。"""
        sess = self._require_session()
        url = f"{self.BASE_URL}/v3/map/online"
        try:
            async with sess.get(
                url, params={"playerID": tmp_id}, timeout=5
            ) as resp:
                data = await resp.json()
                if resp.status != 200:
                    return {
                        "online": False,
                        "debug_error": f"Trucky V3 API 返回非 200: {resp.status}",
                    }
                online_data = (
                    data.get("response") if "response" in data else data
                )
                if not online_data:
                    return {"online": False, "raw": data}
                online = bool(
                    online_data.get("online") is True and online_data.get("server")
                )
                if not online:
                    return {"online": False, "raw": online_data}
                server_details = online_data.get("serverDetails", {}) or {}
                location = online_data.get("location", {}) or {}
                poi = location.get("poi", {}) or {}
                return {
                    "online": True,
                    "server_name": server_details.get(
                        "name",
                        f"未知服务器 ({online_data.get('server')})",
                    ),
                    "game": server_details.get("game"),
                    "country": poi.get("country") or location.get("country"),
                    "real_name": poi.get("realName") or location.get("realName"),
                    "x": online_data.get("x"),
                    "y": online_data.get("y"),
                    "server_id": online_data.get("server"),
                    "server_details": server_details,
                }
        except aiohttp.ClientError as exc:
            raise NetworkException(f"Trucky V3 网络异常: {exc}") from exc
        except asyncio.TimeoutError as exc:
            raise NetworkException("Trucky V3 请求超时") from exc
        except Exception as exc:
            return {
                "online": False,
                "debug_error": f"Trucky V3 解析异常: {exc.__class__.__name__}",
            }

    # ------------------------------------------------------------------ #
    # 路况 (v2)
    # ------------------------------------------------------------------ #
    async def get_traffic_top(self, server_key: str) -> List[Dict[str, Any]]:
        """获取指定服务器热门地点实时路况。"""
        sess = self._require_session()
        key = (server_key or "").strip().lower()
        server = TRAFFIC_SERVER_ALIAS.get(key, key)
        if not server:
            raise ApiResponseException("无效的服务器标识")

        url = f"{self.BASE_URL}/v2/traffic/top"
        try:
            async with sess.get(
                url,
                params={"game": "ets2", "server": server},
                timeout=self._http.timeout,
            ) as resp:
                if resp.status == 404:
                    return []
                if resp.status != 200:
                    raise ApiResponseException(
                        f"Trucky 路况 API 状态码: {resp.status}"
                    )
                data = await resp.json()
                items = data.get("response") if isinstance(data, dict) else data
                if not isinstance(items, list):
                    raise ApiResponseException("路况 API 数据结构异常")
                return items
        except (ApiResponseException, NetworkException):
            raise
        except aiohttp.ClientError as exc:
            raise NetworkException(f"Trucky 路况 API 网络异常: {exc}") from exc
        except asyncio.TimeoutError as exc:
            raise NetworkException("Trucky 路况 API 请求超时") from exc

    # ------------------------------------------------------------------ #
    # 工具
    # ------------------------------------------------------------------ #
    def _require_session(self) -> aiohttp.ClientSession:
        sess = self._http.session
        if sess is None:
            raise NetworkException("Trucky HTTP 会话尚未初始化")
        return sess


__all__ = ["TruckyClient"]
