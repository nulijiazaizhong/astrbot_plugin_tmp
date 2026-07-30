"""core.commands.context

命令执行需要的全部依赖聚合：通过 ``TmpCommandContext`` 单点注入。

每个由 ``CommandRegistry`` 暴露的 AstrBot 命令都接收该对象，
业务逻辑通过它获取服务、http、配置等资源。
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from ..api import (
    BaiduTranslateClient,
    Ets2MapClient,
    HttpSessionManager,
    TmpClient,
    TruckyClient,
    VtcmClient,
)
from ..render import HtmlRenderService
from ..services import (
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


@dataclass
class TmpCommandContext:
    """命令执行上下文。"""

    config: ConfigService
    http: HttpSessionManager
    translate: TranslationService
    baidu_client: BaiduTranslateClient
    binding: BindingService
    tmp_client: TmpClient
    trucky_client: TruckyClient
    vtcm_client: VtcmClient
    ets2map_client: Ets2MapClient
    location: LocationService
    player: PlayerService
    ranking: RankingService
    dlc: DlcService
    traffic: TrafficService
    server: ServerService
    footprint_service: FootprintService
    render: HtmlRenderService


__all__ = ["TmpCommandContext"]
