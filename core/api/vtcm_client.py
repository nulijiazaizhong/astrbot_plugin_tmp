"""da.vtcm.link 公开数据 API 客户端。

本客户端**不再**承担任何车队平台管理职能（活动列表、成员 CRUD、加减积分、改密码等），
仅保留以下无 Token 的公开端：
    - 玩家里程 / 排名（Mileage / Mileage Rank）
    - DLC 市场列表
    - 玩家足迹（playerHistory）
    - 周边玩家列表（playerList，仅定位命令使用）
    - 历史车队 (vtc/history)
    - 官方服务器列表 / 插件版本（直接对接 api.truckersmp.com）

原 ``open.vtcm.link`` 上需要 Token 的接口在本版本中**已删除**。
"""

from __future__ import annotations

import asyncio
from typing import Any, Dict, List, Optional

import aiohttp

from ..utils.exceptions import (
    ApiResponseException,
    NetworkException,
)
from .http_session import HttpSessionManager


# ---------------------------------------------------------------------------
# 通用工具
# ---------------------------------------------------------------------------
def _to_km_2f(val: Any, default: float = 0.0) -> float:
    """把任意类型数值转换成公里（保留两位小数）。"""
    try:
        if val is None:
            return default
        if isinstance(val, (int, float)):
            return round(float(val) / 1000.0, 2)
        s = str(val).strip()
        if not s:
            return default
        return round(float(s) / 1000.0, 2)
    except Exception:
        return default


def _to_int_rank(val: Any) -> Optional[int]:
    """可空整数排名。"""
    try:
        if val is None:
            return None
        if isinstance(val, int):
            return val
        if isinstance(val, float):
            return int(val)
        s = str(val).strip()
        if not s:
            return None
        return int(float(s))
    except Exception:
        return None


