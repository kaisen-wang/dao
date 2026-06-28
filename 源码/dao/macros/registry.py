"""
宏注册表
========

管理已定义的宏，提供宏的注册、查找和管理功能。

宏注册表是一个单例对象，负责：
1. 存储所有已定义的宏
2. 提供查找宏定义的接口
3. 管理宏的作用域
4. 防止宏重定义

宏定义包含：
- 宏名称
- 参数列表
- 宏体（引述块）
- 定义位置
"""

import logging
from dataclasses import dataclass
from typing import Dict, List, Optional, Set

from ..ast_nodes import MacroDefinition
from ..tokens import TokenType

logger = logging.getLogger('dao.macros')


@dataclass
class MacroInfo:
    """宏信息数据类"""

    name: str
    parameters: List[str]
    body: any  # 通常是 QuoteBlock 节点
    line: int
    column: int
    source_code: str  # 宏定义的源代码片段（用于调试）
    scope_depth: int = 0  # 定义时的作用域深度


class MacroRegistry:
    """宏注册表管理类"""

    _instance = None

    def __new__(cls):
        """单例模式：确保只创建一个实例"""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialize()
        return cls._instance

    def _initialize(self):
        """初始化注册表"""
        self._macros: Dict[str, List[MacroInfo]] = {}  # 宏名 → 定义栈
        self._scope_stack: List[Set[str]] = [set()]  # 作用域栈，每层记录该层定义的宏名
        self._scope_depth: int = 0  # 当前作用域深度

    def enter_scope(self, scope_name: str = None):
        """进入新的作用域"""
        self._scope_stack.append(set())
        self._scope_depth += 1
        logger.debug("进入作用域，深度=%d", self._scope_depth)

    def leave_scope(self):
        """离开当前作用域"""
        if len(self._scope_stack) <= 1:
            return  # 不能离开根作用域

        # 获取离开的作用域中定义的宏名
        leaving_scope = self._scope_stack.pop()
        self._scope_depth -= 1

        # 移除该作用域下定义的所有宏
        for macro_name in leaving_scope:
            if macro_name in self._macros:
                # 移除该作用域深度定义的宏
                self._macros[macro_name] = [
                    info for info in self._macros[macro_name]
                    if info.scope_depth != self._scope_depth + 1
                ]
                if not self._macros[macro_name]:
                    del self._macros[macro_name]

        logger.debug("离开作用域，深度=%d", self._scope_depth)

    def register_macro(self, macro_def: MacroDefinition, source_code: str = ""):
        """
        注册宏定义

        Args:
            macro_def: MacroDefinition AST节点
            source_code: 宏定义的源代码（用于调试）

        Returns:
            bool: 注册是否成功
        """
        # 检查是否已在当前作用域中定义了同名宏
        current_scope = self._scope_stack[-1]
        if macro_def.name in current_scope:
            from ..errors import 宏展开错误
            raise 宏展开错误(
                f"宏 '{macro_def.name}' 已在当前作用域中定义",
                macro_def.line,
                macro_def.column,
                source_code,
            )

        # 创建宏信息对象
        macro_info = MacroInfo(
            name=macro_def.name,
            parameters=macro_def.parameters,
            body=macro_def.body,
            line=macro_def.line,
            column=macro_def.column,
            source_code=source_code,
            scope_depth=self._scope_depth,
        )

        # 存储到注册表中
        if macro_def.name not in self._macros:
            self._macros[macro_def.name] = []
        self._macros[macro_def.name].insert(0, macro_info)  # 最新的宏在栈顶

        # 记录到当前作用域
        current_scope.add(macro_def.name)

        logger.debug("注册宏 '%s'，作用域深度=%d", macro_def.name, self._scope_depth)
        return True

    def find_macro(self, name: str) -> Optional[MacroInfo]:
        """
        根据名称查找宏定义

        Args:
            name: 宏名称

        Returns:
            MacroInfo: 宏信息（如果找到），None表示未找到
        """
        if name not in self._macros:
            return None

        return self._macros[name][0]  # 返回当前作用域链顶部的宏

    def get_macro_by_name(self, name: str, line: int = None) -> Optional[MacroInfo]:
        """
        根据名称查找宏定义

        Args:
            name: 宏名称
            line: 定义位置的行号（保留参数，用于兼容）

        Returns:
            MacroInfo: 宏信息（如果找到）
        """
        return self.find_macro(name)

    def get_all_macros(self) -> List[MacroInfo]:
        """获取所有宏的列表（去重）"""
        unique_macros = []
        seen = set()
        for macro_list in self._macros.values():
            for macro in macro_list:
                if macro.name not in seen:
                    seen.add(macro.name)
                    unique_macros.append(macro)
        return unique_macros

    def clear(self):
        """清空所有宏定义"""
        self._macros.clear()
        self._scope_stack = [set()]
        self._scope_depth = 0

    def get_macro_count(self) -> int:
        """获取宏定义的总数"""
        return sum(len(macros) for macros in self._macros.values())

    def __repr__(self) -> str:
        """字符串表示"""
        macro_names = list(self._macros.keys())
        return (
            f"MacroRegistry("
            f"宏数量={self.get_macro_count()}, "
            f"宏名={', '.join(macro_names)}, "
            f"作用域深度={self._scope_depth})"
        )

    def __str__(self) -> str:
        """字符串表示（更详细）"""
        lines = ["宏注册表："]
        for name, info_list in self._macros.items():
            for info in info_list:
                lines.append(f"  宏名: {name} ({info.parameters})")
                lines.append(f"    定义位置: 第{info.line}行")
                lines.append(f"    作用域深度: {info.scope_depth}")
        if not self._macros:
            lines.append("  无宏定义")
        return "\n".join(lines)
