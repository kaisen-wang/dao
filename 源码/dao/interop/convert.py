"""
互操作桥的安全值转换
====================

道语言在解释器层面直接使用 Python 原生标量、``list``、``tuple``、``dict``
和 ``None`` 表示自身的值，因此基本类型可以直通。本模块的职责是：

1. **入站**（道 -> Python）：只放行标量、列表、元组、字典、集合等可序列化值，
   拒绝函数、模块、文件句柄、类实例等对象，防止把宿主对象走私进 Python 调用。
2. **出站**（Python -> 道）：把常见安全容器与几个无害包装类型转换成道原生值；
   对文件句柄、模块、函数、代码对象等一律抛中文运行时错误，杜绝对象泄漏。
3. 通过深度、容器长度、迭代器消费上限防止内存耗尽型攻击。
"""

import collections.abc
import datetime
import pathlib
from typing import Any

from ..errors import 类型错误, 运行时错误

# 安全上限：防止恶意构造的超大/嵌套/无限结构耗尽内存。
最大深度 = 32
最大容器元素 = 10000
最大迭代元素 = 10000


def _检查深度(深度: int) -> None:
    if 深度 > 最大深度:
        raise 运行时错误(
            f"Python 互操作桥拒绝转换嵌套过深的值（超过 {最大深度} 层）"
        )


def _检查大小(值: Any, 上限: int) -> None:
    try:
        长度 = len(值)
    except (TypeError, AttributeError):
        return
    if 长度 > 上限:
        raise 运行时错误(
            f"Python 互操作桥拒绝转换包含超过 {上限} 个元素的值，防止资源耗尽"
        )


# ---------------------------------------------------------------------------
# 入站：道语言值 -> Python 值
# ---------------------------------------------------------------------------
def 参数转Python(值: Any, _深度: int = 0) -> Any:
    """把道语言传入的参数转换为安全的 Python 值。

    允许的入站类型：``None``、``bool``、``int``、``float``、``str``、
    ``bytes``、``list``、``tuple``、``dict``、``set``、``frozenset``。
    其他类型（尤其是函数、模块、文件对象、``Python模块`` 句柄）一律拒绝。
    """
    _检查深度(_深度)

    if 值 is None or isinstance(值, (bool, int, float, str, bytes)):
        return 值

    if isinstance(值, (list, tuple)):
        _检查大小(值, 最大容器元素)
        转换后 = [参数转Python(项, _深度 + 1) for 项 in 值]
        return tuple(转换后) if isinstance(值, tuple) else 转换后

    if isinstance(值, dict):
        _检查大小(值, 最大容器元素)
        return {
            参数转Python(键, _深度 + 1): 参数转Python(值项, _深度 + 1)
            for 键, 值项 in 值.items()
        }

    if isinstance(值, (set, frozenset)):
        _检查大小(值, 最大容器元素)
        转换后 = [参数转Python(项, _深度 + 1) for 项 in 值]
        return frozenset(转换后) if isinstance(值, frozenset) else set(转换后)

    raise 类型错误(
        f"Python 互操作桥不接受类型为 {type(值).__name__} 的参数；"
        "只允许空值、布尔、整数、小数、文本、字节、列表、元组、字典和集合"
    )


# ---------------------------------------------------------------------------
# 出站：Python 值 -> 道语言值
# ---------------------------------------------------------------------------
def _转无害包装对象(值: Any, 深度: int) -> tuple[bool, Any]:
    """转换若干已知无害的包装类型；返回 ``(是否处理, 结果)``。"""
    # pathlib.Path / PurePath -> 路径字符串（不触碰文件系统）
    if isinstance(值, pathlib.PurePath):
        return True, str(值)

    # hashlib 哈希对象 -> 十六进制摘要字符串；递归转换以防伪造对象夹带危险值
    if hasattr(值, "hexdigest") and callable(值.hexdigest):
        return True, 结果转道(值.hexdigest(), 深度 + 1)

    # datetime / date / time -> ISO 8601 字符串；timedelta -> 总秒数
    if isinstance(值, (datetime.datetime, datetime.date, datetime.time)):
        return True, 值.isoformat()
    if isinstance(值, datetime.timedelta):
        return True, 值.total_seconds()

    return False, None


def 结果转道(值: Any, _深度: int = 0) -> Any:
    """把 Python 函数返回值转换为道语言值。

    不可序列化或不安全的对象（文件句柄、模块、函数、类、代码对象等）
    会触发中文运行时错误，绝不会以对象引用形式泄漏给道语言。
    """
    _检查深度(_深度)

    # 标量直通。bool 必须在 int 之前判断（bool 是 int 的子类）。
    if 值 is None or isinstance(值, (bool, int, float, str)):
        return 值
    if isinstance(值, (bytes, bytearray, memoryview)):
        return bytes(值)

    # 已知无害包装类型
    已处理, 结果 = _转无害包装对象(值, _深度)
    if 已处理:
        return 结果

    # 文件/流句柄等具备读写语义的对象一律拒绝，绝不物化其内容
    if any(callable(getattr(值, 属性, None))
           for 属性 in ("fileno", "read", "write", "close", "seek")):
        raise 运行时错误(
            f"Python 函数返回了不允许暴露给道语言的对象类型: {type(值).__name__}"
            "（文件/流句柄被禁止）"
        )

    # 映射（含 Counter / OrderedDict / defaultdict 等 dict 子类）
    if isinstance(值, collections.abc.Mapping):
        _检查大小(值, 最大容器元素)
        return {
            结果转道(键, _深度 + 1): 结果转道(值项, _深度 + 1)
            for 键, 值项 in 值.items()
        }

    # 列表与元组保持原有类别（道语言有独立的元组字面量）
    if isinstance(值, (list, tuple)):
        _检查大小(值, 最大容器元素)
        转换后 = [结果转道(项, _深度 + 1) for 项 in 值]
        return tuple(转换后) if isinstance(值, tuple) else 转换后

    # 集合、deque 等确定性要求较低的容器统一转成列表
    if isinstance(值, (set, frozenset, collections.abc.Sequence)):
        _检查大小(值, 最大容器元素)
        return [结果转道(项, _深度 + 1) for 项 in 值]

    # 迭代器：只允许白名单模块 itertools 产生的迭代器有上限地物化为列表。
    # 其他迭代器（生成器、文件对象等）一律拒绝，防止对象泄漏。
    if isinstance(值, collections.abc.Iterator):
        if type(值).__module__ != "itertools":
            raise 运行时错误(
                f"Python 函数返回了不允许暴露给道语言的对象类型: {type(值).__name__}"
                "（仅允许 itertools 迭代器）"
            )
        return 结果转道(list(_限长消费(值)), _深度 + 1)

    # 到这里仍未被识别的对象：拒绝泄漏。
    raise 运行时错误(
        f"Python 函数返回了不允许暴露给道语言的对象类型: {type(值).__name__}；"
        "互操作桥只接受空值、布尔、整数、小数、文本、字节、列表、元组、字典和集合"
    )


def _限长消费(迭代器: collections.abc.Iterator) -> list:
    """最多消费 ``最大迭代元素`` 个项，超出即抛错。"""
    结果: list = []
    for _ in range(最大迭代元素 + 1):
        try:
            结果.append(next(迭代器))
        except StopIteration:
            return 结果
    raise 运行时错误(
        f"Python 函数返回的迭代器产生超过 {最大迭代元素} 个元素，已拒绝转换"
    )


__all__ = ["参数转Python", "最大容器元素", "最大深度", "最大迭代元素", "结果转道"]
