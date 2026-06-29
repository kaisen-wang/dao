"""表达式和赋值解析混入"""

from ...ast_nodes import (
    Assignment,
    DestructureAssign,
    DestructureTarget,
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

        if self.match(TokenType.赋值):
            if isinstance(expr, ListLiteral):
                targets = []
                pattern = self._build_list_pattern_from_list_literal(expr)
                for elem in expr.elements:
                    if not isinstance(elem, Identifier):
                        raise self._error("解构赋值的目标必须是变量名")
                    targets.append(elem.name)
                value = self.parse_expression()
                while self.current.type in (TokenType.换行, TokenType.缩进):
                    self.advance()
                return DestructureAssign(
                    targets=targets,
                    value=value,
                    is_declaration=False,
                    pattern=pattern,
                    line=expr.line,
                    column=expr.column,
                )
            value = self.parse_expression()
            while self.current.type in (TokenType.换行, TokenType.缩进):
                self.advance()
            return Assignment(
                target=expr,
                value=value,
                line=expr.line,
                column=expr.column,
            )

        from ...ast_nodes import MacroCall

        if isinstance(expr, MacroCall) and self.current.type == TokenType.左花括号:
            print(
                f"  [parse_expression_or_assignment] Found left curly brace for block"
            )

            self.advance()

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

        while self.current.type in (TokenType.换行, TokenType.缩进):
            self.advance()

        return ExpressionStmt(
            expression=expr,
            line=expr.line,
            column=expr.column,
        )

    def _build_list_pattern_from_list_literal(self, lit: ListLiteral) -> DestructureTarget:
        """从 ListLiteral 构建列表解构模式"""
        targets = []
        for elem in lit.elements:
            if isinstance(elem, Identifier):
                targets.append(DestructureTarget(name=elem.name))
            else:
                targets.append(DestructureTarget(name=str(elem)))
        return DestructureTarget(is_list=True, list_targets=targets)

    # 逻辑编程