class VtcmClient:
    """da.vtcm.link 公开数据 API 客户端。"""

    BASE_URL = "https://da.vtcm.link"
    OPEN_URL = "https://open.vtcm.link"

    def __init__(self, http: HttpSessionManager) -> None:
        self._http = http
        # 注：本类已不依赖 Token；保留字段以兼容旧初始化路径。
        self._api_token = ""

    # ------------------------------------------------------------------ #
    # 通用 GET 包装（da.vtcm.link，SSL 关闭）
    # ------------------------------------------------------------------ #
    async def _get_json(
        self,
        url: str,
        *,
        params: Optional[Dict[str, Any]] = None,
        use_token: bool = False,
        verify_ssl: bool = False,
        timeout: Optional[int] = None,
    ) -> Dict[str, Any]:
        sess = self._http.session
        if sess is None:
            raise NetworkException("HTTP 会话尚未初始化")

        headers: Dict[str, str] = {}
        if use_token and self._api_token:
            headers["Authorization"] = f"Bearer {self._api_token}"

        try:
            async with sess.get(
                url,
                params=params,
                headers=headers,
                timeout=timeout or self._http.timeout,
                allow_redirects=True,
                ssl=verify_ssl,
            ) as resp:
                if resp.status != 200:
                    raise ApiResponseException(
                        f"da.vtcm.link 返回非 200: status={resp.status}"
                    )
                return await resp.json()
        except (NetworkException, ApiResponseException):
            raise
        except aiohttp.ClientError as exc:
            raise NetworkException(f"da.vtcm.link 网络异常: {exc}") from exc
        except asyncio.TimeoutError as exc:
            raise NetworkException("da.vtcm.link 请求超时") from exc

    # ------------------------------------------------------------------ #
    # 玩家里程 (里程 / 排名)
    # ------------------------------------------------------------------ #
    async def get_player_stats(self, tmp_id: str) -> Dict[str, Any]:
        """获取玩家总里程 / 今日里程 / 头像 / 排名等数据。"""
        url = f"{self.BASE_URL}/player/info"
        data = await self._get_json(url, params={"tmpId": tmp_id})
        resp_data = data.get("data") or {}
        return {
            "total_km": _to_km_2f(resp_data.get("mileage")),
            "daily_km": _to_km_2f(resp_data.get("todayMileage")),
            "avatar_url": resp_data.get("avatarUrl", ""),
            "last_online": (
                resp_data.get("lastOnline")
                or resp_data.get("lastOnlineTime")
                or resp_data.get("last_login")
                or resp_data.get("lastLogin")
            ),
            "vtcRole": resp_data.get("vtcRole") or resp_data.get("vtc_role"),
            "total_rank": _to_int_rank(
                resp_data.get("mileageRank")
                or resp_data.get("totalMileageRank")
                or resp_data.get("mileage_rank")
                or resp_data.get("total_rank")
            ),
            "daily_rank": _to_int_rank(
                resp_data.get("todayMileageRank")
                or resp_data.get("todayRank")
                or resp_data.get("today_mileage_rank")
                or resp_data.get("today_rank")
            ),
            "raw_code": data.get("code"),
            "raw_msg": data.get("msg"),
        }

    # ------------------------------------------------------------------ #
    # 排行榜
    # ------------------------------------------------------------------ #
    async def get_mileage_ranking(
        self, ranking_type: str = "total", limit: int = 10
    ) -> List[Dict[str, Any]]:
        """获取总里程 / 今日里程排行榜。"""
        type_code = 2 if str(ranking_type).lower() in ("today", "daily", "2") else 1
        url = f"{self.BASE_URL}/statistics/mileageRankingList"
        data = await self._get_json(
            url,
            params={"rankingType": type_code, "rankingCount": limit},
        )
        result = data.get("data")
        return result if isinstance(result, list) else []

    # ------------------------------------------------------------------ #
    # DLC
    # ------------------------------------------------------------------ #
    async def get_dlc_list(self, dlc_type: int = 1) -> List[Dict[str, Any]]:
        url = f"{self.BASE_URL}/dlc/list"
        data = await self._get_json(url, params={"type": dlc_type})
        items = data.get("data")
        return items if isinstance(items, list) else []

    # ------------------------------------------------------------------ #
    # 足迹
    # ------------------------------------------------------------------ #
    async def get_player_history(
        self,
        tmp_id: str,
        start_time: str,
        end_time: str,
        server_id: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        params: Dict[str, Any] = {
            "tmpId": str(tmp_id).strip(),
            "startTime": str(start_time).strip(),
            "endTime": str(end_time).strip(),
        }
        if server_id:
            params["serverId"] = str(server_id)
        url = f"{self.BASE_URL}/map/playerHistory"
        data = await self._get_json(url, params=params)
        items = data.get("data")
        return items if isinstance(items, list) else []

    # ------------------------------------------------------------------ #
    # 周边玩家列表（仅定位命令使用）
    # ------------------------------------------------------------------ #
    async def get_area_players(
        self,
        server_id: Any,
        a_axis_x: float,
        a_axis_y: float,
        b_axis_x: float,
        b_axis_y: float,
    ) -> List[Dict[str, Any]]:
        url = f"{self.BASE_URL}/map/playerList"
        params = {
            "aAxisX": a_axis_x,
            "aAxisY": a_axis_y,
            "bAxisX": b_axis_x,
            "bAxisY": b_axis_y,
            "serverId": server_id,
        }
        try:
            data = await self._get_json(url, params=params)
        except (NetworkException, ApiResponseException):
            return []
        items = data.get("data")
        return items if isinstance(items, list) else []

    # ------------------------------------------------------------------ #
    # 历史车队
    # ------------------------------------------------------------------ #
    async def get_vtc_history(self, tmp_id: str) -> List[Dict[str, Any]]:
        """读取玩家的历史车队列表。"""
        url = f"{self.BASE_URL}/vtc/history"
        data = await self._get_json(url, params={"tmpId": tmp_id})
        items = data.get("data")
        return items if isinstance(items, list) else []

    # ------------------------------------------------------------------ #
    # 服务器版本（直接对接 api.truckersmp.com）
    # ------------------------------------------------------------------ #
    async def get_plugin_version(self) -> Dict[str, Any]:
        """拉取官方服务器插件版本（直接拉 ``api.truckersmp.com/v2/version``）。"""
        url = "https://api.truckersmp.com/v2/version"
        sess = self._http.session
        if sess is None:
            return {}
        try:
            async with sess.get(url, timeout=10) as resp:
                if resp.status != 200:
                    return {}
                data = await resp.json()
                return data if isinstance(data, dict) else {}
        except Exception:
            return {}

    async def get_official_servers(self) -> List[Dict[str, Any]]:
        """拉取官方服务器列表（直接拉 ``api.truckersmp.com/v2/servers``）。"""
        url = "https://api.truckersmp.com/v2/servers"
        sess = self._http.session
        if sess is None:
            return []
        try:
            async with sess.get(url, timeout=10) as resp:
                if resp.status != 200:
                    return []
                data = await resp.json()
                if not isinstance(data, dict):
                    return []
                code = data.get("code")
                if code is not None and int(code) != 200:
                    return []
                for key in ("data", "response", "result"):
                    arr = data.get(key)
                    if isinstance(arr, list):
                        return arr
                return []
        except Exception:
            return []


__all__ = ["VtcmClient"]
