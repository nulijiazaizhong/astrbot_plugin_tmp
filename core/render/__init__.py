"""core.render

负责 AstrBot ``html_render`` / ``text_to_image`` 的封装与共享 HTML 模板。
所有命令的图文渲染统一通过 ``HtmlRenderService`` 调用，便于在
插件主体替换渲染引擎时只改一处。
"""

from .render_service import HtmlRenderService, PlainRenderer
from .templates import (
    DLC_LIST_TEMPLATE,
    RANK_TEMPLATE,
    LOCATE_MAP_TEMPLATE,
    FOOTPRINT_MAP_TEMPLATE,
    DEFAULT_TILE_ETS,
    DEFAULT_TILE_PROMODS,
    LEAFLET_CSS_URL,
    LEAFLET_JS_URL,
)

__all__ = [
    "HtmlRenderService",
    "PlainRenderer",
    "DLC_LIST_TEMPLATE",
    "RANK_TEMPLATE",
    "LOCATE_MAP_TEMPLATE",
    "FOOTPRINT_MAP_TEMPLATE",
    "DEFAULT_TILE_ETS",
    "DEFAULT_TILE_PROMODS",
    "LEAFLET_CSS_URL",
    "LEAFLET_JS_URL",
]
