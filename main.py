"""astrbot_plugin_tmp_bot.main

插件主入口（AstrBot Star 派生类）。

职责：
    - 构造 / 销毁 HTTP 会话 + 后台 fullmap 周期任务
    - 通过 :class:`core.commands.CommandRegistry` 暴露命令与消息分发器
    - ``on_load`` 时把自身 binding 到 ``HtmlRenderService``
"""

from __future__ import annotations

import asyncio
import os
from typing import Any, AsyncGenerator, Optional

from astrbot.api.event import filter, AstrMessageEvent
from astrbot.api.message_components import Plain
from astrbot.api.star import Context, Star, register
from astrbot.api import logger

from .core.api import (
    BaiduTranslateClient,
    Ets2MapClient,
    HttpSessionManager,
    TmpClient,
    TruckyClient,
    VtcmClient,
)
from .core.commands import CommandRegistry, TmpCommandContext
from .core.render import HtmlRenderService
from .core.services import (
    BindingService,
    ConfigService,
    DlcService,
    FootprintService,
    LocationService,
    PlayerService,
    RankingService,
    ServerService,
    TrafficService,
    TranslationService,
)


@register(
    "astrbot_plugin_tmp_bot",
    "BGYdook, 晚安（Goodnight_An）",
    "TMP 查询 Bot (欧卡2/美卡) 重构版",
    "2.0.0",
    "https://github.com/BGYdook/astrbot-plugin-tmp-bot",
)
class TmpBotPlugin(Star):
    """重构后的 AstrBot 插件主类。"""

    def __init__(self, context: Context, config: Optional[dict] = None) -> None:
        super().__init__(context)
        self.config_service = ConfigService(config or {})
        self._configure_dependencies()
        self._fullmap_task: Optional[asyncio.Task] = None
        logger.info("astrbot_plugin_tmp_bot v2.0.0 已实例化")

    # ----------------------------------------------------------------- #
    # 内部装配
    # ----------------------------------------------------------------- #
    def _configure_dependencies(self) -> None:
        cfg = self.config_service

        timeout = cfg.get_int("api_timeout_seconds", 10)
        self.http = HttpSessionManager(timeout=timeout)

        # API 客户端
        self.tmp_client = TmpClient(self.http)
        self.trucky_client = TruckyClient(self.http)
        self.vtcm_client = VtcmClient(
            self.http,
            base_url=cfg.get_str("vtcm_base_url", ""),
            open_url=cfg.get_str("vtcm_open_url", ""),
        )
        self.ets2map_client = Ets2MapClient(
            self.http,
            interval_seconds=cfg.get_int("ets2map_fullmap_interval_seconds", 60),
        )

        translate_cache: dict[str, str] = {}
        self.baidu_client = BaiduTranslateClient(
            self.http,
            app_id=cfg.get_str("baidu_translate_app_id", ""),
            app_key=cfg.get_str("baidu_translate_key", ""),
            cache=translate_cache,
        )
        self.translation = TranslationService(self.baidu_client, cfg)

        bind_path = self._resolve_bind_path()
        self.binding = BindingService(file_path=bind_path)

        cities_dir = self._resolve_cities_dir()
        self.location_service = LocationService(
            self.translation, cities_dir=cities_dir
        )

        self.player_service = PlayerService(
            self.tmp_client,
            self.trucky_client,
            self.vtcm_client,
            self.location_service,
        )
        self.ranking_service = RankingService(self.vtcm_client)
        self.dlc_service = DlcService(self.vtcm_client)
        self.traffic_service = TrafficService(
            self.trucky_client, self.location_service
        )
        self.server_service = ServerService(self.tmp_client)
        self.footprint_service = FootprintService(self.vtcm_client)

        # 渲染层
        self.render_service = HtmlRenderService()

        ctx = TmpCommandContext(
            config=cfg,
            http=self.http,
            translate=self.translation,
            baidu_client=self.baidu_client,
            binding=self.binding,
            tmp_client=self.tmp_client,
            trucky_client=self.trucky_client,
            vtcm_client=self.vtcm_client,
            ets2map_client=self.ets2map_client,
            location=self.location_service,
            player=self.player_service,
            ranking=self.ranking_service,
            dlc=self.dlc_service,
            traffic=self.traffic_service,
            server=self.server_service,
            footprint_service=self.footprint_service,
            render=self.render_service,
        )
        self.registry = CommandRegistry(ctx)

    def _resolve_bind_path(self) -> str:
        try:
            from astrbot.api.star import StarTools
            data_dir = StarTools.get_data_dir("astrbot_plugin_tmp_bot")
            os.makedirs(data_dir, exist_ok=True)
            return os.path.join(data_dir, "tmp_bindings.json")
        except Exception:
            here = os.path.dirname(os.path.abspath(__file__))
            fallback = os.path.join(here, "data", "tmp_bindings.json")
            os.makedirs(os.path.dirname(fallback), exist_ok=True)
            return fallback

    def _resolve_cities_dir(self) -> Optional[str]:
        here = os.path.dirname(os.path.abspath(__file__))
        candidate = os.path.join(here, "TruckersMP-citties-name")
        return candidate if os.path.isdir(candidate) else None

    # ----------------------------------------------------------------- #
    # AstrBot 生命周期
    # ----------------------------------------------------------------- #
    async def on_load(self) -> None:
        logger.info("TMP Bot 插件启动中...")
        await self.http.start()
        # 把 Star 自身交给 render_service 以获得 html_render/text_to_image。
        self.render_service.bind_star(self)

        try:
            self._fullmap_task = asyncio.create_task(
                self.ets2map_client.start_periodic_refresh()
            )
        except Exception as exc:
            logger.warning(f"启动 fullmap 周期任务失败: {exc}")
            self._fullmap_task = None

        logger.info("TMP Bot 插件启动完成")

    async def on_unload(self) -> None:
        logger.info("TMP Bot 插件卸载中...")
        if self._fullmap_task and not self._fullmap_task.done():
            self._fullmap_task.cancel()
            try:
                await self._fullmap_task
            except (asyncio.CancelledError, Exception):
                pass
        await self.http.close()
        logger.info("TMP Bot 插件已卸载")

    # ----------------------------------------------------------------- #
    # 命令入口
    # ----------------------------------------------------------------- #
    @filter.command("绑定")
    async def bind_cmd(self, event: AstrMessageEvent) -> AsyncGenerator[Any, None]:
        async for r in self.registry.bind(event):
            yield r
        try:
            event.stop_event()
        except Exception:
            pass
        return

    @filter.command("解绑")
    async def unbind_cmd(self, event: AstrMessageEvent) -> AsyncGenerator[Any, None]:
        async for r in self.registry.unbind(event):
            yield r
        try:
            event.stop_event()
        except Exception:
            pass
        return

    @filter.command("查询")
    async def query_cmd(
        self, event: AstrMessageEvent, tmp_id: str | None = None
    ) -> AsyncGenerator[Any, None]:
        async for r in self.registry.cmd_query(event, tmp_id):
            yield r
        try:
            event.stop_event()
        except Exception:
            pass
        return

    @filter.command("查")
    async def query_alias_cmd(
        self, event: AstrMessageEvent, tmp_id: str | None = None
    ) -> AsyncGenerator[Any, None]:
        async for r in self.registry.cmd_query(event, tmp_id):
            yield r
        try:
            event.stop_event()
        except Exception:
            pass
        return

    @filter.command("定位")
    async def locate_cmd(
        self, event: AstrMessageEvent, tmp_id: str | None = None
    ) -> AsyncGenerator[Any, None]:
        async for r in self.registry.cmd_locate(event, tmp_id):
            yield r
        try:
            event.stop_event()
        except Exception:
            pass
        return

    @filter.command("路况")
    async def traffic_cmd(
        self, event: AstrMessageEvent, server: str | None = None
    ) -> AsyncGenerator[Any, None]:
        async for r in self.registry.cmd_traffic(event, server):
            yield r
        try:
            event.stop_event()
        except Exception:
            pass
        return

    @filter.command("总里程排行")
    async def rank_total_cmd(self, event: AstrMessageEvent) -> AsyncGenerator[Any, None]:
        async for r in self.registry.cmd_rank_total(event):
            yield r
        try:
            event.stop_event()
        except Exception:
            pass
        return

    @filter.command("今日里程排行")
    async def rank_today_cmd(self, event: AstrMessageEvent) -> AsyncGenerator[Any, None]:
        async for r in self.registry.cmd_rank_today(event):
            yield r
        try:
            event.stop_event()
        except Exception:
            pass
        return

    @filter.command("足迹")
    async def footprint_cmd(
        self,
        event: AstrMessageEvent,
        server: str | None = None,
        tmp_id: str | None = None,
    ) -> AsyncGenerator[Any, None]:
        async for r in self.registry.cmd_today_footprint(event, server, tmp_id):
            yield r
        try:
            event.stop_event()
        except Exception:
            pass
        return

    @filter.command("服务器")
    async def servers_cmd(self, event: AstrMessageEvent) -> AsyncGenerator[Any, None]:
        async for r in self.registry.cmd_servers(event):
            yield r
        try:
            event.stop_event()
        except Exception:
            pass
        return

    @filter.command("插件版本")
    async def version_cmd(self, event: AstrMessageEvent) -> AsyncGenerator[Any, None]:
        async for r in self.registry.cmd_plugin_version(event):
            yield r
        try:
            event.stop_event()
        except Exception:
            pass
        return

    @filter.command("菜单")
    async def help_cmd(self, event: AstrMessageEvent) -> AsyncGenerator[Any, None]:
        async for r in self.registry.cmd_help(event):
            yield r
        try:
            event.stop_event()
        except Exception:
            pass
        return

    @filter.command("帮助")
    async def help_alias_cmd(self, event: AstrMessageEvent) -> AsyncGenerator[Any, None]:
        async for r in self.registry.cmd_help(event):
            yield r
        try:
            event.stop_event()
        except Exception:
            pass
        return

    @filter.command("DLC列表")
    async def dlc_cmd(self, event: AstrMessageEvent) -> AsyncGenerator[Any, None]:
        async for r in self.registry.cmd_dlc_list(event):
            yield r
        try:
            event.stop_event()
        except Exception:
            pass
        return

    @filter.command("DLC")
    async def dlc_alias_cmd(self, event: AstrMessageEvent) -> AsyncGenerator[Any, None]:
        async for r in self.registry.cmd_dlc_list(event):
            yield r
        try:
            event.stop_event()
        except Exception:
            pass
        return

    @filter.command("地图DLC")
    async def dlc_map_cmd(self, event: AstrMessageEvent) -> AsyncGenerator[Any, None]:
        async for r in self.registry.cmd_dlc_list(event):
            yield r
        try:
            event.stop_event()
        except Exception:
            pass
        return

    @filter.command("历史车队")
    async def vtc_history_cmd(self, event: AstrMessageEvent) -> AsyncGenerator[Any, None]:
        async for r in self.registry.cmd_vtc_history(event):
            yield r
        try:
            event.stop_event()
        except Exception:
            pass
        return

    # 活动 / 活动列表 / 今日活动 / 信息 / 修改密码 / 成员管理 等 VTCM 车队平台功能
    # 已于 v2 中移除，命令由 `cmd_event_list` / `cmd_today_event` 等占位方法响应。

    # 注：v2 起不再使用 ``filter.event_message_type(ALL)`` 兜底，避免与
    # ``filter.command`` 双触发导致重复回复。无空格的紧凑写法（如 ``查123``）
    # AstrBot 路由器层不识别为 ``查询`` 命令，故不再单独接管；如有需要
    # 请在 AstrBot 配置中显式发送时加上空格，或为相关命令定义命令别名。


__all__ = ["TmpBotPlugin"]
