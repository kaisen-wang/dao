"""表达式和赋值解析混入"""

from ...tokens import TokenType
from ...ast_nodes import Statement, Assignment, ExpressionStmt, DestructureAssign, ListLiteral, Identifier


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
                self.match(TokenType.换行)
                return DestructureAssign(
                    targets=targets,
                    value=value,
                    is_declaration=False,
                    line=expr.line,
                    column=expr.column,
                )
            # 普通赋值
            value = self.parse_expression()
            self.match(TokenType.换行)
            return Assignment(
                target=expr,
                value=value,
                line=expr.line,
                column=expr.column,
            )

        self.match(TokenType.换行)
        return ExpressionStmt(
            expression=expr,
            line=expr.line,
            column=expr.column,
        )

    # 逻辑编程

