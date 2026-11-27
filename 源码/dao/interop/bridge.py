"""
Python 互操作桥核心
==================

对外提供三个操作：列出白名单模块、载入模块句柄、通过句柄调用白名单函数。
所有入口都进行白名单校验与安全值转换，不提供任何任意代码执行能力。
"""

from typing import Any

from ..errors import 类型错误, 运行时错误
from .convert import 参数转Python, 结果转道
from .whitelist import (
    允许模块,
    允许的属性,
    列出模块名,
    规范模块名,
    需编码字符串参数模块,
)


class Python模块:
    """不透明的 Python 模块句柄。

    只有下划线开头的槽位，道语言的属性访问兜底逻辑会拒绝下划线成员，
    因此外部无法通过 ``模块.某属性`` 绕过 ``调用Python函数`` 直接取到
    Python 模块对象或其危险属性。
    """

    __slots__ = ("_模块", "_模块名")

    def __init__(self, 模块名: str, 模块: object):
        self._模块名 = 模块名
        self._模块 = 模块

    def __repr__(self) -> str:
        return f"<Python模块 {self._模块名}>"


def 列出可用模块() -> list[str]:
    """返回白名单中所有可加载的模块名（排序后的列表）。"""
    return 列出模块名()


def 载入模块(模块名: str) -> Python模块:
    """载入白名单内的模块并返回不透明句柄；否则抛中文运行时错误。"""
    if not isinstance(模块名, str):
        raise 类型错误(
            f"载入Python模块() 的模块名必须是文本，收到: {type(模块名).__name__}"
        )
    规范名 = 规范模块名(模块名)
    if 规范名 is None:
        raise 运行时错误(
            f"Python 模块 '{模块名}' 不在白名单中，禁止加载。"
            f"可用模块: {'、'.join(列出可用模块())}"
        )
    return Python模块(规范名, 允许模块[规范名])


def _适配参数(规范名: str, 参数: list, 命名参数: dict) -> tuple[list, dict]:
    """对 bytes 类 API 做有限的 UTF-8 编码适配。"""
    if 规范名 not in 需编码字符串参数模块:
        return 参数, 命名参数
    新参数 = [项.encode("utf-8") if isinstance(项, str) else 项 for 项 in 参数]
    新命名参数 = {
        键: (值.encode("utf-8") if isinstance(值, str) else 值)
        for 键, 值 in 命名参数.items()
    }
    return 新参数, 新命名参数


def 调用模块函数(
    模块句柄: Any,
    函数名: str,
    *参数: Any,
    **命名参数: Any,
) -> Any:
    """通过句柄调用白名单内的模块函数或读取常量。

    - 参数与返回值都经过安全转换；
    - 不接受下划线属性，也不接受白名单外的任何属性；
    - Python 侧异常统一包装为中文运行时错误。
    """
    if not isinstance(模块句柄, Python模块):
        raise 类型错误(
            "调用Python函数() 的第一个参数必须是 载入Python模块() 返回的模块句柄"
        )
    if not isinstance(函数名, str):
        raise 类型错误(
            f"调用Python函数() 的函数名必须是文本，收到: {type(函数名).__name__}"
        )

    规范名 = 模块句柄._模块名

    if 函数名.startswith("_") or 函数名 not in 允许的属性(规范名):
        raise 运行时错误(
            f"Python 模块 '{规范名}' 不允许访问 '{函数名}'：该属性不在互操作白名单中"
        )

    try:
        属性 = getattr(模块句柄._模块, 函数名)
    except AttributeError:
        raise 运行时错误(
            f"Python 模块 '{规范名}' 中不存在属性 '{函数名}'"
        ) from None

    # 常量（如 math.pi）直接按返回值处理。
    if not callable(属性):
        return 结果转道(属性)

    参数, 命名参数 = _适配参数(规范名, 参数, 命名参数)

    for 键 in 命名参数:
        if not isinstance(键, str) or 键.startswith("_"):
            raise 运行时错误("调用Python函数() 的命名参数名必须是非下划线开头的文本")

    安全参数 = [参数转Python(项) for 项 in 参数]
    安全命名参数 = {键: 参数转Python(值) for 键, 值 in 命名参数.items()}

    try:
        结果 = 属性(*安全参数, **安全命名参数)
    except Exception as 异常:
        raise 运行时错误(
            f"调用 Python 函数 {规范名}.{函数名}() 失败: "
            f"{type(异常).__name__}: {异常}"
        ) from 异常

    return 结果转道(结果)


__all__ = ["Python模块", "列出可用模块", "调用模块函数", "载入模块"]
