"""core.utils.exceptions

集中管理插件内部使用的异常类型。其它层抛出具体异常
由 ``commands/`` 层捕获并翻译成用户可读消息。
"""

from __future__ import annotations


class TmpApiException(Exception):
    """TMP 相关异常的基类。"""


class PlayerNotFoundException(TmpApiException):
    """玩家不存在异常。"""


class SteamIdNotFoundException(TmpApiException):
    """Steam ID 未绑定 TMP 账号异常。"""


class NetworkException(TmpApiException):
    """网络请求异常。"""


class ApiResponseException(TmpApiException):
    """API 响应解析异常。"""


class ServiceUnavailableException(TmpApiException):
    """依赖服务不可用异常。"""


__all__ = [
    "TmpApiException",
    "PlayerNotFoundException",
    "SteamIdNotFoundException",
    "NetworkException",
    "ApiResponseException",
    "ServiceUnavailableException",
]
