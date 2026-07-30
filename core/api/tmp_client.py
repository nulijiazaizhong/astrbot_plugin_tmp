"""TruckersMP 官方 V2 API 客户端。

仅负责"取得数据 + 抛出异常"两个职责，业务格式化在服务层。
"""

from __future__ import annotations

import asyncio
from typing import Any, Dict, List, Optional

import aiohttp

from ..utils.exceptions import (
    ApiResponseException,
    NetworkException,
    PlayerNotFoundException,
    SteamIdNotFoundException,
)
from .http_session import HttpSessionManager


class TmpClient:
    """TruckersMP V2 API 客户端。

    端点参考：https://truckersmp.com/developers/api
    """

    BASE_URL = "https://api.truckersmp.com/v2"

    def __init__(self, http: HttpSessionManager) -> None:
        self._http = http

    # ------------------------------------------------------------------ #
    # Player
    # ------------------------------------------------------------------ #
    async def get_player(self, tmp_id: str) -> Dict[str, Any]:
        """根据 TMP ID 读取玩家信息。"""
        sess = self._require_session()
        url = f"{self.BASE_URL}/player/{tmp_id}"
        try:
            async with sess.get(url, timeout=10) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    payload = data.get("response")
                    if payload and isinstance(payload, dict):
                        return payload
                    raise PlayerNotFoundException(f"玩家 {tmp_id} 不存在")
                if resp.status == 404:
                    raise PlayerNotFoundException(f"玩家 {tmp_id} 不存在")
                raise ApiResponseException(f"API 返回错误状态码: {resp.status}")
        except (PlayerNotFoundException, ApiResponseException):
            raise
        except aiohttp.ClientError as exc:
            raise NetworkException(f"TruckersMP API 网络请求失败: {exc}") from exc
        except asyncio.TimeoutError as exc:
            raise NetworkException("请求 TruckersMP API 超时") from exc

    async def get_player_by_steam_id(self, steam_id: str) -> str:
        """根据 SteamID64 查询并返回 TMP ID。

        Raises:
            SteamIdNotFoundException: 当 SteamID 未绑定 TMP 账号时。
        """
        sess = self._require_session()
        url = f"{self.BASE_URL}/player/{steam_id}"
        try:
            async with sess.get(url, timeout=10) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    if data.get("error") is False and data.get("response"):
                        tmp_id = data["response"].get("id")
                        if tmp_id:
                            return str(tmp_id)
                        raise SteamIdNotFoundException(
                            f"Steam ID {steam_id} 未在 TruckersMP 中注册。"
                        )
                    err = (data.get("descriptor") or "").lower()
                    if "not found" in err or "unable to find" in err:
                        raise SteamIdNotFoundException(
                            f"Steam ID {steam_id} 未在 TruckersMP 中注册。"
                        )
                    raise ApiResponseException(f"API 返回错误: {data.get('descriptor', '未知错误')}")
                if resp.status == 404:
                    raise SteamIdNotFoundException(
                        f"Steam ID {steam_id} 未在 TruckersMP 中注册。"
                    )
                raise ApiResponseException(f"API 返回错误状态码: {resp.status}")
        except (SteamIdNotFoundException, ApiResponseException):
            raise
        except aiohttp.ClientError:
            raise SteamIdNotFoundException("Steam ID 查询服务网络请求失败") from None
        except asyncio.TimeoutError:
            raise SteamIdNotFoundException("请求 Steam ID 查询服务超时") from None

    async def get_player_bans(self, tmp_id: str) -> List[Dict[str, Any]]:
        """获取玩家封禁列表。"""
        sess = self._require_session()
        url = f"{self.BASE_URL}/bans/{tmp_id}"
        try:
            async with sess.get(url, timeout=10) as resp:
                if resp.status != 200:
                    return []
                data = await resp.json()
                bans = data.get("response") or data.get("data") or []
                return bans if isinstance(bans, list) else []
        except Exception:
            return []

    async def get_servers(self) -> List[Dict[str, Any]]:
        """获取官方服务器列表。"""
        sess = self._require_session()
        url = f"{self.BASE_URL}/servers"
        try:
            async with sess.get(url, timeout=self._http.timeout) as resp:
                if resp.status != 200:
                    return []
                data = await resp.json()
                servers = data.get("response") if isinstance(data, dict) else None
                return servers if isinstance(servers, list) else []
        except Exception:
            return []

    # ------------------------------------------------------------------ #
    # 工具
    # ------------------------------------------------------------------ #
    def _require_session(self) -> aiohttp.ClientSession:
        sess = self._http.session
        if sess is None:
            raise NetworkException("插件 HTTP 会话尚未初始化")
        return sess


__all__ = ["TmpClient"]
