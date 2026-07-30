"""core.render.render_service

AstrBot ``html_render`` 与 ``text_to_image`` 的轻量封装。

设计要点：
    - 所有渲染经过单一服务类，便于上层（命令）统一调用与故障降级；
    - ``html_render`` 来自 AstrBot ``Star`` 主体；
    - 当 ``Star`` 不提供 ``html_render`` 时的兜底：通过 ``Image`` 模板渲染
      失败后会回到 ``PlainRenderer``（直接把文本转为 Plain）。
"""

from __future__ import annotations

from typing import Any, Awaitable, Callable, Dict, Optional, Protocol, Union


class _StarLike(Protocol):
    """仅暴露 html_render/text_to_image 的最小协议。"""

    async def html_render(
        self,
        tmpl: str,
        data: Dict[str, Any],
        *,
        options: Optional[Dict[str, Any]] = None,
    ) -> str: ...

    async def text_to_image(
        self,
        text: str,
        *,
        options: Optional[Dict[str, Any]] = None,
    ) -> Union[str, bytes, bytearray]: ...


# 接受底层 AstrBot 主体的最小 Protocol。
HtmlRenderFn = Callable[[str, Dict[str, Any]], Awaitable[str]]


class HtmlRenderService:
    """所有命令层使用的统一渲染入口。"""

    def __init__(self, star: Optional[_StarLike] = None) -> None:
        self._star = star

    def bind_star(self, star: _StarLike) -> None:
        """在 on_load 时绑定真正的 AstrBot 主体。"""
        self._star = star

    async def render_html(
        self,
        tmpl: str,
        data: Dict[str, Any],
        options: Optional[Dict[str, Any]] = None,
    ) -> Optional[str]:
        if self._star is None or not hasattr(self._star, "html_render"):
            return None
        try:
            result = await self._star.html_render(tmpl, data, options=options)
            if isinstance(result, str) and result:
                return result
        except Exception:
            return None
        return None

    async def render_text(
        self,
        text: str,
        options: Optional[Dict[str, Any]] = None,
    ) -> Optional[Union[str, bytes, bytearray]]:
        if self._star is None or not hasattr(self._star, "text_to_image"):
            return None
        try:
            result = await self._star.text_to_image(text, options=options)
            return result
        except Exception:
            return None


class PlainRenderer:
    """降级渲染器：仅返回文本组件，避免上层调用链使用嵌套条件。"""

    @staticmethod
    def fallback_text(text: str) -> str:
        return text


__all__ = ["HtmlRenderService", "PlainRenderer"]
