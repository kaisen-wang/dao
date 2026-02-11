"""
内置函数与核心类型包
==================

"道"语言的内置函数和面向对象核心类型定义。
按功能拆分为：
- callables  : 可调用对象体系（DaoCallable, BuiltinFunction, DaoFunction 等）
- oop_types  : 面向对象核心类型（DaoClass, DaoInstance, BoundMethod, SuperProxy）
- functions  : 基础内置函数（打印、长度、取类型 等）
- hof        : 高阶内置函数（映射、筛选、折叠 等）
"""

from .callables import (
    DaoCallable,
    BuiltinFunction,
    InterpreterBuiltin,
    DaoFunction,
    CurriedFunction,
)
from .oop_types import (
    DaoClass,
    DaoInstance,
    BoundMethod,
    SuperProxy,
    DaoGenerator,
    DaoTrait,
)
from .functions import get_builtins
from .hof import get_interpreter_builtins

__all__ = [
    "DaoCallable",
    "BuiltinFunction",
    "InterpreterBuiltin",
    "DaoFunction",
    "CurriedFunction",
    "DaoClass",
    "DaoInstance",
    "BoundMethod",
    "SuperProxy",
    "DaoGenerator",
    "DaoTrait",
    "get_builtins",
    "get_interpreter_builtins",
]
