"""异常处理解析混入"""

from ...tokens import TokenType
from ...ast_nodes import TryStmt, ThrowStmt, AssertStmt


class ExceptionHandlingParser:
    """异常处理解析方法集"""

    def parse_try_stmt(self) -> TryStmt:
        """解析尝试-捕获-最终"""
        token = self.advance()  # 消费 尝试
        self.expect(TokenType.换行, "'尝试' 后需要换行")
        try_body = self.parse_block()

        catch_var = None
        catch_body = []
        finally_body = []

        self.skip_newlines()
        if self.match(TokenType.捕获):
            error_type = None
            # 检查是否是类型化捕获：捕获 异常: 错误类型
            if self.current.type == TokenType.标识符:
                catch_var = self.advance().value
                if self.match(TokenType.冒号):
                    error_type_token = self.expect(TokenType.标识符, "期望错误类型名称")
                    error_type = error_type_token.value
            self.expect(TokenType.换行, "'捕获' 后需要换行")
            catch_body = self.parse_block()

        self.skip_newlines()
        if self.match(TokenType.最终):
            self.expect(TokenType.换行, "'最终' 后需要换行")
            finally_body = self.parse_block()

        return TryStmt(
            try_body=try_body,
            catch_var=catch_var,
            catch_body=catch_body,
            error_type=error_type,
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
        condition = self.parse_expression()
        message = None
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

