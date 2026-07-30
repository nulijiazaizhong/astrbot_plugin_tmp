"""core.commands

AstrBot 命令集合与消息分发器。

模块导出 ``CommandRegistry``，由 ``main.py`` 实例化，调用
``registry.attach(plugin)`` 把所有 ``@filter.command`` 装饰的
方法挂到 AstrBot Star 对象上。
"""

from .registry import CommandRegistry, TmpCommandContext

__all__ = ["CommandRegistry", "TmpCommandContext"]
