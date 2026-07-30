"""core.services.dlc_service

地图 DLC 数据业务。
"""

from __future__ import annotations

from typing import Any, Dict, List

from ..api import VtcmClient
from ..utils.exceptions import ApiResponseException, NetworkException


class DlcService:
    """DLC 业务。"""

    def __init__(self, vtcm: VtcmClient) -> None:
        self._vtcm = vtcm

    async def list(self, dlc_type: int = 1) -> List[Dict[str, Any]]:
        try:
            return await self._vtcm.get_dlc_list(dlc_type)
        except (ApiResponseException, NetworkException):
            return []


__all__ = ["DlcService"]
