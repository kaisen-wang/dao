"""
AST内省接口
============

提供对AST节点的深入分析和查询功能，支持：

1. 类型信息查询
2. 节点关系分析
3. 代码结构查询
4. 变量使用分析
5. 控制流查询

这些功能为宏系统的高级特性提供支持，如类型检查增强和编译期分析。
"""

from typing import Any

from ..ast_nodes import (
    AssertStmt,
    Assignment,
    AsyncFunctionDecl,
    AwaitExpr,
    BooleanLiteral,
    BreakStmt,
    ChannelExpr,
    ClassDecl,
    ContinueStmt,
    ForInStmt,
    ForRangeStmt,
    FunctionCall,
    FunctionDecl,
    Identifier,
    IfStmt,
    LogicBlock,
    LogicFact,
    LogicQuery,
    LogicRule,
    MacroCall,
    MacroDefinition,
    NullLiteral,
    NumberLiteral,
    QuoteBlock,
    ReceiveExpr,
    ReturnStmt,
    SelectCase,
    SelectStmt,
    SendStmt,
    StringLiteral,
    ThrowStmt,
    TryStmt,
    UnquoteExpr,
    VariableDecl,
    WhileStmt,
)
from .ast_ops import ASTOperations


class ASTIntrospector:
    """AST内省接口"""

    def __init__(self, node: Any):
        self.node = node

    # ========================
    # 基本查询方法
    # ========================

    def get_node_type(self) -> str:
        """获取节点类型名称"""
        return type(self.node).__name__

    def get_node_count(self) -> int:
        """获取节点总数"""
        return ASTOperations.count_nodes(self.node)

    def get_depth(self) -> int:
        """获取树深度"""
        return ASTOperations.get_node_depth(self.node)

    def find_by_type(self, node_type: type) -> list[Any]:
        """查找特定类型的节点"""
        return ASTOperations.find_nodes(self.node, node_type)

    # ========================
    # 表达式查询
    # ========================

    def get_all_variables(self) -> list[Identifier]:
        """获取所有变量引用"""
        return self.find_by_type(Identifier)

    def get_all_literals(self) -> list[Any]:
        """获取所有字面量"""
        literals = []
        for literal_type in [NumberLiteral, StringLiteral, BooleanLiteral, NullLiteral]:
            literals.extend(self.find_by_type(literal_type))
        return literals

    def get_function_calls(self) -> list[FunctionCall]:
        """获取所有函数调用"""
        return self.find_by_type(FunctionCall)

    def get_macro_calls(self) -> list[MacroCall]:
        """获取所有宏调用"""
        return self.find_by_type(MacroCall)

    def get_quote_blocks(self) -> list[QuoteBlock]:
        """获取所有引述块"""
        return self.find_by_type(QuoteBlock)

    def get_unquote_exprs(self) -> list[UnquoteExpr]:
        """获取所有注入表达式"""
        return self.find_by_type(UnquoteExpr)

    # ========================
    # 语句查询
    # ========================

    def get_variable_definitions(self) -> list[VariableDecl]:
        """获取所有变量定义"""
        return self.find_by_type(VariableDecl)

    def get_constant_definitions(self) -> list[VariableDecl]:
        """获取所有常量定义"""
        # 在当前实现中，常量也是 VariableDecl，只是 is_constant=True
        return [decl for decl in self.find_by_type(VariableDecl) if decl.is_constant]

    def get_function_definitions(self) -> list[FunctionDecl]:
        """获取所有函数定义"""
        return self.find_by_type(FunctionDecl)

    def get_macro_definitions(self) -> list[MacroDefinition]:
        """获取所有宏定义"""
        return self.find_by_type(MacroDefinition)

    def get_class_definitions(self) -> list[ClassDecl]:
        """获取所有类定义"""
        return self.find_by_type(ClassDecl)

    # ========================
    # 控制流查询
    # ========================

    def get_if_statements(self) -> list[IfStmt]:
        """获取所有if语句"""
        return self.find_by_type(IfStmt)

    def get_loop_statements(self) -> list[Any]:
        """获取所有循环语句"""
        loops = []
        for loop_type in [WhileStmt, ForInStmt, ForRangeStmt]:
            loops.extend(self.find_by_type(loop_type))
        return loops

    def get_try_statements(self) -> list[TryStmt]:
        """获取所有try语句"""
        return self.find_by_type(TryStmt)

    def get_switch_statements(self) -> list[dict]:
        """获取所有switch语句（匹配/情况）"""
        matches = self.find_by_type(SelectStmt)
        cases = self.find_by_type(SelectCase)
        return {"matches": matches, "cases": cases}

    # ========================
    # 逻辑编程查询
    # ========================

    def get_logic_blocks(self) -> list[LogicBlock]:
        """获取所有逻辑块"""
        return self.find_by_type(LogicBlock)

    def get_logic_queries(self) -> list[LogicQuery]:
        """获取所有查询"""
        return self.find_by_type(LogicQuery)

    def get_logic_rules(self) -> list[LogicRule]:
        """获取所有规则"""
        return self.find_by_type(LogicRule)

    def get_logic_facts(self) -> list[LogicFact]:
        """获取所有事实"""
        return self.find_by_type(LogicFact)

    # ========================
    # 并发编程查询
    # ========================

    def get_async_functions(self) -> list[AsyncFunctionDecl]:
        """获取所有异步函数"""
        return self.find_by_type(AsyncFunctionDecl)

    def get_await_expressions(self) -> list[AwaitExpr]:
        """获取所有await表达式"""
        return self.find_by_type(AwaitExpr)

    def get_channel_expressions(self) -> list[ChannelExpr]:
        """获取所有通道表达式"""
        return self.find_by_type(ChannelExpr)

    def get_send_receive_operations(self) -> list[Any]:
        """获取发送和接收操作"""
        return self.find_by_type(SendStmt) + self.find_by_type(ReceiveExpr)

    # ========================
    # 高级分析方法
    # ========================

    def get_variable_usage(self) -> dict[str, list[Identifier]]:
        """获取变量使用情况统计"""
        usage = {}
        for var in self.get_all_variables():
            name = var.name
            if name not in usage:
                usage[name] = []
            usage[name].append(var)
        return usage

    def get_free_variables(self, scope: Any = None) -> set[str]:
        """获取自由变量"""
        definitions = set()
        references = set()

        # 收集定义的变量
        for definition in (
            self.get_variable_definitions() + self.get_constant_definitions()
        ):
            definitions.add(definition.name)

        # 收集使用的变量
        for var in self.get_all_variables():
            references.add(var.name)

        return references - definitions

    def get_function_dependencies(self) -> list[str]:
        """获取函数依赖关系"""
        calls = self.get_function_calls()
        functions = self.get_function_definitions()

        dependencies = set()
        function_names = {f.name for f in functions}

        for call in calls:
            if call.callee and hasattr(call.callee, "name"):
                name = call.callee.name
                if name in function_names:
                    dependencies.add(name)

        return list(dependencies)

    def analyze_control_flow(self) -> dict[str, Any]:
        """分析控制流结构"""
        return {
            "if_count": len(self.get_if_statements()),
            "loop_count": len(self.get_loop_statements()),
            "function_count": len(self.get_function_definitions()),
            "macro_count": len(self.get_macro_definitions()),
            "return_count": len(self.find_by_type(ReturnStmt)),
            "break_count": len(self.find_by_type(BreakStmt)),
            "continue_count": len(self.find_by_type(ContinueStmt)),
        }

    def has_side_effects(self) -> bool:
        """分析是否有副作用"""
        has_assignments = len(self.find_by_type(Assignment)) > 0
        has_throw = len(self.find_by_type(ThrowStmt)) > 0
        has_assert = len(self.find_by_type(AssertStmt)) > 0
        has_send_receive = len(self.get_send_receive_operations()) > 0

        return has_assignments or has_throw or has_assert or has_send_receive

    # ========================
    # 代码复杂度分析
    # ========================

    def calculate_cyclomatic_complexity(self) -> int:
        """计算圈复杂度（简单实现）"""
        complexity = 1
        complexity += len(self.get_if_statements())
        complexity += len(self.get_loop_statements())
        complexity += len(self.get_switch_statements()["matches"])
        return complexity

    def calculate_maintainability_index(self) -> float:
        """计算可维护性指数（简单实现）"""
        try:
            code_length = len(str(self.node))
            complexity = self.calculate_cyclomatic_complexity()
            comment_density = 0  # 简单实现

            index = (
                171
                - (3.42 * complexity)
                - (0.015 * code_length)
                - (50.0 * comment_density)
            )
            return max(0, min(100, index))
        # 指标计算失败时返回默认分；保留裸 except 以维持现有异常兜底语义（不改异常传播）
        except:  # noqa: E722
            return 0.0

    def print_statistics(self):
        """打印统计信息"""
        print(f"节点类型: {self.get_node_type()}")
        print(f"总节点数: {self.get_node_count()}")
        print(f"树深度: {self.get_depth()}")
        print(f"变量定义: {len(self.get_variable_definitions())}")
        print(f"变量使用: {len(self.get_all_variables())}")
        print(f"函数定义: {len(self.get_function_definitions())}")
        print(f"函数调用: {len(self.get_function_calls())}")
        print(f"宏定义: {len(self.get_macro_definitions())}")
        print(f"宏调用: {len(self.get_macro_calls())}")
        print(f"类定义: {len(self.get_class_definitions())}")
        print(f"圈复杂度: {self.calculate_cyclomatic_complexity()}")
        print(f"可维护性指数: {self.calculate_maintainability_index():.1f}")

        if self.get_free_variables():
            print(f"自由变量: {', '.join(self.get_free_variables())}")

    # ========================
    # 可视化方法
    # ========================

    def print_tree(self, indent: int = 0):
        """打印AST树结构"""
        print("  " * indent + type(self.node).__name__)
        if hasattr(self.node, "__dict__"):
            for attr_name in dir(self.node):
                if not attr_name.startswith("__") and hasattr(self.node, attr_name):
                    attr_value = getattr(self.node, attr_name)
                    if not callable(attr_value) and attr_value is not None:
                        if isinstance(attr_value, list):
                            if attr_value:
                                print("  " * (indent + 1) + f"{attr_name}: [")
                                for item in attr_value:
                                    if hasattr(item, "__dict__"):
                                        ASTIntrospector(item).print_tree(indent + 2)
                                    else:
                                        print("  " * (indent + 2) + str(item))
                                print("  " * (indent + 1) + "]")
                        elif hasattr(attr_value, "__dict__"):
                            print("  " * (indent + 1) + f"{attr_name}:")
                            ASTIntrospector(attr_value).print_tree(indent + 2)
                        else:
                            print("  " * (indent + 1) + f"{attr_name}: {attr_value}")
