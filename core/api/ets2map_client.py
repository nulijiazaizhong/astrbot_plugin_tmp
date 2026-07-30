"""ets2map.com 客户端。

用于：
    - 周期抓取 ``/v3/fullmap`` 的瓦片 URL 模板列表与在线玩家。
    - 通过缓存降低接口压力。
"""

from __future__ import annotations

import asyncio
import time
from typing import Any, Dict, List, Optional

import aiohttp

from ..utils.exceptions import NetworkException
from .http_session import HttpSessionManager


class Ets2MapClient:
    BASE_URL = "https://tracker.ets2map.com"

    def __init__(self, http: HttpSessionManager, interval_seconds: int = 60) -> None:
        self._http = http
        self._interval = max(60, int(interval_seconds or 60))
        self._cache: Optional[Dict[str, Any]] = None
        self._cache_ts: float = 0.0
        self._last_fetch_ts: float = 0.0
        self._next_fetch_ts: float = 0.0
        self._fetch_lock = asyncio.Lock()

    # ------------------------------------------------------------------ #
    # fullmap cache
    # ------------------------------------------------------------------ #
    @property
    def cache(self) -> Optional[Dict[str, Any]]:
        return self._cache

    @property
    def interval(self) -> int:
        return self._interval

    async def start_periodic_refresh(self) -> Optional[asyncio.Task]:
        """启动定期刷新 fullmap 的后台任务。返回创建的 ``asyncio.Task``，便于上层取消。"""
        # 首次延迟一个 interval，避免插件启动即高频拉取
        await asyncio.sleep(self._interval)
        while True:
            await self.fetch_fullmap()
            await asyncio.sleep(self._interval)

    async def fetch_fullmap(self) -> None:
        """主动拉取一次 fullmap。"""
        sess = self._http.session
        if sess is None:
            return
        async with self._fetch_lock:
            now_wall = time.time()
            if now_wall - self._last_fetch_ts < self._interval and self._cache:
                return
            now_mono = asyncio.get_event_loop().time() if hasattr(asyncio, "get_event_loop") else time.monotonic()
            if now_mono < self._next_fetch_ts and self._cache:
                return
            self._next_fetch_ts = now_mono + self._interval
            self._last_fetch_ts = now_wall

        url = f"{self.BASE_URL}/v3/fullmap"
        try:
            async with sess.get(url, timeout=self._http.timeout) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    if isinstance(data, dict):
                        self._cache = data
                        self._cache_ts = time.time()
                        return
        except (aiohttp.ClientError, asyncio.TimeoutError):
            return
        except Exception:
            return

    # ------------------------------------------------------------------ #
    # 解析工具
    # ------------------------------------------------------------------ #
    def find_tile_url(self, map_type: str = "ets") -> Optional[str]:
        """在 fullmap 缓存中查找匹配指定游戏类型的瓦片 URL 模板。"""
        data = self._cache or {}
        candidates: List[str] = []

        def walk(v: Any) -> None:
            if isinstance(v, dict):
                for val in v.values():
                    walk(val)
                return
            if isinstance(v, list):
                for val in v:
                    walk(val)
                return
            if isinstance(v, str):
                s = v.strip()
                if s.startswith("http") and "{z}" in s and "{x}" in s and "{y}" in s:
                    candidates.append(s)

        if isinstance(data, dict):
            inner = data.get("Data") or data.get("data")
            if inner is not None:
                walk(inner)
            walk(data)
        else:
            walk(data)

        # 去重保持顺序
        seen, uniq = set(), []
        for c in candidates:
            if c in seen:
                continue
            seen.add(c)
            uniq.append(c)
        candidates = uniq

        if not candidates:
            return None
        if map_type == "promods":
            for c in candidates:
                if "promods" in c.lower():
                    return c
        for c in candidates:
            lc = c.lower()
            if "ets" in lc and "promods" not in lc:
                return c
        return candidates[0]

    def find_player(self, tmp_id: str) -> Optional[Dict[str, Any]]:
        """从 fullmap 缓存里查找指定 TMP ID 的玩家数据。"""
        data = self._cache or {}
        payload = None
        if isinstance(data, dict):
            payload = data.get("Data") or data.get("data") or data.get("players")
        if not isinstance(payload, list):
            return None
        target = str(tmp_id)
        for p in payload:
            if not isinstance(p, dict):
                continue
            mp_id = p.get("MpId") or p.get("mp_id") or p.get("tmpId") or p.get("tmp_id")
            if mp_id is None:
                continue
            if str(mp_id) == target:
                return p
        return None


__all__ = ["Ets2MapClient"]
