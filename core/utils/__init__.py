"""core.utils

通用工具集合：
    - constants   : 地区映射、用户组映射等常量字典
    - time_utils  : 时间戳格式化、时区转换
    - text_utils  : 文本清洗、HTML 字符处理、CJK 检测
    - translate   : 百度翻译客户端（封装在 api.translate 中）
"""

from .constants import (
    USER_GROUP_MAP,
    COUNTRY_MAP_EN_TO_CN,
    CITY_MAP_EN_TO_CN,
    LOCATION_FIX_MAP,
    PROMODS_SERVER_IDS,
)
from .time_utils import (
    format_timestamp_to_readable,
    format_timestamp_to_beijing,
)
from .text_utils import cleanup_cn_location_text, has_cjk, translate_user_groups

__all__ = [
    "USER_GROUP_MAP",
    "COUNTRY_MAP_EN_TO_CN",
    "CITY_MAP_EN_TO_CN",
    "LOCATION_FIX_MAP",
    "PROMODS_SERVER_IDS",
    "format_timestamp_to_readable",
    "format_timestamp_to_beijing",
    "cleanup_cn_location_text",
    "has_cjk",
    "translate_user_groups",
]
