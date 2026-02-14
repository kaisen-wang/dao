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

from dataclasses import dataclass
from typing import Dict, List, Optional

from ..ast_nodes import MacroDefinition
from ..tokens import TokenType


@dataclass
class MacroInfo:
    """宏信息数据类"""

    name: str
    parameters: List[str]
    body: any  # 通常是 QuoteBlock 节点
    line: int
    column: int
    source_code: str  # 宏定义的源代码片段（用于调试）


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
        self.macros: Dict[str, List[MacroInfo]] = {}  # 宏名 -> 作用域链
        self.current_scope: List[str] = []  # 当前作用域链

    def enter_scope(self, scope_name: str = None):
        """进入新的作用域"""
        if scope_name:
            self.current_scope.append(scope_name)

    def leave_scope(self):
        """离开当前作用域"""
        if self.current_scope:
            scope_name = self.current_scope.pop()
            # 移除该作用域下定义的所有宏
            for macro_name in list(self.macros.keys()):
                scope_macros = []
                for info in self.macros[macro_name]:
                    if info.line not in self._get_scope_lines(scope_name):
                        scope_macros.append(info)
                if not scope_macros:
                    del self.macros[macro_name]
                else:
                    self.macros[macro_name] = scope_macros

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
        if macro_def.name in self.macros:
            for existing in self.macros[macro_def.name]:
                if existing.line == macro_def.line:
                    return False  # 同一位置的宏定义已存在

        # 创建宏信息对象
        macro_info = MacroInfo(
            name=macro_def.name,
            parameters=macro_def.parameters,
            body=macro_def.body,
            line=macro_def.line,
            column=macro_def.column,
            source_code=source_code,
        )

        # 存储到注册表中
        if macro_def.name not in self.macros:
            self.macros[macro_def.name] = []
        self.macros[macro_def.name].insert(0, macro_info)  # 最新的宏在作用域链顶部

        return True

    def find_macro(self, name: str) -> Optional[MacroInfo]:
        """
        根据名称查找宏定义

        Args:
            name: 宏名称

        Returns:
            MacroInfo: 宏信息（如果找到），None表示未找到
        """
        if name not in self.macros:
            return None

        return self.macros[name][0]  # 返回当前作用域链顶部的宏

    def get_macro_by_name(self, name: str, line: int = None) -> Optional[MacroInfo]:
        """
        根据名称和位置查找宏定义

        Args:
            name: 宏名称
            line: 定义位置的行号（用于作用域解析）

        Returns:
            MacroInfo: 宏信息（如果找到）
        """
        if name not in self.macros:
            return None

        for macro in self.macros[name]:
            if line is None or abs(macro.line - line) < 100:  # 简单的位置匹配
                return macro

        return self.macros[name][0]

    def get_all_macros(self) -> List[MacroInfo]:
        """获取所有宏的列表（去重）"""
        unique_macros = []
        seen = set()
        for macro_list in self.macros.values():
            for macro in macro_list:
                if macro.name not in seen:
                    seen.add(macro.name)
                    unique_macros.append(macro)
        return unique_macros

    def clear(self):
        """清空所有宏定义"""
        self.macros.clear()
        self.current_scope.clear()
        self._initialize()

    def get_macro_count(self) -> int:
        """获取宏定义的总数"""
        return sum(len(macros) for macros in self.macros.values())

    def _get_scope_lines(self, scope_name: str) -> List[int]:
        """获取作用域对应的行号范围（简单实现）"""
        # 这里可以根据实际的作用域管理进行优化
        return []

    def __repr__(self) -> str:
        """字符串表示"""
        macro_names = list(self.macros.keys())
        return (
            f"MacroRegistry("
            f"宏数量={self.get_macro_count()}, "
            f"宏名={', '.join(macro_names)}, "
            f"作用域={'.'.join(self.current_scope)})"
        )

    def __str__(self) -> str:
        """字符串表示（更详细）"""
        lines = ["宏注册表："]
        for name, info_list in self.macros.items():
            for info in info_list:
                lines.append(f"  宏名: {name} ({info.parameters})")
                lines.append(f"    定义位置: 第{info.line}行")
                lines.append(f"    作用域: {' -> '.join(self.current_scope)}")
        if not self.macros:
            lines.append("  无宏定义")
        return "\n".join(lines)


# 全局注册表实例
_registry = None


def get_registry() -> MacroRegistry:
    """获取全局宏注册表实例"""
    global _registry
    if _registry is None:
        _registry = MacroRegistry()
    return _registry


def register_macro(macro_def: MacroDefinition, source_code: str = ""):
    """注册宏定义的便捷函数"""
    return get_registry().register_macro(macro_def, source_code)


def find_macro(name: str) -> Optional[MacroInfo]:
    """查找宏定义的便捷函数"""
    return get_registry().find_macro(name)
