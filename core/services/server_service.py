"""core.services.server_service

TruckersMP 官方服务器业务。
"""

from __future__ import annotations

from typing import Any, Dict, List

from ..api import TmpClient
from ..utils.exceptions import NetworkException


class ServerService:
    """服务器状态业务。"""

    def __init__(self, tmp: TmpClient) -> None:
        self._tmp = tmp

    async def list(self) -> List[Dict[str, Any]]:
        try:
            return await self._tmp.get_servers()
        except NetworkException:
            return []


__all__ = ["ServerService"]
