"""
道语言调试器基础层
=================

提供不可侵入的断点、单步观察与变量查看能力。

用法示例：
    from dao.debug import Debugger, DebugExecutor

    调试器 = Debugger()
    调试器.设置断点("", 2)
    执行器 = DebugExecutor(调试器, 文件名="示例.道")
    执行器.execute(ast, source=源码)
    调试器.查看变量("a")
"""

from .debugger import (
    DebugExecutor,
    Debugger,
    调试暂停,
    调试指令,
    断点,
    暂停事件,
)

__all__ = [
    "Debugger",
    "DebugExecutor",
    "断点",
    "暂停事件",
    "调试指令",
    "调试暂停",
]
