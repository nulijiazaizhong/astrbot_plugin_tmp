"""core.services.translation_service

对百度翻译客户端的封装，向上提供 ``translate(text)`` 接口。
会根据配置决定是否真正调用远端服务。
"""

from __future__ import annotations

from typing import Optional

from ..api import BaiduTranslateClient
from .config_service import ConfigService


class TranslationService:
    """百度翻译包装服务。

    - ``enabled`` 表示配置中开启 + 已配置凭据
    - ``translate`` 始终返回字符串；关闭或失败时回退原文。
    """

    def __init__(
        self,
        client: BaiduTranslateClient,
        config: ConfigService,
    ) -> None:
        self._client = client
        self._config = config

    @property
    def enabled(self) -> bool:
        return (
            self._config.get_bool("baidu_translate_enable", True)
            and self._client.enabled
        )

    @property
    def cache_enabled(self) -> bool:
        return self._config.get_bool("baidu_translate_cache_enable", False)

    def configure(self) -> None:
        """重新读取配置以更新内部客户端。"""
        self._client.configure(
            self._config.get_str("baidu_translate_app_id", ""),
            self._config.get_str("baidu_translate_key", ""),
        )

    async def translate(self, text: Optional[str]) -> str:
        if not self.enabled:
            return text or ""
        try:
            return await self._client.translate(text or "", use_cache=self.cache_enabled)
        except Exception:
            return text or ""


__all__ = ["TranslationService"]
