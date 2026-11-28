"""道语言调用点上下文。

解释器在调用可调用对象时写入当前源码位置，标准库（如日志）可读取它，
调用者无需显式传入位置。使用 ContextVar 保证线程 / 协程隔离，并在嵌套
调用返回后正确恢复上一层的位置。
"""

from __future__ import annotations

from contextvars import ContextVar
from pathlib import Path
from typing import NamedTuple


def _relative_source(source: str) -> str:
    """把源文件路径规范化为相对于命令执行目录（cwd）的路径。

    根目录取启动命令时所在目录，脚本无需 ``道.配置`` 也能正确显示位置；
    不在 cwd 下的文件（如临时脚本）保留原路径。
    """
    if not source or "\n" in source:
        return ""
    try:
        resolved = Path(source).resolve()
        cwd = Path.cwd().resolve()
        return resolved.relative_to(cwd).as_posix()
    except (OSError, ValueError):
        return source


class CallSite(NamedTuple):
    """一次调用的源码位置。"""

    source: str
    line: int
    column: int

    def describe(self) -> str:
        """返回便于阅读的位置文本：相对命令执行目录的路径:行号。"""
        source = _relative_source(self.source)
        if source:
            return f"{source}:{self.line}"
        return f"<道源码>:{self.line}"


current_call_site: ContextVar[CallSite | None] = ContextVar(
    "dao_current_call_site", default=None
)
