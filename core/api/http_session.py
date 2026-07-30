"""统一 HTTP 会话管理。

对外仅暴露 ``HttpSessionManager``，封装 aiohttp ``ClientSession``
的创建/关闭，使所有 API 客户端共享会话和连接池。

注意：AstrBot v4+ 在热重载时可能**跳过** ``on_load``，但仍
允许命令方法被调用；因此实现上保证：

    - ``session`` 属性访问时若未初始化则通过同步 IO 循环 lazy 创建；
    - 对 asyncio 环境仍然使用 ``aiohttp.ClientSession``，避免
      与 AstrBot 现有事件循环冲突。
    - ``start()`` / ``close()`` 仅作为兼容性接口保留。
"""

from __future__ import annotations

import socket
from typing import Optional

import aiohttp

from astrbot.api import logger


class HttpSessionManager:
    """异步 aiohttp 会话的轻量包装。"""

    DEFAULT_USER_AGENT = "astrBot-TMP-Plugin/2.0.0"

    def __init__(self, user_agent: Optional[str] = None, timeout: int = 10) -> None:
        self._user_agent = user_agent or self.DEFAULT_USER_AGENT
        self._timeout = timeout
        self._session: Optional[aiohttp.ClientSession] = None
        # 注：AstrBot v4+ 在热重载时可能跳过 on_load，
        # 因此 session 不再仅依赖 start() 显式初始化。

    @property
    def session(self) -> aiohttp.ClientSession:
        """延迟返回已初始化的 ``ClientSession``。

        若尚未初始化，**同步**创建一个临时 session（旧 aiohttp
        API 仍支持）以保证调用方立刻可用。
        """
        if self._session is not None and not self._session.closed:
            return self._session
        # 这里通常发生在 on_load 之前的早期命令阶段（如热重载），
        # 所以以"尽力提供"为原则同步构造。
        try:
            self._session = aiohttp.ClientSession(
                headers={"User-Agent": self._user_agent},
                timeout=aiohttp.ClientTimeout(total=self._timeout),
                trust_env=True,
            )
            logger.info(f"TMP HTTP 会话已按需懒创建: timeout={self._timeout}s")
            return self._session
        except Exception as exc:
            logger.error(f"TMP HTTP 会话懒创建失败: {exc}")
            raise

    @property
    def timeout(self) -> int:
        return self._timeout

    async def start(self) -> None:
        """异步会话启动（通常在 ``on_load`` 中调用）。"""
        if self._session is not None and not self._session.closed:
            return
        connector = aiohttp.TCPConnector(family=socket.AF_INET)
        self._session = aiohttp.ClientSession(
            headers={"User-Agent": self._user_agent},
            timeout=aiohttp.ClientTimeout(total=self._timeout),
            connector=connector,
            trust_env=True,
        )
        logger.info(f"TMP HTTP 会话已创建: timeout={self._timeout}s")

    async def close(self) -> None:
        """安全关闭当前会话。"""
        if self._session and not self._session.closed:
            try:
                await self._session.close()
            except Exception:
                pass
        self._session = None


__all__ = ["HttpSessionManager"]
