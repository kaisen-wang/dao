"""变量/常量声明解析混入"""

from ...ast_nodes import DestructureAssign, Identifier, ListLiteral, VariableDecl
from ...errors import 语法错误
from ...tokens import Token, TokenType


class VariableDeclParser:
    """变量/常量声明解析方法集"""

    def parse_variable_decl(
        self, is_constant: bool
    ) -> VariableDecl | DestructureAssign:
        """解析变量/常量声明：定义 x = 值 或 定义 [甲, 乙] = 值 或 定义 {姓名, 年龄} = 值"""
        token = self.advance()  # 消费 定义/常量

        # 检查是否是列表解构赋值：定义 [甲, 乙] = ...
        if self.current.type == TokenType.左方括号:
            return self._parse_destructure_decl(token, is_constant)

        # 检查是否是字典解构赋值：定义 {姓名, 年龄} = ...
        if self.current.type == TokenType.左花括号:
            return self._parse_dict_destructure_decl(token, is_constant)

        name_token = self.expect(TokenType.标识符, "变量声明需要一个变量名")
        self.expect(TokenType.赋值, "变量声明需要 '=' 赋值")
        value = self.parse_expression()
        self.match(TokenType.换行)
        return VariableDecl(
            name=name_token.value,
            value=value,
            is_constant=is_constant,
            line=token.line,
            column=token.column,
        )

    def _parse_dict_destructure_decl(self, token, is_constant: bool) -> DestructureAssign:
        """解析字典解构声明：定义 {姓名, 年龄} = 人 或 定义 {姓名: 名} = 人"""
        self.advance()  # 消费 {
        dict_targets = {}
        while self.current.type != TokenType.右花括号:
            key_token = self.expect(TokenType.标识符, "字典解构需要键名")
            key = key_token.value
            if self.match(TokenType.冒号):
                value_token = self.expect(TokenType.标识符, "字典解构需要变量名")
                dict_targets[key] = value_token.value
            else:
                dict_targets[key] = key
            if not self.match(TokenType.逗号):
                break
        self.expect(TokenType.右花括号, "字典解构需要 '}'")
        self.expect(TokenType.赋值, "字典解构需要 '='")
        value = self.parse_expression()
        self.match(TokenType.换行)
        return DestructureAssign(
            targets=[],
            value=value,
            is_declaration=True,
            dict_targets=dict_targets,
            is_dict_destructure=True,
            line=token.line,
            column=token.column,
        )

    def _parse_destructure_decl(self, token, is_constant: bool) -> DestructureAssign:
        """解析解构声明：定义 [甲, 乙, ...尾] = [1, 2, 3, 4]"""
        self.advance()  # 消费 [
        targets = []
        rest_target = None
        while self.current.type != TokenType.右方括号:
            if self.current.type == TokenType.展开:
                self.advance()  # 消费 ...
                rest_name = self.expect(TokenType.标识符, "展开操作符后需要变量名")
                rest_target = rest_name.value
                break
            name = self.expect(TokenType.标识符, "解构赋值需要变量名")
            targets.append(name.value)
            if not self.match(TokenType.逗号):
                break
        self.expect(TokenType.右方括号, "解构赋值需要 ']'")
        self.expect(TokenType.赋值, "解构赋值需要 '='")
        value = self.parse_expression()
        self.match(TokenType.换行)
        return DestructureAssign(
            targets=targets,
            value=value,
            is_declaration=True,
            rest_target=rest_target,
            line=token.line,
            column=token.column,
        )
