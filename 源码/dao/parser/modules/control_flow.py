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

        # 检查当前是否在引号块中（通过调用堆栈判断）
        import inspect

        is_in_quote_block = False
        for frame in inspect.stack():
            if "parse_quote_block" in frame.function:
                is_in_quote_block = True
                break

        if not is_in_quote_block:
            self.expect(TokenType.换行, "条件后需要换行")

        body = self.parse_block()

        elif_clauses = []
        else_body = []

        self.skip_newlines()
        while self.match(TokenType.否则如果):
            elif_cond = self.parse_expression()

            if not is_in_quote_block:
                self.expect(TokenType.换行, "条件后需要换行")

            elif_body = self.parse_block()
            elif_clauses.append((elif_cond, elif_body))
            self.skip_newlines()

        if self.match(TokenType.否则):
            if not is_in_quote_block:
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

        logger.debug(f"=== parse_while_stmt ===")
        logger.debug(f"  condition parsed, current pos: {self.pos}")
        logger.debug(f"  current token: {self.current.type.name} '{self.current.value}'")

        # 在引号块中不需要强制换行
        if self.current.type != TokenType.左花括号:
            self.expect(TokenType.换行, "条件后需要换行")

        logger.debug(f"  calling parse_block at pos: {self.pos}")

        # 检查是否已经是左花括号，如果是，不应该通过 match 消费，直接传递给 parse_block
        if self.current.type == TokenType.左花括号:
            # 直接调用内部的解析逻辑，避免再次调用 match 消费左花括号
            statements = []
            self.advance()  # 消费左花括号

            logger.debug(
                f"parse_block 开始解析，pos={self.pos}, current token: {self.tokens[self.pos].type.name} -> '{self.tokens[self.pos].value}'"
            )

            while (
                not self.match(TokenType.右花括号)
                and self.current.type != TokenType.文件结束
            ):
                # 跳过换行或缩进
                if self.current.type in (TokenType.换行, TokenType.缩进):
                    logger.debug(f"parse_block 跳过换行/缩进，pos={self.pos}")
                    self.advance()
                    continue

                if (
                    self.match(TokenType.右花括号)
                    or self.current.type == TokenType.文件结束
                ):
                    break

                # 特别处理 $块 标识符，确保它被正确解析
                if (
                    self.current.type == TokenType.标识符
                    and self.current.value == "$块"
                ):
                    logger.debug(f"parse_block 找到 $块，pos={self.pos}")
                    from ...ast_nodes import ExpressionStmt

                    expr = self.parse_primary()
                    stmt = ExpressionStmt(
                        expression=expr,
                        line=self.current.line,
                        column=self.current.column,
                    )
                    statements.append(stmt)
                    logger.debug(f"parse_block 添加 $块 语句，type={type(stmt).__name__}")
                    continue

                # 处理其他以 $ 开头的标识符
                elif (
                    self.current.type == TokenType.标识符
                    and self.current.value.startswith("$")
                ):
                    logger.debug(
                        f"parse_block 找到 $ 标识符，value={self.current.value}, pos={self.pos}"
                    )
                    from ...ast_nodes import ExpressionStmt

                    expr = self.parse_primary()
                    stmt = ExpressionStmt(
                        expression=expr,
                        line=self.current.line,
                        column=self.current.column,
                    )
                    statements.append(stmt)

                else:
                    logger.debug(
                        f"parse_block 解析语句，pos={self.pos}, type={self.current.type.name}"
                    )
                    stmt = self.parse_statement()
                    if stmt:
                        statements.append(stmt)
                        logger.debug(f"parse_block 添加语句，type={type(stmt).__name__}")
                    else:
                        logger.debug(f"parse_block 跳过无效语句，pos={self.pos}")
                        self.advance()

            logger.debug(f"parse_block 结束解析，共 {len(statements)} 个语句")
            self.advance()  # 消费右花括号
            body = statements
        else:
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
