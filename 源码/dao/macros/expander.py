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
    VariableDecl,
)
from ..tokens import TokenType
from .hygiene import HygieneProcessor
from .registry import MacroInfo, MacroRegistry
from .scope import MacroScope

logger = logging.getLogger('dao.macros')


class MacroExpander:
    """宏展开器核心类"""

    # 错误恢复策略
    STRICT = "strict"      # 严格模式：出错即停止
    PERMISSIVE = "permissive"  # 宽松模式：跳过出错的宏，继续展开

    def __init__(self):
        self.registry = MacroRegistry()
        self.hygiene_processor = HygieneProcessor()
        self.max_recursion = 100  # 防止无限递归的最大深度
        self.trace_expansion = False  # 是否跟踪展开过程
        self.error_mode = self.STRICT  # 错误恢复策略
        self.expansion_errors = []  # 展开过程中的错误列表
        self._call_stack = []  # 宏展开调用栈

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
        # 记录调用栈
        stack_entry = {
            "name": call.name,
            "line": getattr(call, 'line', 0),
            "column": getattr(call, 'column', 0),
            "depth": recursion_depth,
        }
        self._call_stack.append(stack_entry)

        try:
            return self._do_expand_macro_call(call, recursion_depth)
        finally:
            self._call_stack.pop()

    def _do_expand_macro_call(self, call: MacroCall, recursion_depth: int):
        """宏调用的实际展开逻辑"""
        try:
            # 查找宏定义
            macro_info = self.registry.find_macro(call.name)
            if not macro_info:
                return call

            # 模式匹配宏分支
            if macro_info.is_pattern_macro:
                return self._expand_pattern_macro(call, macro_info, recursion_depth)

            logger.debug("展开宏调用: !%s%s (深度=%d)", call.name, call.arguments, recursion_depth)
            self._log_trace("开始展开", call.name, f"深度={recursion_depth}")

            # 检测递归宏调用：如果宏体中包含对自身的调用，
            # 则只做参数替换，不递归展开，让解释器在运行时处理递归
            if self._is_recursive_macro(macro_info, call.name):
                logger.debug("检测到递归宏 '%s'，仅做参数替换", call.name)
                self._log_trace("递归检测", call.name, "仅做参数替换")
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
            self._log_trace("完成展开", call.name, f"结果类型={type(expanded).__name__}")

            return expanded

        except Exception as e:
            # 记录展开错误，包含位置信息
            line = getattr(call, 'line', 0)
            column = getattr(call, 'column', 0)
            error_info = {
                "macro_name": call.name,
                "line": line,
                "column": column,
                "error": e,
            }
            self.expansion_errors.append(error_info)

            if self.error_mode == self.PERMISSIVE:
                # 宽松模式：跳过出错的宏，返回原始调用
                logger.warning(
                    "宏 '!%s' 展开失败（行 %d, 列 %d）: %s，跳过展开",
                    call.name, line, column, e,
                )
                return call
            else:
                # 严格模式：重新抛出异常，附加位置信息
                from ..errors import 宏展开错误
                raise 宏展开错误(
                    f"宏 '!{call.name}' 展开失败: {e}",
                    line,
                    column,
                    "",
                )

    def _expand_pattern_macro(self, call: MacroCall, macro_info: MacroInfo, recursion_depth: int):
        """展开模式匹配宏：将宏调用展开为等价的 MatchStmt"""
        from ..ast_nodes import MatchCase, MatchStmt, VariableDecl

        # 构建等价的 MatchStmt
        subject = Identifier(name=macro_info.parameters[0].split('=')[0].strip())
        cases = []

        for branch in macro_info.branches:
            case = MatchCase(
                pattern=branch.pattern,
                guard=branch.guard,
                body=branch.body.body,  # QuoteBlock.body → list[Statement]
                is_wildcard=isinstance(branch.pattern, Identifier) and branch.pattern.name == "_",
                line=branch.line,
                column=branch.column,
            )
            cases.append(case)

        match_stmt = MatchStmt(
            subject=subject,
            cases=cases,
            line=call.line,
            column=call.column,
        )

        # 将宏调用参数绑定到匹配主题
        # 例如：!描述(0) → 设 值 = 0; 匹配 值 ...
        bindings = {}
        for i, param in enumerate(macro_info.parameters):
            param_name = param.split('=')[0].strip()
            if i < len(call.arguments):
                bindings[param_name] = call.arguments[i]

        # 创建参数绑定语句 + MatchStmt
        result_stmts = []
        for param_name, arg_expr in bindings.items():
            result_stmts.append(VariableDecl(
                name=param_name,
                value=arg_expr,
                line=call.line,
                column=call.column,
            ))
        result_stmts.append(match_stmt)

        return result_stmts

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
        if enabled:
            self._trace_log = []
        else:
            self._trace_log = None

    def get_trace_log(self):
        """获取展开追踪日志"""
        return getattr(self, '_trace_log', None)

    def get_call_stack(self):
        """获取当前宏展开调用栈

        Returns:
            list[dict]: 调用栈列表，每个元素包含 name, line, column, depth
        """
        return list(self._call_stack)

    def format_call_stack(self) -> str:
        """格式化宏展开调用栈为可读字符串

        Returns:
            str: 格式化的调用栈信息
        """
        if not self._call_stack:
            return "宏调用栈为空"

        lines = ["宏展开调用栈:"]
        for i, entry in enumerate(self._call_stack):
            indent = "  " * i
            name = entry.get("name", "?")
            line = entry.get("line", 0)
            column = entry.get("column", 0)
            depth = entry.get("depth", 0)
            lines.append(
                f"{indent}[{i}] !{name} (行 {line}, 列 {column}, 深度 {depth})"
            )
        return "\n".join(lines)

    def _log_trace(self, phase: str, macro_name: str, detail: str = ""):
        """记录展开追踪信息"""
        if self.trace_expansion and hasattr(self, '_trace_log'):
            self._trace_log.append({
                "phase": phase,
                "macro": macro_name,
                "detail": detail,
            })
            logger.debug("[宏追踪] %s: %s %s", phase, macro_name, detail)

    @staticmethod
    def ast_diff(before, after) -> list[str]:
        """比较两个 AST 节点的差异

        Args:
            before: 展开前的 AST 节点
            after: 展开后的 AST 节点

        Returns:
            差异描述列表
        """
        diffs = []

        def node_summary(node) -> str:
            if node is None:
                return "None"
            if isinstance(node, list):
                return f"[{', '.join(node_summary(n) for n in node)}]"
            type_name = type(node).__name__
            if hasattr(node, 'name'):
                return f"{type_name}({node.name})"
            if hasattr(node, 'value') and isinstance(node.value, (str, int, float, bool)):
                return f"{type_name}({node.value})"
            return type_name

        before_summary = node_summary(before)
        after_summary = node_summary(after)

        if before_summary != after_summary:
            diffs.append(f"  展开前: {before_summary}")
            diffs.append(f"  展开后: {after_summary}")
        else:
            diffs.append(f"  无变化: {before_summary}")

        return diffs

    def register_builtin_macros(self):
        """注册内置宏"""
        from .builtins import register_builtin_macros
        register_builtin_macros(self.registry)

    def __repr__(self):
        return f"MacroExpander(注册表={self.registry})"
