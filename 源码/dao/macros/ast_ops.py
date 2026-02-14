"""
AST操作工具
===========

提供对AST节点的各种操作，包括搜索、修改、替换和分析。

主要功能：
1. 节点搜索和查询
2. 节点替换和修改
3. 结构分析和验证
4. 代码生成支持
5. 节点创建和操作

设计原则：
1. 提供简单易用的API
2. 支持所有类型的节点操作
3. 保持与源AST的一致性
4. 提供错误处理和验证
"""

from typing import Any, Callable, Dict, List, Optional, Union

from ..ast_nodes import (
    BinaryOp,
    BooleanLiteral,
    ChannelExpr,
    Expression,
    FunctionCall,
    LogicBlock,
    LogicConstraint,
    LogicCut,
    LogicFact,
    LogicNegation,
    LogicPredicate,
    LogicQuery,
    LogicRule,
    MacroCall,
    MacroDefinition,
    NullLiteral,
    NumberLiteral,
    Program,
    QuoteBlock,
    ReceiveExpr,
    Statement,
    StringLiteral,
    UnaryOp,
    UnquoteExpr,
)
from ..ast_nodes import LogicVariable as LogicVar
from ..tokens import TokenType


class ASTOperations:
    """AST操作工具类"""

    @staticmethod
    def replace_variables(node: Any, replacements: Dict[str, Any]) -> Any:
        """
        替换节点中的变量引用

        Args:
            node: 要操作的节点
            replacements: 变量名到替换值的映射

        Returns:
            替换后的节点
        """
        if not replacements:
            return node

        # 处理节点列表
        if isinstance(node, list):
            return [ASTOperations.replace_variables(n, replacements) for n in node]

        # 处理变量节点 - 支持 $x 格式
        if hasattr(node, "name") and isinstance(node.name, str):
            # 检查是否带 $ 前缀
            variable_name = node.name.lstrip("$")
            if variable_name in replacements:
                return replacements[variable_name]

        # 递归处理子节点
        if hasattr(node, "__dict__"):
            for attr_name in dir(node):
                if not attr_name.startswith("__") and hasattr(node, attr_name):
                    attr_value = getattr(node, attr_name)
                    new_value = ASTOperations.replace_variables(
                        attr_value, replacements
                    )
                    setattr(node, attr_name, new_value)

        return node

    @staticmethod
    def find_nodes(node: Any, node_type: type) -> List[Any]:
        """
        查找所有特定类型的节点

        Args:
            node: 要搜索的根节点
            node_type: 要查找的节点类型

        Returns:
            匹配的节点列表
        """
        matches = []

        if isinstance(node, list):
            for n in node:
                matches.extend(ASTOperations.find_nodes(n, node_type))
            return matches

        if isinstance(node, node_type):
            matches.append(node)

        # 检查子节点
        if hasattr(node, "__dict__"):
            for attr_name in dir(node):
                if not attr_name.startswith("__") and hasattr(node, attr_name):
                    attr_value = getattr(node, attr_name)
                    matches.extend(ASTOperations.find_nodes(attr_value, node_type))

        return matches

    @staticmethod
    def find_node_by_condition(
        node: Any, condition: Callable[[Any], bool]
    ) -> List[Any]:
        """
        按条件查找节点

        Args:
            node: 要搜索的根节点
            condition: 匹配条件函数

        Returns:
            匹配的节点列表
        """
        matches = []

        if isinstance(node, list):
            for n in node:
                matches.extend(ASTOperations.find_node_by_condition(n, condition))
            return matches

        if condition(node):
            matches.append(node)

        if hasattr(node, "__dict__"):
            for attr_name in dir(node):
                if not attr_name.startswith("__") and hasattr(node, attr_name):
                    attr_value = getattr(node, attr_name)
                    matches.extend(
                        ASTOperations.find_node_by_condition(attr_value, condition)
                    )

        return matches

    @staticmethod
    def replace_node(node: Any, target_node: Any, replacement: Any) -> Any:
        """
        替换指定的节点

        Args:
            node: 要操作的根节点
            target_node: 要替换的目标节点
            replacement: 替换值

        Returns:
            修改后的节点
        """
        if node is target_node:
            return replacement

        if isinstance(node, list):
            return [
                ASTOperations.replace_node(n, target_node, replacement) for n in node
            ]

        if hasattr(node, "__dict__"):
            for attr_name in dir(node):
                if not attr_name.startswith("__") and hasattr(node, attr_name):
                    attr_value = getattr(node, attr_name)
                    new_value = ASTOperations.replace_node(
                        attr_value, target_node, replacement
                    )
                    setattr(node, attr_name, new_value)

        return node

    @staticmethod
    def modify_node(
        node: Any, target_type: type, modify_func: Callable[[Any], Any]
    ) -> Any:
        """
        修改特定类型的节点

        Args:
            node: 要操作的根节点
            target_type: 目标节点类型
            modify_func: 修改函数

        Returns:
            修改后的节点
        """
        if isinstance(node, target_type):
            return modify_func(node)

        if isinstance(node, list):
            return [
                ASTOperations.modify_node(n, target_type, modify_func) for n in node
            ]

        if hasattr(node, "__dict__"):
            for attr_name in dir(node):
                if not attr_name.startswith("__") and hasattr(node, attr_name):
                    attr_value = getattr(node, attr_name)
                    new_value = ASTOperations.modify_node(
                        attr_value, target_type, modify_func
                    )
                    setattr(node, attr_name, new_value)

        return node

    @staticmethod
    def extract_node_info(node: Any) -> Dict[str, Any]:
        """提取节点信息"""
        info = {
            "type": type(node).__name__,
            "line": getattr(node, "line", -1),
            "column": getattr(node, "column", -1),
        }

        # 提取字段信息
        if hasattr(node, "__dataclass_fields__"):
            for field_name in getattr(node, "__dataclass_fields__", {}).keys():
                if field_name not in ["line", "column"]:
                    value = getattr(node, field_name)
                    info[field_name] = value

        return info

    @staticmethod
    def validate_node(node: Any, validator: Callable[[Any], bool]) -> bool:
        """
        验证节点是否符合特定条件

        Args:
            node: 要验证的节点
            validator: 验证函数

        Returns:
            验证结果
        """
        if validator(node):
            return True

        if isinstance(node, list):
            return any(ASTOperations.validate_node(n, validator) for n in node)

        if hasattr(node, "__dict__"):
            for attr_name in dir(node):
                if not attr_name.startswith("__") and hasattr(node, attr_name):
                    attr_value = getattr(node, attr_name)
                    if ASTOperations.validate_node(attr_value, validator):
                        return True

        return False

    @staticmethod
    def traverse_node(
        node: Any, pre_order: Callable[[Any], Any], post_order: Callable[[Any], Any]
    ) -> Any:
        """
        遍历节点并应用操作

        Args:
            node: 要遍历的根节点
            pre_order: 前序遍历操作
            post_order: 后序遍历操作

        Returns:
            处理后的节点
        """
        if isinstance(node, list):
            return [ASTOperations.traverse_node(n, pre_order, post_order) for n in node]

        # 前序操作
        node = pre_order(node)

        # 处理子节点
        if hasattr(node, "__dict__"):
            for attr_name in dir(node):
                if not attr_name.startswith("__") and hasattr(node, attr_name):
                    attr_value = getattr(node, attr_name)
                    new_value = ASTOperations.traverse_node(
                        attr_value, pre_order, post_order
                    )
                    setattr(node, attr_name, new_value)

        # 后序操作
        node = post_order(node)

        return node

    @staticmethod
    def count_nodes(node: Any) -> int:
        """计算节点数量"""
        if node is None:
            return 0

        count = 1

        if isinstance(node, list):
            return sum(ASTOperations.count_nodes(n) for n in node)

        if hasattr(node, "__dict__"):
            for attr_name in dir(node):
                if not attr_name.startswith("__") and hasattr(node, attr_name):
                    attr_value = getattr(node, attr_name)
                    count += ASTOperations.count_nodes(attr_value)

        return count

    @staticmethod
    def get_node_depth(node: Any, depth: int = 0) -> int:
        """计算节点深度"""
        if node is None:
            return depth

        max_depth = depth

        if isinstance(node, list):
            for n in node:
                current_depth = ASTOperations.get_node_depth(n, depth + 1)
                if current_depth > max_depth:
                    max_depth = current_depth
            return max_depth

        if hasattr(node, "__dict__"):
            for attr_name in dir(node):
                if not attr_name.startswith("__") and hasattr(node, attr_name):
                    attr_value = getattr(node, attr_name)
                    current_depth = ASTOperations.get_node_depth(attr_value, depth + 1)
                    if current_depth > max_depth:
                        max_depth = current_depth

        return max_depth
