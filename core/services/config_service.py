"""core.services.config_service

对配置字典的封装，集中处理类型转换与默认值。
"""

from __future__ import annotations

from typing import Any


class ConfigService:
    """统一访问 AstrBot 注入的 ``config`` 字典。"""

    def __init__(self, config: dict | None) -> None:
        self._config = config or {}

    def get_bool(self, key: str, default: bool = False) -> bool:
        v = self._config.get(key, default)
        return bool(v) if isinstance(v, (bool, int, str)) else default

    def get_int(self, key: str, default: int = 0) -> int:
        try:
            return int(self._config.get(key, default))
        except Exception:
            return default

    def get_str(self, key: str, default: str = "") -> str:
        v = self._config.get(key, default)
        return default if v is None else str(v)

    def raw(self) -> dict:
        return dict(self._config)


__all__ = ["ConfigService"]
