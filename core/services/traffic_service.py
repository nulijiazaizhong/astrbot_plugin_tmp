"""core.services.traffic_service

实时路况业务：拉取热门地点 + 名称翻译。
"""

from __future__ import annotations

from typing import Any, Dict, List

from ..api import TruckyClient
from ..utils.exceptions import ApiResponseException, NetworkException
from .location_service import LocationService


class TrafficService:
    """实时路况业务。"""

    def __init__(self, trucky: TruckyClient, locations: LocationService) -> None:
        self._trucky = trucky
        self._locations = locations

    async def top(self, server_key: str, *, with_translate: bool = True) -> List[Dict[str, Any]]:
        """获取服务器热门地点列表（已翻译地点名为 ``name_cn``）。"""
        try:
            items = await self._trucky.get_traffic_top(server_key)
        except (ApiResponseException, NetworkException):
            return []
        if not with_translate:
            return items

        translated: List[Dict[str, Any]] = []
        for item in items:
            name_en = item.get("name") if isinstance(item, dict) else ""
            name_cn = await self._locations.translate_traffic_name(str(name_en)) if name_en else ""
            if isinstance(item, dict):
                new_item = dict(item)
                new_item["name_cn"] = name_cn
                translated.append(new_item)
            else:
                translated.append(item)
        return translated


__all__ = ["TrafficService"]
