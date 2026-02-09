"""
解释器包
=======

"道"语言的树遍历解释器，按职责拆分为：
- core        : 核心 Interpreter 类 —— 初始化、执行入口、辅助方法
- statements  : 语句执行混入 —— 所有 exec_* 方法
- expressions : 表达式求值混入 —— 所有 eval_* 方法
"""

from .core import Interpreter

__all__ = ['Interpreter']
