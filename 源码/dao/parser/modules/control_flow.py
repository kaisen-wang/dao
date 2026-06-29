"""控制流解析混入"""

import logging

logger = logging.getLogger('dao.parser')

from ...ast_nodes import (
    BreakStmt,
    ContinueStmt,
    ForInStmt,
    ForRangeStmt,
    IfStmt,
    WhileStmt,
)
from ...tokens import TokenType


class ControlFlowParser:
    """控制流解析方法集"""

    def parse_if_stmt(self) -> IfStmt:
        """解析条件语句"""
        token = self.advance()  # 消费 如果
        condition = self.parse_expression()

        # 条件后期望换行（统一缩进风格）
        self.expect(TokenType.换行, "条件后需要换行")

        body = self.parse_block()

        elif_clauses = []
        else_body = []

        self.skip_newlines()
        while self.match(TokenType.否则如果):
            elif_cond = self.parse_expression()
            self.expect(TokenType.换行, "条件后需要换行")
            elif_body = self.parse_block()
            elif_clauses.append((elif_cond, elif_body))
            self.skip_newlines()

        if self.match(TokenType.否则):
            self.expect(TokenType.换行, "'否则' 后需要换行")
            else_body = self.parse_block()

        return IfStmt(
            condition=condition,
            body=body,
            elif_clauses=elif_clauses,
            else_body=else_body,
            line=token.line,
            column=token.column,
        )

    def parse_while_stmt(self) -> WhileStmt:
        """解析当循环"""
        token = self.advance()  # 消费 当
        condition = self.parse_expression()

        logger.debug("=== parse_while_stmt ===")

        self.expect(TokenType.换行, "条件后需要换行")

        body = self.parse_block()

        return WhileStmt(
            condition=condition,
            body=body,
            line=token.line,
            column=token.column,
        )

    def parse_for_stmt(self) -> ForInStmt | ForRangeStmt:
        """解析遍历循环（遍历...在... 或 遍历...从...到... 或 对于...）"""
        token = self.advance()  # 消费 遍历 或 对于
        var_token = self.expect(TokenType.标识符, "遍历需要一个循环变量名")

        if self.match(TokenType.在):
            # 遍历 x 在 集合
            iterable = self.parse_expression()
            self.expect(TokenType.换行, "遍历语句后需要换行")
            body = self.parse_block()
            return ForInStmt(
                variable=var_token.value,
                iterable=iterable,
                body=body,
                line=token.line,
                column=token.column,
            )
        elif self.match(TokenType.逗号):
            # 遍历 键, 值 在 字典
            second_var = self.expect(TokenType.标识符, "遍历需要第二个变量名")
            self.expect(TokenType.在, "遍历双变量需要 '在'")
            iterable = self.parse_expression()
            self.expect(TokenType.换行, "遍历语句后需要换行")
            body = self.parse_block()
            return ForInStmt(
                variable=var_token.value,
                second_variable=second_var.value,
                iterable=iterable,
                body=body,
                line=token.line,
                column=token.column,
            )
        elif self.match(TokenType.从):
            # 遍历 i 从 1 到 10 [步长 2]
            start = self.parse_expression()
            self.expect(TokenType.到, "范围循环需要 '到'")
            end = self.parse_expression()
            step = None
            if self.match(TokenType.步长):
                step = self.parse_expression()
            self.expect(TokenType.换行, "遍历语句后需要换行")
            body = self.parse_block()
            return ForRangeStmt(
                variable=var_token.value,
                start=start,
                end=end,
                step=step,
                body=body,
                line=token.line,
                column=token.column,
            )
        else:
            raise self._error("遍历后需要 '在' 或 '从'")

    def parse_break_stmt(self) -> BreakStmt:
        token = self.advance()
        self.match(TokenType.换行)
        return BreakStmt(line=token.line, column=token.column)

    def parse_continue_stmt(self) -> ContinueStmt:
        token = self.advance()
        self.match(TokenType.换行)
        return ContinueStmt(line=token.line, column=token.column)

    # 错误处理
