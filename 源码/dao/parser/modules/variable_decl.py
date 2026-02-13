"""变量/常量声明解析混入"""

from ...ast_nodes import DestructureAssign, Identifier, ListLiteral, VariableDecl
from ...errors import 语法错误
from ...tokens import Token, TokenType


class VariableDeclParser:
    """变量/常量声明解析方法集"""

    def parse_variable_decl(
        self, is_constant: bool
    ) -> VariableDecl | DestructureAssign:
        """解析变量/常量声明：定义 x = 值 或 定义 [甲, 乙] = 值"""
        token = self.advance()  # 消费 定义/常量

        # 检查是否是解构赋值：定义 [甲, 乙] = ...
        if self.current.type == TokenType.左方括号:
            return self._parse_destructure_decl(token, is_constant)

        name_token = self.expect(TokenType.标识符, "变量声明需要一个变量名")
        self.expect(TokenType.赋值, "变量声明需要 '=' 赋值")
        value = self.parse_expression()
        # 允许可选的换行符，不强制要求
        self.match(TokenType.换行)
        return VariableDecl(
            name=name_token.value,
            value=value,
            is_constant=is_constant,
            line=token.line,
            column=token.column,
        )

    def _parse_destructure_decl(self, token, is_constant: bool) -> DestructureAssign:
        """解析解构声明：定义 [甲, 乙] = [1, 2]"""
        self.advance()  # 消费 [
        targets = []
        while self.current.type != TokenType.右方括号:
            name = self.expect(TokenType.标识符, "解构赋值需要变量名")
            targets.append(name.value)
            if not self.match(TokenType.逗号):
                break
        self.expect(TokenType.右方括号, "解构赋值需要 ']'")
        self.expect(TokenType.赋值, "解构赋值需要 '='")
        value = self.parse_expression()
        # 允许可选的换行符，不强制要求
        self.match(TokenType.换行)
        return DestructureAssign(
            targets=targets,
            value=value,
            is_declaration=True,
            line=token.line,
            column=token.column,
        )
