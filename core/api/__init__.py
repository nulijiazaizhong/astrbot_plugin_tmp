"""core.api

封装所有外部 HTTP API 调用：
    - tmp_client   : TruckersMP 官方 V2 API
    - vtcm_client  : VTCM 车队平台 API（含积分/活动/成员）
    - trucky_client: Trucky App v2/v3 API（实时在线、路况）
    - ets2map_client: ets2map.com 底图 fullmap
    - baidu_translate : 百度翻译通用 API
    - http_session : 异步 aiohttp 会话管理器
"""

from .http_session import HttpSessionManager
from .tmp_client import TmpClient
from .vtcm_client import VtcmClient
from .trucky_client import TruckyClient
from .ets2map_client import Ets2MapClient
from .baidu_translate import BaiduTranslateClient

__all__ = [
    "HttpSessionManager",
    "TmpClient",
    "VtcmClient",
    "TruckyClient",
    "Ets2MapClient",
    "BaiduTranslateClient",
]
