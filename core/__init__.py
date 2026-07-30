"""astrbot_plugin_tmp_bot.core

重构后的分层核心包：
    - core.api     : 各类外部 HTTP API 客户端
    - core.services: 业务层服务（玩家、绑定、排行、足迹等）
    - core.commands: AstrBot 命令注册与消息分发
    - core.utils   : 通用工具（时间格式化、文本清洗、常量等）
"""

__version__ = "2.0.0"
