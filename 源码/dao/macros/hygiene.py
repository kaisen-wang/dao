"""
卫生宏处理
==========

提供卫生宏处理功能，防止变量捕获问题。

卫生宏处理的核心概念：
- 自由变量：宏内部使用但未定义的变量
- 绑定变量：宏内部定义的变量
- 变量捕获：宏调用时，宏内部的自由变量意外捕获了外部变量

主要功能：
1. 分析变量作用域
2. 检测变量捕获问题
3. 生成唯一的变量名
4. 应用变量重写
5. 确保变量引用的正确性

实现策略：
1. 使用 name rewriting 技术
2. 为变量添加唯一前缀
3. 维护变量到唯一名称的映射
"""

from dataclasses import dataclass
from typing import Dict, List, Optional, Set

from ..ast_nodes import (
    BinaryOp,
    BooleanLiteral,
    Expression,
    FunctionCall,
    Identifier,
    MacroCall,
    NullLiteral,
    NumberLiteral,
    QuoteBlock,
    Statement,
    StringLiteral,
    UnaryOp,
    UnquoteExpr,
)
from .scope import MacroScope


class HygieneProcessor:
    """卫生宏处理器"""

    def __init__(self):
        self.variable_map: Dict[str, str] = {}  # 变量名映射表
        self.counter = 0

    def process(self, node: any, scope: MacroScope):
        """
        应用卫生宏处理

        Args:
            node: 要处理的节点
            scope: 变量作用域信息

        Returns:
            经过卫生处理后的节点
        """
        if not node or scope is None:
            return node

        self.variable_map.clear()
        self.counter = 0

        # 分析变量捕获
        captures = scope.analyze_captures()
        for var in captures:
            self.variable_map[var.name] = self._generate_unique_name(var.name)

        return self._rewrite_variables(node)

    def _rewrite_variables(self, node: any):
        """递归重写变量名"""
        if node is None:
            return None

        if isinstance(node, list):
            return [self._rewrite_variables(n) for n in node]

        if hasattr(node, "__dict__"):
            for attr_name in dir(node):
                if not attr_name.startswith("__"):
                    attr_value = getattr(node, attr_name)
                    new_value = self._rewrite_variables(attr_value)
                    setattr(node, attr_name, new_value)

        # 重写变量引用
        if hasattr(node, "name") and isinstance(node.name, str):
            if node.name in self.variable_map:
                node.name = self.variable_map[node.name]

        return node

    def _generate_unique_name(self, base_name: str) -> str:
        """
        生成唯一的变量名

        Args:
            base_name: 基础变量名

        Returns:
            str: 唯一变量名
        """
        unique_name = f"{base_name}__{self.counter}"
        self.counter += 1
        return unique_name

    def add_rewrite(self, original: str, new_name: str):
        """添加变量重写规则"""
        if original not in self.variable_map:
            self.variable_map[original] = new_name
        return new_name

    def get_rewrite_map(self) -> Dict[str, str]:
        """获取变量重写映射表"""
        return dict(self.variable_map)

    def has_rewrite(self, variable_name: str) -> bool:
        """检查变量是否需要重写"""
        return variable_name in self.variable_map

    def __str__(self):
        return (
            f"HygieneProcessor("
            f"变量重写数={len(self.variable_map)}, "
            f"变量映射={self.variable_map})"
        )

    def __repr__(self):
        return str(self)


class HygieneAnalysis:
    """卫生分析工具"""

    @staticmethod
    def get_free_variables(scope: MacroScope) -> List[str]:
        """获取自由变量列表"""
        return [var.name for var in scope.get_free_variables()]

    @staticmethod
    def get_bound_variables(scope: MacroScope) -> List[str]:
        """获取绑定变量列表"""
        return [var.name for var in scope.get_used_variables() if var.is_bound]

    @staticmethod
    def get_capture_risk(scope: MacroScope) -> Dict[str, str]:
        """分析变量捕获风险"""
        free_vars = {var.name: var for var in scope.get_free_variables()}
        bound_vars = {
            var.name: var for var in scope.get_used_variables() if var.is_bound
        }

        risk_map = {}
        for var_name, info in free_vars.items():
            if var_name in bound_vars:
                risk_map[var_name] = f"变量 '{var_name}' 可能被捕获（作用域冲突）"

    @staticmethod
    def get_capture_risk(scope: MacroScope) -> Dict[str, str]:
        """分析变量捕获风险"""
        free_vars = {var.name: var for var in scope.get_free_variables()}
        bound_vars = {
            var.name: var for var in scope.get_used_variables() if var.is_bound
        }

        risk_map = {}
        for var_name, info in free_vars.items():
            if var_name in bound_vars:
                risk_map[var_name] = f"变量 '{var_name}' 可能被捕获（作用域冲突）"
        return risk_map

    @staticmethod
    def print_analysis(scope: MacroScope):
        """打印变量作用域分析信息"""
        free_vars = HygieneAnalysis.get_free_variables(scope)
        bound_vars = HygieneAnalysis.get_bound_variables(scope)
        capture_risk = HygieneAnalysis.get_capture_risk(scope)

        print("\n=== 变量作用域分析 ===")
        print(f"绑定变量: {', '.join(bound_vars)}")
        print(f"自由变量: {', '.join(free_vars)}")
        if capture_risk:
            print("\n=== 变量捕获风险 ===")
            for var, msg in capture_risk.items():
                print(msg)
