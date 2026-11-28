"""
VM 异常语义辅助函数
==================

从 AST 解释器（``dao/interpreter/statements/executor.py`` 的 ``exec_try`` /
``exec_throw``）抽取出的纯函数，供字节码 VM 与单元测试复用。

这些函数不依赖 Interpreter / VirtualMachine 类，只依赖 ``dao.errors``、
``dao.builtins.oop_types`` 以及 Environment 的 ``get`` / ``get_stack`` 接口。
"""

from ..builtins.oop_types import DaoError
from ..errors import (
    产出信号,
    名称错误,
    运行时错误,
    继续信号,
    道错误,
    跳出信号,
    返回信号,
)

__all__ = [
    "normalize_raise",
    "wrap_python_exception",
    "matches_catch",
    "is_control_signal",
]

# exec_try 在 ``except Exception`` 之前单独 re-raise 的四类控制流信号。
_CONTROL_SIGNALS = (跳出信号, 继续信号, 返回信号, 产出信号)


def normalize_raise(value, *, line=0, column=0, source="") -> BaseException:
    """把 ``抛出`` 语句的值转换为可抛出的异常（对齐 ``exec_throw``）。

    - 文本（str）→ ``运行时错误(value, line, column, source)``
    - ``DaoError`` 及其子类实例 → 原样返回
    - 其它值 → ``运行时错误(str(value), line, column, source)``
    """
    if isinstance(value, str):
        return 运行时错误(value, line, column, source)
    if isinstance(value, DaoError):
        return value
    return 运行时错误(str(value), line, column, source)


def wrap_python_exception(exc, env=None, *, line=0, column=0, source="") -> 道错误:
    """把 Python 异常包装成带中文信息的道错误（对齐 ``exec_try`` 的 catch 块）。

    返回值是可抛出的 ``道错误`` 实例，其 ``信息`` / ``类型`` / ``行`` / ``列`` /
    ``文件名`` / ``来源`` / ``堆栈`` 属性与 ``exec_try`` 中定义的 ``错误信息``
    对象保持一致，便于 VM 与 AST 两种模式共用同一套读取逻辑。

    行、列、来源优先使用显式传入的参数；未提供时从异常对象上读取
    ``line`` / ``lineno``、``column`` / ``colno``、``source``、``filename``。
    ``env`` 提供时按 ``exec_try`` 的格式生成调用栈字符串写入 ``堆栈``。
    """
    error_line = getattr(exc, "line", getattr(exc, "lineno", 0))
    error_col = getattr(exc, "column", getattr(exc, "colno", 0))
    filename = getattr(exc, "filename", "") or ""
    error_source = getattr(exc, "source", "") or ""

    effective_line = line or error_line
    effective_col = column or error_col
    effective_source = source or error_source

    frames = []
    stack_parts = []
    if env is not None:
        get_stack = getattr(env, "get_stack", None)
        if callable(get_stack):
            frames = list(get_stack())
            for i, frame in enumerate(frames):
                func_name = frame.get("function", "<匿名>")
                src_file = frame.get("file", "<未知>")
                src_line = frame.get("line", "?")
                stack_parts.append(
                    f"  {i}. 在 {func_name}() (文件: {src_file}, 行: {src_line})"
                )
    stack_str = "\n".join(stack_parts)

    message = f"{type(exc).__name__} {exc}"
    wrapped = 道错误(
        message,
        effective_line,
        effective_col,
        effective_source,
        stack=frames,
        filename=filename,
    )
    # 兼容 exec_try 中 错误信息 的字段名，使两种模式可共用读取逻辑。
    wrapped.信息 = message
    wrapped.类型 = type(exc).__name__
    wrapped.行 = effective_line
    wrapped.列 = effective_col
    wrapped.文件名 = filename
    wrapped.来源 = effective_source
    wrapped.堆栈 = stack_str
    return wrapped


def matches_catch(exc, error_type, env) -> bool:
    """判断异常是否匹配某个 ``捕获`` 项（对齐 ``exec_try`` 的匹配规则）。

    - ``error_type`` 为 ``"异常"``（或未指定）时捕获全部；
    - ``DaoError`` 及其子类按 ``exc.类型 == env.get(error_type)`` 匹配；
    - 普通 Python 异常按 ``isinstance(exc, env.get(error_type))`` 匹配；
    - 控制流信号恒不匹配（``exec_try`` 在捕获匹配之前单独 re-raise 它们）；
    - 未知错误类型时让 ``env.get`` 抛出的 ``名称错误`` 传播出去，与 AST
      解释器一致（不静默吞掉拼写错误的类型名）。
    """
    if is_control_signal(exc):
        return False
    if not error_type or error_type == "异常":
        return True

    error_class = env.get(error_type)
    if isinstance(exc, DaoError):
        return exc.类型 == error_class
    return isinstance(exc, error_class)


def is_control_signal(exc) -> bool:
    """判断异常是否为四类控制流信号（不属于道错误，不能被捕获）。"""
    return isinstance(exc, _CONTROL_SIGNALS)
