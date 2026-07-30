"""百度翻译通用 API 客户端。

提供 ``translate(text)`` 方法带可选的内存缓存，避免重复消耗
每日配额。调用方一般通过 ``TranslationService`` 间接使用。
"""

from __future__ import annotations

import asyncio
import hashlib
import random
from typing import Dict, Optional

import aiohttp

from ..utils.exceptions import NetworkException
from .http_session import HttpSessionManager


class BaiduTranslateClient:
    """百度翻译通用 API 客户端。

    Args:
        http: 共享 HTTP 会话。
        app_id: 百度翻译 AppID，留空表示禁用。
        app_key: 百度翻译 密钥。
        cache: 进程内缓存实例（可选）。
    """

    ENDPOINT = "https://fanyi-api.baidu.com/api/trans/vip/translate"

    def __init__(
        self,
        http: HttpSessionManager,
        app_id: str = "",
        app_key: str = "",
        cache: Optional[Dict[str, str]] = None,
    ) -> None:
        self._http = http
        self._app_id = (app_id or "").strip()
        self._app_key = (app_key or "").strip()
        self._cache = cache if cache is not None else {}

    @property
    def enabled(self) -> bool:
        """是否提供了完整凭据。"""
        return bool(self._app_id and self._app_key)

    def configure(self, app_id: str, app_key: str) -> None:
        """更新凭据。"""
        self._app_id = (app_id or "").strip()
        self._app_key = (app_key or "").strip()

    async def translate(self, text: str, *, use_cache: bool = True) -> str:
        """翻译 ``text``，如未启用或失败则回退原文本。"""
        s = (text or "").strip()
        if not s:
            return text or ""
        if not self.enabled:
            return text or ""
        cache_key = hashlib.md5(s.encode("utf-8")).hexdigest()
        if use_cache and cache_key in self._cache:
            return self._cache[cache_key]

        salt = str(random.randint(1000, 9999))
        sign = hashlib.md5(
            (self._app_id + s + salt + self._app_key).encode("utf-8")
        ).hexdigest()
        params = {
            "q": s,
            "from": "auto",
            "to": "zh",
            "appid": self._app_id,
            "salt": salt,
            "sign": sign,
        }

        sess = self._http.session
        if sess is None:
            return text or ""

        try:
            async with sess.get(
                self.ENDPOINT, params=params, timeout=self._http.timeout
            ) as resp:
                if resp.status != 200:
                    return text or ""
                data = await resp.json()
                results = data.get("trans_result") if isinstance(data, dict) else None
                if isinstance(results, list) and results:
                    dst = results[0].get("dst")
                    if isinstance(dst, str) and dst.strip():
                        translated = dst.strip()
                        if use_cache:
                            self._cache[cache_key] = translated
                        return translated
        except (aiohttp.ClientError, asyncio.TimeoutError) as exc:
            raise NetworkException(f"百度翻译网络异常: {exc}") from exc
        return text or ""


__all__ = ["BaiduTranslateClient"]
