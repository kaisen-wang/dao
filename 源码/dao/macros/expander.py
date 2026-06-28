"""
宏展开器
========

宏展开器是道语言宏系统的核心组件，负责：
1. 找到代码中的宏调用
2. 替换为对应的引述块
3. 注入表达式值
4. 处理递归宏调用
5. 防止无限递归

主要功能：
- 编译期宏执行
- 递归宏展开
- 高级错误恢复
- 宏展开跟踪

展开过程：
1. 识别宏调用（!前缀）
2. 查找对应的宏定义
3. 应用参数绑定
4. 展开引述块
5. 处理注入表达式
6. 递归处理结果中的宏调用
"""

import copy
import logging
import re
from typing import List, Optional, Union

from ..ast_nodes import (
    BooleanLiteral,
    Expression,
    Identifier,
    MacroCall,
    NullLiteral,
    NumberLiteral,
    QuoteBlock,
    ReturnStmt,
    Statement,
    StringLiteral,
    UnquoteExpr,
)
from ..tokens import TokenType
from .hygiene import HygieneProcessor
from .registry import MacroInfo, MacroRegistry
from .scope import MacroScope

logger = logging.getLogger('dao.macros')


class MacroExpander:
    """宏展开器核心类"""

    def __init__(self):
        self.registry = MacroRegistry()
        self.hygiene_processor = HygieneProcessor()
        self.max_recursion = 100  # 防止无限递归的最大深度
        self.trace_expansion = False  # 是否跟踪展开过程

    def expand(
        self, node: Union[Expression, Statement, List], recursion_depth: int = 0
    ):
        """
        展开代码中的宏调用

        Args:
            node: 要展开的AST节点
            recursion_depth: 当前递归深度

        Returns:
            展开后的节点
        """
        if recursion_depth >= self.max_recursion:
            from ..errors import 宏展开错误
            raise 宏展开错误(
                f"宏展开递归深度超限（最大{self.max_recursion}层）",
                getattr(node, 'line', 0),
                getattr(node, 'column', 0),
                "",
            )

        # 处理节点列表
        if isinstance(node, list):
            return [self.expand(n, recursion_depth) for n in node]

        # 处理宏调用
        if isinstance(node, MacroCall):
            return self._expand_macro_call(node, recursion_depth)

        # 处理引述块
        if isinstance(node, QuoteBlock):
            return self._expand_quote_block(node, recursion_depth)

        # 处理注入表达式
        if isinstance(node, UnquoteExpr):
            return self._expand_unquote_expr(node, recursion_depth)

        # 处理其他类型的节点
        return self._expand_other_nodes(node, recursion_depth)

    def _expand_macro_call(self, call: MacroCall, recursion_depth: int):
        """处理宏调用"""
        # 查找宏定义
        macro_info = self.registry.find_macro(call.name)
        if not macro_info:
            return call

        logger.debug("展开宏调用: !%s%s (深度=%d)", call.name, call.arguments, recursion_depth)

        # 检测递归宏调用：如果宏体中包含对自身的调用，
        # 则只做参数替换，不递归展开，让解释器在运行时处理递归
        if self._is_recursive_macro(macro_info, call.name):
            logger.debug("检测到递归宏 '%s'，仅做参数替换", call.name)
            expanded_body = self._apply_macro_parameters(
                macro_info.body, macro_info.parameters, call.arguments
            )
            # 卫生宏处理
            expanded_body = self._apply_hygiene(expanded_body, macro_info.parameters)
            return expanded_body

        # 评估宏参数
        evaluated_args = [self.expand(arg, recursion_depth) for arg in call.arguments]

        # 应用参数绑定
        expanded_body = self._apply_macro_parameters(
            macro_info.body, macro_info.parameters, evaluated_args
        )

        # 卫生宏处理
        expanded_body = self._apply_hygiene(expanded_body, macro_info.parameters)

        # 递归展开结果中的宏调用
        expanded = self.expand(expanded_body, recursion_depth + 1)

        logger.debug("宏调用结果: %s", expanded)

        return expanded

    def _is_recursive_macro(self, macro_info: MacroInfo, macro_name: str) -> bool:
        """检测宏体中是否包含对自身的递归调用"""
        return self._contains_macro_call(macro_info.body, macro_name)

    def _contains_macro_call(self, node, macro_name: str) -> bool:
        """检查节点树中是否包含指定名称的宏调用"""
        if node is None:
            return False

        if isinstance(node, list):
            return any(self._contains_macro_call(n, macro_name) for n in node)

        if isinstance(node, MacroCall) and node.name == macro_name:
            return True

        if hasattr(node, '__dataclass_fields__'):
            for field_name in node.__dataclass_fields__:
                if field_name in ('line', 'column'):
                    continue
                attr = getattr(node, field_name)
                if isinstance(attr, list):
                    if any(self._contains_macro_call(item, macro_name) for item in attr):
                        return True
                elif hasattr(attr, '__dataclass_fields__') or isinstance(attr, (Expression, Statement)):
                    if self._contains_macro_call(attr, macro_name):
                        return True

        return False

    def _expand_quote_block(self, block: QuoteBlock, recursion_depth: int):
        """处理引述块"""
        # 引述块内的代码在宏展开阶段保持原样
        return QuoteBlock(body=block.body.copy())

    def _expand_unquote_expr(self, expr: UnquoteExpr, recursion_depth: int):
        """处理注入表达式"""
        # 注入表达式需要被评估
        expanded = self.expand(expr.expression, recursion_depth)
        return expanded

    def _expand_other_nodes(
        self, node: Union[Expression, Statement], recursion_depth: int
    ):
        """处理其他类型的节点"""
        if not hasattr(node, '__dataclass_fields__'):
            return node

        for field_name in node.__dataclass_fields__:
            if field_name in ('line', 'column'):
                continue
            attr = getattr(node, field_name)

            # 如果属性是可迭代对象，递归处理
            if isinstance(attr, list):
                new_value = [self.expand(item, recursion_depth) for item in attr]
                setattr(node, field_name, new_value)
            elif isinstance(attr, (Expression, Statement)):
                new_value = self.expand(attr, recursion_depth)
                setattr(node, field_name, new_value)

        return node

    def _apply_hygiene(self, node, macro_parameters: List[str]):
        """应用卫生宏处理"""
        # 创建作用域分析器
        scope = MacroScope()
        param_names = set()
        for param in macro_parameters:
            name = param.split('=')[0].strip() if '=' in param else param.strip()
            param_names.add(name)

        scope._macro_parameters = param_names

        # 收集节点中的变量信息
        self._collect_variables(node, scope)

        # 应用卫生处理
        return self.hygiene_processor.process(node, scope)

    def _collect_variables(self, node, scope: MacroScope):
        """收集节点中的变量定义和使用信息"""
        if node is None:
            return

        if isinstance(node, list):
            for n in node:
                self._collect_variables(n, scope)
            return

        if isinstance(node, VariableDecl):
            scope.define_variable(node.name, is_bound=True)

        if isinstance(node, Identifier):
            scope.use_variable(node.name)

        if hasattr(node, '__dataclass_fields__'):
            for field_name in node.__dataclass_fields__:
                if field_name in ('line', 'column'):
                    continue
                attr = getattr(node, field_name)
                if isinstance(attr, list):
                    for item in attr:
                        self._collect_variables(item, scope)
                elif hasattr(attr, '__dataclass_fields__') or isinstance(attr, Identifier):
                    self._collect_variables(attr, scope)

    def _apply_macro_parameters(
        self, body: Expression, parameters: List[str], arguments: List[Expression]
    ):
        """应用宏参数绑定"""
        from .ast_ops import ASTOperations

        # 深拷贝传入的 body，防止多次调用之间的状态共享
        body = copy.deepcopy(body)

        logger.debug("=== 宏参数绑定 ===")
        logger.debug("  参数列表: %s", parameters)
        logger.debug("  实参列表: %s", arguments)

        # 支持可选参数（处理默认值）
        # 首先解析参数列表，分离参数名和默认值
        parsed_params = []
        for param in parameters:
            if "=" in param:
                name, default = param.split("=", 1)
                parsed_params.append((name.strip(), default.strip()))
            else:
                parsed_params.append((param.strip(), None))

        # 创建替换字典，处理可选参数
        replacements = {}
        for i, (param_name, default_value) in enumerate(parsed_params):
            if i < len(arguments):
                replacements[param_name] = arguments[i]
                logger.debug("  绑定参数 '%s' -> %s (来自实参)", param_name, arguments[i])
            else:
                # 处理默认值
                default_node = self._parse_default_value(default_value, param_name)
                if default_node is not None:
                    replacements[param_name] = default_node
                    logger.debug("  绑定参数 '%s' -> %s (默认值)", param_name, default_value)

        # 处理返回值的情况
        target_body = body

        if (
            isinstance(body, list)
            and len(body) == 1
            and isinstance(body[0], ReturnStmt)
        ):
            # 处理 return 语句的情况
            target_body = body[0].value

        # 参数替换
        result = self._replace_in_node(target_body, replacements)
        return result

    def _parse_default_value(self, value_str: Optional[str], param_name: str) -> Optional[Expression]:
        """解析宏参数默认值"""
        if value_str is None:
            return None

        value_str = value_str.strip()

        # 数值（含负数、浮点数）
        if re.match(r'^-?\d+$', value_str):
            return NumberLiteral(value=int(value_str))
        if re.match(r'^-?\d+\.\d+$', value_str):
            return NumberLiteral(value=float(value_str))
        # 布尔值
        if value_str in ('true', '真'):
            return BooleanLiteral(value=True)
        if value_str in ('false', '假'):
            return BooleanLiteral(value=False)
        # 空值
        if value_str in ('null', '空'):
            return NullLiteral()
        # 字符串
        if (value_str.startswith('"') and value_str.endswith('"')) or \
           (value_str.startswith("'") and value_str.endswith("'")):
            return StringLiteral(value=value_str[1:-1])
        # 对于名为 '块' 的参数，如果没有传入实参且没有默认值，不设置默认值
        if param_name == '块':
            return None

        logger.warning("无法解析默认值 '%s'，使用 0 作为默认值", value_str)
        return NumberLiteral(value=0)

    def _replace_in_node(self, node, replacements: dict):
        """在节点中替换宏参数"""
        if not replacements:
            return node

        if isinstance(node, list):
            return [self._replace_in_node(n, replacements) for n in node]

        if node is None:
            return node

        # 处理 UnquoteExpr 中的 Identifier
        if isinstance(node, UnquoteExpr):
            if isinstance(node.expression, Identifier):
                param_name = node.expression.name
                if param_name in replacements:
                    return replacements[param_name]
            else:
                node.expression = self._replace_in_node(node.expression, replacements)
            return node

        # 处理 Identifier
        if isinstance(node, Identifier):
            if node.name in replacements:
                return replacements[node.name]
            return node

        # 处理 QuoteBlock - 进入其内部替换
        if isinstance(node, QuoteBlock):
            node.body = [self._replace_in_node(stmt, replacements) for stmt in node.body]
            return node

        # 递归处理其他类型的节点
        if hasattr(node, '__dataclass_fields__'):
            for field_name in node.__dataclass_fields__:
                if field_name in ('line', 'column'):
                    continue
                attr_value = getattr(node, field_name)
                if isinstance(attr_value, list):
                    new_value = [self._replace_in_node(n, replacements) for n in attr_value]
                    setattr(node, field_name, new_value)
                elif hasattr(attr_value, '__dataclass_fields__') or isinstance(attr_value, (Expression, Statement)):
                    new_value = self._replace_in_node(attr_value, replacements)
                    setattr(node, field_name, new_value)

        return node

    def set_trace(self, enabled: bool):
        """设置是否跟踪展开过程"""
        self.trace_expansion = enabled

    def register_builtin_macros(self):
        """注册内置宏"""
        # 内置宏将在后续版本中实现
        pass

    def __repr__(self):
        return f"MacroExpander(注册表={self.registry})"
