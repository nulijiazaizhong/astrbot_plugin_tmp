"""core.services.player_service

聚合玩家维度的查询：基本信息 + 封禁 + VTCM 里程 / 排名 + 在线状态
+ VTC 角色 + 历史车队 + Patreon 赞助字段抽取。

完整行为说明：
    - ``fetch_full_profile``：将 TMP / bans / VTCM stats / online status 合并返回。
    - ``fetch_vtc_member_role``：若玩家没有 ``vtc.role``，主动查询。
    - ``resolve_tmp_id``：把 SteamID64 也接受为输入。
    - ``fetch_vtc_history``：读取玩家历史车队列表。
"""

from __future__ import annotations

import asyncio
from typing import Any, Dict, List, Optional, Tuple

from ..api import TmpClient, TruckyClient, VtcmClient
from ..utils.exceptions import (
    ApiResponseException,
    NetworkException,
    PlayerNotFoundException,
    SteamIdNotFoundException,
)
from .helpers import (
    format_ban_info,
    get_steam_id_from_player_info,
    normalize_avatar_url,
    to_int,
)
from .location_service import LocationService


class PlayerService:
    """玩家业务服务。"""

    def __init__(
        self,
        tmp: TmpClient,
        trucky: TruckyClient,
        vtcm: VtcmClient,
        locations: LocationService,
    ) -> None:
        self._tmp = tmp
        self._trucky = trucky
        self._vtcm = vtcm
        self._locations = locations

    # ------------------------------------------------------------------ #
    # 基础信息
    # ------------------------------------------------------------------ #
    async def fetch_profile(self, tmp_id: str) -> Dict[str, Any]:
        """获取玩家基本信息（已并入 bans）。失败时抛出 ``PlayerNotFoundException``。"""
        info, bans = await asyncio.gather(
            self._safe_get_player(tmp_id),
            self._safe_get_bans(tmp_id),
        )
        if not info:
            raise PlayerNotFoundException(f"玩家 {tmp_id} 不存在")
        return {"info": info, "bans": bans or []}

    async def resolve_tmp_id(self, query: str) -> str:
        """根据 ``query``（TMP ID 或 SteamID64）返回 TMP ID。"""
        query = (query or "").strip()
        if not query:
            raise PlayerNotFoundException("查询参数为空")
        try:
            return await self._tmp.get_player_by_steam_id(query)
        except SteamIdNotFoundException as exc:
            try:
                info = await self._safe_get_player(query)
                if info:
                    return str(info.get("id") or query)
            except Exception:
                pass
            raise exc

    async def fetch_online_status(self, tmp_id: str) -> Dict[str, Any]:
        """获取在线状态 + 服务器 / 国家 / 城市翻译。"""
        try:
            data = await self._trucky.get_player_online(tmp_id)
        except (NetworkException, ApiResponseException) as exc:
            return {"online": False, "debug_error": str(exc)}
        if not data.get("online"):
            return data

        country_cn, city_cn = await self._locations.translate_country_city(
            data.get("country"),
            data.get("real_name"),
        )
        data["country_cn"] = country_cn
        data["city_cn"] = city_cn
        return data

    # ------------------------------------------------------------------ #
    # VTCM 扩展信息
    # ------------------------------------------------------------------ #
    async def fetch_vtcm_stats(self, tmp_id: str) -> Dict[str, Any]:
        """获取 VTCM 平台的里程/头像/排名等扩展信息。"""
        try:
            return await self._vtcm.get_player_stats(tmp_id)
        except (NetworkException, ApiResponseException) as exc:
            return {"error": str(exc)}

    async def fetch_full_profile(self, tmp_id: str) -> Dict[str, Any]:
        """合并 TMP + VTCM + 在线状态，给上层一次性渲染。"""
        profile_task = asyncio.create_task(self.fetch_profile(tmp_id))
        vtcm_task = asyncio.create_task(self.fetch_vtcm_stats(tmp_id))
        online_task = asyncio.create_task(self.fetch_online_status(tmp_id))

        profile, vtcm, online = await asyncio.gather(
            profile_task, vtcm_task, online_task, return_exceptions=True
        )

        if isinstance(profile, Exception):
            if isinstance(profile, PlayerNotFoundException):
                raise profile
            raise NetworkException(str(profile))
        if isinstance(profile, dict) and "error" in profile:
            raise NetworkException(profile["error"])  # type: ignore[index]

        info = profile.get("info", {}) if isinstance(profile, dict) else {}
        bans = profile.get("bans", []) if isinstance(profile, dict) else []

        # VTC role 兜底
        if isinstance(info, dict):
            vtc = info.get("vtc") if isinstance(info.get("vtc"), dict) else {}
            if vtc and not (vtc.get("role") or vtc.get("position")):
                try:
                    role = await self.fetch_vtc_member_role(tmp_id, vtc)
                    if role and isinstance(info, dict):
                        info.setdefault("vtc", {})["role"] = role
                except Exception:
                    pass

        ban_count, sorted_bans = format_ban_info(bans)

        return {
            "profile": info,
            "bans": list(bans),
            "ban_count": ban_count,
            "sorted_bans": sorted_bans,
            "vtcm": vtcm if isinstance(vtcm, dict) else {},
            "online": online if isinstance(online, dict) else {},
        }

    # ------------------------------------------------------------------ #
    # VTC 信息
    # ------------------------------------------------------------------ #
    async def fetch_vtc_member_role(
        self,
        tmp_id: str,
        vtc_info: Optional[Dict[str, Any]] = None,
    ) -> Optional[str]:
        """返回玩家在车队内的角色（'Owner'/'Member' 等）。"""
        if not isinstance(vtc_info, dict):
            vtc_info = {}
        try:
            # 复用历史车队接口，返回的 list 中包含玩家在该车队的角色信息
            history = await self._vtcm.get_vtc_history(tmp_id)
        except (NetworkException, ApiResponseException):
            return None
        if not isinstance(history, list):
            return None
        target_id = str(vtc_info.get("id") or vtc_info.get("vtcId") or "")
        for item in history:
            if not isinstance(item, dict):
                continue
            cur_vtc = str(
                item.get("vtcId") or item.get("vtc_id") or item.get("vtcTag") or ""
            )
            if target_id and cur_vtc and cur_vtc != target_id:
                continue
            role = (
                item.get("role")
                or item.get("position")
                or item.get("vtcRole")
                or item.get("vtc_role")
            )
            if role:
                return str(role)
        return None

    async def fetch_vtc_history(self, tmp_id: str) -> Optional[List[Dict[str, Any]]]:
        """按原 main.py 行为返回原始历史车队数据。"""
        try:
            return await self._vtcm.get_vtc_history(tmp_id)
        except (NetworkException, ApiResponseException) as exc:
            return None if "私密" in str(exc) else None

    # ------------------------------------------------------------------ #
    # 头像 / Steam
    # ------------------------------------------------------------------ #
    @staticmethod
    def normalize_avatar_url(url: Optional[str]) -> Optional[str]:
        return normalize_avatar_url(url)

    @staticmethod
    def get_steam_id(player_info: Dict[str, Any]) -> Optional[str]:
        return get_steam_id_from_player_info(player_info)

    @staticmethod
    def to_int(value: Any, default: int = 0) -> int:
        return to_int(value, default)

    # ------------------------------------------------------------------ #
    # 内部
    # ------------------------------------------------------------------ #
    async def _safe_get_player(self, tmp_id: str) -> Optional[Dict[str, Any]]:
        try:
            return await self._tmp.get_player(tmp_id)
        except PlayerNotFoundException:
            return None
        except (NetworkException, ApiResponseException) as exc:
            raise NetworkException(str(exc)) from exc

    async def _safe_get_bans(self, tmp_id: str) -> list[Dict[str, Any]]:
        try:
            return await self._tmp.get_player_bans(tmp_id)
        except Exception:
            return []


__all__ = ["PlayerService"]
