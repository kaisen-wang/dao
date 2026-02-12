"""
语句解析主入口
===========

这个文件将所有语句解析方法从各个模块导入，并通过多重继承组合到Parser类中。
"""

from ..tokens import TokenType
from ..ast_nodes import Statement

# 导入所有语句解析模块
from .modules import (
    VariableDeclParser,
    FunctionDeclParser,
    ControlFlowParser,
    ExceptionHandlingParser,
    OOPDeclParser,
    PatternMatchingParser,
    ModuleSystemParser,
    ExpressionAndAssignmentParser,
    LogicProgrammingParser,
)


class StatementParser(
    VariableDeclParser,
    FunctionDeclParser,
    ControlFlowParser,
    ExceptionHandlingParser,
    OOPDeclParser,
    PatternMatchingParser,
    ModuleSystemParser,
    ExpressionAndAssignmentParser,
    LogicProgrammingParser,
):
    """语句解析器 - 组合所有语句解析方法"""

    def parse_statement(self) -> Statement:
        """解析一条语句 - 根据当前token类型分派到相应的解析方法"""
        token = self.current

        match token.type:
            case TokenType.定义:
                return self.parse_variable_decl(is_constant=False)
            case TokenType.常量:
                return self.parse_variable_decl(is_constant=True)
            case TokenType.函数:
                return self.parse_function_decl()
            case TokenType.抽象:
                return self.parse_abstract_decl()
            case TokenType.类型:
                return self.parse_class_decl()
            case TokenType.枚举:
                return self.parse_enum_decl()
            case TokenType.特征:
                return self.parse_trait_decl()
            case TokenType.返回:
                return self.parse_return_stmt()
            case TokenType.产出:
                return self.parse_yield_stmt()
            case TokenType.如果:
                return self.parse_if_stmt()
            case TokenType.当:
                return self.parse_while_stmt()
            case TokenType.遍历:
                return self.parse_for_stmt()
            case TokenType.跳出:
                return self.parse_break_stmt()
            case TokenType.继续:
                return self.parse_continue_stmt()
            case TokenType.尝试:
                return self.parse_try_stmt()
            case TokenType.抛出:
                return self.parse_throw_stmt()
            case TokenType.断言:
                return self.parse_assert_stmt()
            case TokenType.匹配:
                return self.parse_match_stmt()
            case TokenType.逻辑:
                return self.parse_logic_block()
            case TokenType.导入:
                return self.parse_import_stmt()
            case TokenType.导出:
                return self.parse_export_stmt()
            case TokenType.从:
                self.advance()  # 消费 "从"
                return self.parse_import_stmt(is_from_import=True)
            case _:
                return self.parse_expression_or_assignment()
