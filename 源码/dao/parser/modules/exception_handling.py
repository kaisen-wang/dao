"""异常处理解析混入"""

from ...ast_nodes import AssertStmt, ThrowStmt, TryStmt
from ...tokens import TokenType


class ExceptionHandlingParser:
    """异常处理解析方法集"""

    def parse_try_stmt(self) -> TryStmt:
        """解析尝试-捕获-最终"""
        token = self.advance()  # 消费 尝试
        self.expect(TokenType.换行, "'尝试' 后需要换行")
        try_body = self.parse_block()

        catches = []
        finally_body = []

        self.skip_newlines()
        while self.match(TokenType.捕获):
            catch_var = None
            catch_body = []
            error_type = None

            # 检查是否是类型化捕获：捕获 错误类型: 变量名 或 捕获 变量名
            if self.current.type == TokenType.标识符:
                # 检查下一个 token 是否是冒号，以确定是类型化捕获还是简单捕获
                next_token = self.peek()
                if next_token and next_token.type == TokenType.冒号:
                    # 类型化捕获：捕获 错误类型: 变量名
                    error_type = self.advance().value
                    self.advance()  # 消费冒号
                    catch_var = self.expect(TokenType.标识符, "期望捕获变量名").value
                else:
                    # 简单捕获：捕获 变量名（无类型指定）
                    catch_var = self.advance().value
            elif self.match(TokenType.冒号):
                # 捕获: 变量名（无类型指定）
                catch_var = self.expect(TokenType.标识符, "期望捕获变量名").value
            self.expect(TokenType.换行, "'捕获' 后需要换行")
            catch_body = self.parse_block()

            catches.append(
                {
                    "catch_var": catch_var,
                    "catch_body": catch_body,
                    "error_type": error_type,
                }
            )

            self.skip_newlines()

        if self.match(TokenType.最终):
            self.expect(TokenType.换行, "'最终' 后需要换行")
            finally_body = self.parse_block()

        return TryStmt(
            try_body=try_body,
            catches=catches,
            finally_body=finally_body,
            line=token.line,
            column=token.column,
        )

    def parse_throw_stmt(self) -> ThrowStmt:
        token = self.advance()  # 消费 抛出
        expr = self.parse_expression()
        self.match(TokenType.换行)
        return ThrowStmt(expression=expr, line=token.line, column=token.column)

    def parse_assert_stmt(self) -> AssertStmt:
        token = self.advance()  # 消费 断言
        condition = None
        message = None

        # 尝试解析断言条件
        if self.current.type == TokenType.标识符 and self.peek().type == TokenType.等于:
            # 简单的断言表达式： 变量 = 表达式
            var_token = self.advance()
            self.advance()  # 消费 等于
            condition = self.parse_expression()
        else:
            # 普通的断言表达式
            condition = self.parse_expression()

        if self.match(TokenType.逗号):
            message = self.parse_expression()
        self.match(TokenType.换行)
        return AssertStmt(
            condition=condition,
            message=message,
            line=token.line,
            column=token.column,
        )

    # OOP 解析
