"""表达式和赋值解析混入"""

from ...ast_nodes import (
    Assignment,
    DestructureAssign,
    ExpressionStmt,
    Identifier,
    ListLiteral,
    Statement,
)
from ...tokens import TokenType


class ExpressionAndAssignmentParser:
    """表达式和赋值解析方法集"""

    def parse_expression_or_assignment(self) -> Statement:
        """解析表达式语句或赋值语句"""
        expr = self.parse_expression()

        # 检查是否为解构赋值：[甲, 乙] = ...
        if self.match(TokenType.赋值):
            if isinstance(expr, ListLiteral):
                # 列表解构赋值
                targets = []
                for elem in expr.elements:
                    if not isinstance(elem, Identifier):
                        raise self._error("解构赋值的目标必须是变量名")
                    targets.append(elem.name)
                value = self.parse_expression()
                # 不强制要求换行，接受后面可能跟的其他内容
                while self.current.type in (TokenType.换行, TokenType.缩进):
                    self.advance()
                return DestructureAssign(
                    targets=targets,
                    value=value,
                    is_declaration=False,
                    line=expr.line,
                    column=expr.column,
                )
            # 普通赋值
            value = self.parse_expression()
            # 不强制要求换行，接受后面可能跟的其他内容
            while self.current.type in (TokenType.换行, TokenType.缩进):
                self.advance()
            return Assignment(
                target=expr,
                value=value,
                line=expr.line,
                column=expr.column,
            )

        # 检查 expr 是否是 MacroCall，且后面是否紧跟块参数 { ... }
        from ...ast_nodes import MacroCall

        if isinstance(expr, MacroCall) and self.current.type == TokenType.左花括号:
            print(
                f"  [parse_expression_or_assignment] Found left curly brace for block"
            )

            # 解析块内容
            self.advance()  # 消费左花括号

            # 找到匹配的右花括号
            depth = 1
            block_end = self.pos
            while block_end < len(self.tokens):
                if self.tokens[block_end].type == TokenType.左花括号:
                    depth += 1
                elif self.tokens[block_end].type == TokenType.右花括号:
                    depth -= 1
                    if depth == 0:
                        print(
                            f"  [parse_expression_or_assignment] Block found from {self.pos} to {block_end}"
                        )
                        break
                block_end += 1

            if block_end < len(self.tokens):
                from ...ast_nodes import BlockExpr

                block_body = []

                while self.pos < block_end:
                    stmt = self.parse_statement()
                    if stmt:
                        block_body.append(stmt)

                expr.arguments.append(BlockExpr(body=block_body))
                self.pos = block_end + 1

        # 不强制要求换行，接受后面可能跟的其他内容
        while self.current.type in (TokenType.换行, TokenType.缩进):
            self.advance()

        return ExpressionStmt(
            expression=expr,
            line=expr.line,
            column=expr.column,
        )

    # 逻辑编程
