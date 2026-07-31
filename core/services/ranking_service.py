"""core.services.ranking_service

里程排行榜业务，统一提供"总里程 / 今日里程"。

补充 ``me_extra`` —— 当命令层希望渲染"我自己"卡片时使用：
    - 输入绑定关系的 ``tmp_id``
    - VTCM stats （含 total_km / daily_km / rank）
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

from ..api import VtcmClient
from ..utils.exceptions import (
    ApiResponseException,
    NetworkException,
    ServiceUnavailableException,
)


class RankingService:
    """里程排行榜业务。"""

    def __init__(self, vtcm: VtcmClient) -> None:
        self._vtcm = vtcm

    async def total(self, limit: int = 10) -> List[Dict[str, Any]]:
        return await self._safe_get("total", limit)

    async def today(self, limit: int = 10) -> List[Dict[str, Any]]:
        return await self._safe_get("today", limit)

    async def _safe_get(self, kind: str, limit: int) -> List[Dict[str, Any]]:
        try:
            return await self._vtcm.get_mileage_ranking(kind, limit)
        except (ApiResponseException, NetworkException, ServiceUnavailableException):
            return []

    @staticmethod
    def build_items(rank_list: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """将原始排行数据转换为 ``{rank, name, km, tmp_id}``。"""
        items: List[Dict[str, Any]] = []
        for idx, player in enumerate(rank_list):
            if not isinstance(player, dict):
                continue
            rank = player.get("ranking") or (idx + 1)
            raw_name = (
                player.get("tmpName")
                or player.get("name")
                or player.get("tmp_name")
                or player.get("nickName")
                or player.get("nickname")
            )
            name = str(raw_name).strip() if raw_name else ""
            if not name:
                name = "未知玩家"

            distance_m = player.get("mileage") or player.get("distance") or 0
            if isinstance(distance_m, (int, float)):
                distance_km = int(distance_m / 1000)
            else:
                distance_km = 0
            tmp_id = player.get("tmpId", "N/A")
            items.append(
                {
                    "rank": rank,
                    "name": name,
                    "km": distance_km,
                    "tmp_id": tmp_id,
                }
            )
        return items

    @staticmethod
    async def me_extra(
        *,
        kind: str,
        stats: Optional[Dict[str, Any]],
        display_name: str,
        bound_tmp_id: Optional[str],
    ) -> Optional[Dict[str, Any]]:
        """构造排行榜中"我"的卡片信息。"""
        if not bound_tmp_id:
            return None
        if not isinstance(stats, dict):
            return None
        key = "total_km" if kind == "total" else "daily_km"
        rank_key = "total_rank" if kind == "total" else "daily_rank"
        km = stats.get(key)
        if not isinstance(km, (int, float)):
            return None
        rank = stats.get(rank_key)
        vtc_role = stats.get("vtcRole")
        return {
            "name": (str(display_name).strip() if display_name else "") or "你",
            "tmp_id": str(bound_tmp_id),
            "rank": rank,
            "km": float(km),
            "vtc_role": (str(vtc_role).strip() if vtc_role else ""),
        }


__all__ = ["RankingService"]
