"""
道语言调试器基础层
=================

在不修改解释器核心源码的前提下，为"道"语言提供断点、单步观察与变量查看能力。

架构：
    Debugger      —— 纯状态机：断点表、单步开关、执行计数、暂停事件、变量查看。
    DebugExecutor —— Interpreter 子类：覆盖 exec_statement / _exec_block，
                    在每条语句执行前调用 Debugger 的钩子。

无障碍原则：
    - 调试器未启用、未命中断点且未开启单步时，钩子立即返回，不改变程序行为。
    - 命中断点默认只记录事件；只有用户回调明确要求"暂停"才抛出 调试暂停 中断执行。
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from enum import Enum
from typing import Any

from ..environment import Environment
from ..interpreter import Interpreter


class 调试指令(Enum):
    """暂停回调可返回的控制指令。"""

    继续 = "继续"
    暂停 = "暂停"


@dataclass(frozen=True)
class 断点:
    """
    一个断点。

    文件：空字符串表示匹配任意文件（AST 节点本身不含文件名，故支持通配）。
    行号：从 1 开始，与 AST 节点的 line 属性一致。
    启用：可临时禁用而不删除。
    """

    文件: str
    行号: int
    启用: bool = True


@dataclass
class 暂停事件:
    """一次命中/单步暂停时捕获的上下文。"""

    文件: str
    行号: int
    列号: int
    语句类型: str
    环境: Environment
    调用栈: list
    步数: int

    def 查看变量(self, 名称: str | None = None) -> Any:
        """名称为空：返回当前作用域变量字典；否则沿作用域链查找该变量。"""
        if 名称 is None:
            return dict(self.环境.values)
        return self.环境.get(名称)


class 调试暂停(Exception):
    """用户回调要求暂停时抛出，携带触发暂停的事件。"""

    def __init__(self, 事件: 暂停事件):
        super().__init__(f"调试器在文件 {事件.文件 or '<任意>'} 第 {事件.行号} 行暂停")
        self.事件 = 事件


class Debugger:
    """道语言调试器：管理断点、单步、暂停回调，并提供变量查看。"""

    def __init__(self) -> None:
        self._断点: list[断点] = []
        self.启用: bool = True
        self.单步: bool = False
        self.执行计数: int = 0
        self.事件列表: list[暂停事件] = []
        self.最后事件: 暂停事件 | None = None
        self.暂停回调: Callable[[暂停事件], 调试指令 | str | None] | None = None

    # ---------------- 断点管理 ----------------
    def 设置断点(self, 文件: str, 行号: int) -> 断点:
        """设置断点；文件传空字符串表示匹配任意文件。重复设置不产生副本。"""
        if not isinstance(行号, int) or 行号 < 1:
            raise ValueError("行号必须是正整数")
        bp = 断点(文件=文件 or "", 行号=行号)
        if not any(b.文件 == bp.文件 and b.行号 == bp.行号 for b in self._断点):
            self._断点.append(bp)
        return bp

    def 删除断点(self, 文件: str, 行号: int) -> bool:
        """删除匹配的断点，返回是否删除成功。"""
        for i, bp in enumerate(self._断点):
            if bp.文件 == (文件 or "") and bp.行号 == 行号:
                self._断点.pop(i)
                return True
        return False

    def 列出断点(self) -> list[断点]:
        """返回当前断点列表（副本）。"""
        return list(self._断点)

    def 清空断点(self) -> None:
        self._断点.clear()

    # ---------------- 钩子 ----------------
    def 执行前回调(self, stmt: Any, env: Environment, 文件: str) -> None:
        """由 DebugExecutor 在每条语句执行前调用。"""
        if not self.启用:
            return
        self.执行计数 += 1
        行号 = getattr(stmt, "line", 0) or 0
        列号 = getattr(stmt, "column", 0) or 0
        if not self.单步 and not self._命中断点(文件, 行号):
            return
        事件 = 暂停事件(
            文件=文件,
            行号=行号,
            列号=列号,
            语句类型=type(stmt).__name__,
            环境=env,
            调用栈=env.get_stack(),
            步数=self.执行计数,
        )
        self.最后事件 = 事件
        self.事件列表.append(事件)
        if self.暂停回调 is not None:
            指令 = self.暂停回调(事件)
            if 指令 in (调试指令.暂停, "暂停"):
                raise 调试暂停(事件)

    def _命中断点(self, 文件: str, 行号: int) -> bool:
        return any(
            bp.启用 and bp.行号 == 行号 and bp.文件 in ("", 文件)
            for bp in self._断点
        )

    # ---------------- 变量查看 ----------------
    def 查看变量(self, 名称: str | None = None) -> Any:
        """查看最后一次暂停处的变量。未暂停过则抛出 RuntimeError。"""
        if self.最后事件 is None:
            raise RuntimeError("尚未在任何断点或单步处暂停，无法查看变量")
        return self.最后事件.查看变量(名称)

    def 查看调用栈(self) -> list:
        if self.最后事件 is None:
            return []
        return list(self.最后事件.调用栈)

    # ---------------- 复位 ----------------
    def 复位(self) -> None:
        """清空执行计数与事件，保留断点与开关设置。"""
        self.执行计数 = 0
        self.事件列表.clear()
        self.最后事件 = None


class DebugExecutor(Interpreter):
    """
    带调试钩子的解释器。

    通过继承 Interpreter 并覆盖语句执行入口插入钩子，完全不改动解释器核心源码。
    """

    def __init__(self, debugger: Debugger, 文件名: str = "", *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.debugger = debugger
        self.文件名 = 文件名

    def exec_statement(self, stmt, env: Environment) -> object:
        """顶层与块内大多数语句的执行入口。"""
        self.debugger.执行前回调(stmt, env, self.文件名)
        return super().exec_statement(stmt, env)

    def _exec_block(self, stmts: list, env: Environment) -> object:
        """
        语句块执行入口。块内 ExpressionStmt 不经过 exec_statement，
        此处逐条补钩子；其余语句交给 exec_statement 钩子，避免重复计数。
        """
        from ..ast_nodes import ExpressionStmt

        result = None
        for stmt in stmts:
            if isinstance(stmt, ExpressionStmt):
                self.debugger.执行前回调(stmt, env, self.文件名)
                result = self.eval_expression(stmt.expression, env)
            else:
                result = self.exec_statement(stmt, env)
        return result
