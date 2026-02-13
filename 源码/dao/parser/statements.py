"""
语句解析主入口
===========

这个文件将所有语句解析方法从各个模块导入，并通过多重继承组合到Parser类中。
"""

from ..ast_nodes import Statement
from ..tokens import TokenType

# 导入所有语句解析模块
from .modules import (
    ConcurrencyParser,
    ControlFlowParser,
    ExceptionHandlingParser,
    ExpressionAndAssignmentParser,
    FunctionDeclParser,
    LogicProgrammingParser,
    ModuleSystemParser,
    OOPDeclParser,
    PatternMatchingParser,
    VariableDeclParser,
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
    ConcurrencyParser,
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
            case TokenType.异步:
                return self.parse_async_function_decl()
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
                # 只有在特定上下文中才是导入语句的 "从"，否则是 for 循环的 "从"
                # 检查前面是否有导入或导出关键字，或者后面是否紧跟模块名
                if self.peek().type == TokenType.标识符:
                    self.advance()  # 消费 "从"
                    return self.parse_import_stmt(is_from_import=True)
                else:
                    # 否则，这是 for 循环的一部分
                    return self.parse_for_stmt()
            case TokenType.并行:
                return self.parse_parallel_stmt()
            case TokenType.发送:
                # 只有后面不是左括号时才是发送语句
                # 如果是左括号，说明是函数调用：发送(...)
                if self.peek().type != TokenType.左括号:
                    return self.parse_send_stmt()
                else:
                    # 否则，'发送' 应该被视为函数调用的一部分
                    return self.parse_expression_or_assignment()
            case TokenType.选择:
                return self.parse_select_stmt()
            case TokenType.同步:
                return self.parse_sync_stmt()
            case _:
                return self.parse_expression_or_assignment()
