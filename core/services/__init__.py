"""core.services

业务层服务：
    - config_service       : 读取插件配置（基于配置字典的统一入口）
    - binding_service      : 维护"QQ -> TMP ID"绑定，持久化到 JSON
    - translation_service  : 包装百度翻译
    - location_service     : 国家/城市/位置翻译 & 加载 city markdown 表
    - player_service       : 玩家信息聚合
    - ranking_service      : 排行榜数据 + "我"的卡片数据
    - dlc_service          : 地图 DLC 数据
    - traffic_service      : 实时路况数据
    - server_service       : 官方服务器状态
    - footprint_service    : 玩家足迹业务
    - helpers              : 工具函数 (normalize_avatar_url 等)
"""

from .config_service import ConfigService
from .binding_service import BindingService
from .translation_service import TranslationService
from .location_service import LocationService
from .player_service import PlayerService
from .ranking_service import RankingService
from .dlc_service import DlcService
from .traffic_service import TrafficService
from .server_service import ServerService
from .footprint_service import FootprintService
from . import helpers

# 暴露 VtcmClient 是为了兼容旧的导入方式
# `from data.plugins.astrbot_plugin_tmp_bot.core.services import VtcmClient`，
# 历史上 services 曾经在内部使用 vtcm_client。现在 VtcmClient 已经迁到
# `core.api`，但仍以"转发"形式从 services 导出，避免破坏 AstrBot 插件加载
# 器对包符号表的扫描行为。
from ..api import VtcmClient  # noqa: E402,F401

__all__ = [
    "ConfigService",
    "BindingService",
    "TranslationService",
    "LocationService",
    "PlayerService",
    "RankingService",
    "DlcService",
    "TrafficService",
    "ServerService",
    "FootprintService",
    "helpers",
    "VtcmClient",
]
