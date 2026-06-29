"""变量/常量声明解析混入"""

from ...ast_nodes import DestructureAssign, DestructureTarget, Identifier, ListLiteral, VariableDecl
from ...errors import 语法错误
from ...tokens import Token, TokenType


class VariableDeclParser:
    """变量/常量声明解析方法集"""

    def parse_variable_decl(
        self, is_constant: bool
    ) -> VariableDecl | DestructureAssign:
        """解析变量/常量声明：定义 x = 值 或 定义 x: 类型 = 值"""
        token = self.advance()  # 消费 定义/常量

        if self.current.type == TokenType.左方括号:
            return self._parse_destructure_decl(token, is_constant)

        if self.current.type == TokenType.左花括号:
            return self._parse_dict_destructure_decl(token, is_constant)

        if self.current.type == TokenType.左括号:
            return self._parse_tuple_destructure_decl(token, is_constant)

        name_token = self.expect(TokenType.标识符, "变量声明需要一个变量名")

        type_annotation = None
        if self.current.type == TokenType.冒号:
            self.advance()  # 消费 :
            type_annotation = self.parse_type_annotation()

        self.expect(TokenType.赋值, "变量声明需要 '=' 赋值")
        value = self.parse_expression()
        self.match(TokenType.换行)
        return VariableDecl(
            name=name_token.value,
            value=value,
            is_constant=is_constant,
            type_annotation=type_annotation,
            line=token.line,
            column=token.column,
        )

    def _parse_tuple_destructure_decl(self, token, is_constant: bool) -> DestructureAssign:
        """解析元组解构声明：定义 (甲, 乙) = 值"""
        pattern = self._parse_tuple_destructure_target()
        self.expect(TokenType.赋值, "元组解构需要 '='")
        value = self.parse_expression()
        self.match(TokenType.换行)
        flat_targets = []
        self._flatten_list_pattern(pattern, flat_targets)
        return DestructureAssign(
            targets=flat_targets,
            value=value,
            is_declaration=True,
            pattern=pattern,
            line=token.line,
            column=token.column,
        )

    def _parse_tuple_destructure_target(self) -> DestructureTarget:
        """递归解析元组解构目标：(甲, 乙) 或 (甲, [乙, 丙])"""
        self.advance()  # 消费 (
        targets = []
        while self.current.type != TokenType.右括号:
            if self.current.type == TokenType.左方括号:
                targets.append(self._parse_list_destructure_target())
            elif self.current.type == TokenType.左花括号:
                targets.append(self._parse_dict_destructure_target())
            else:
                name = self.expect(TokenType.标识符, "元组解构需要变量名")
                targets.append(DestructureTarget(name=name.value))
            if not self.match(TokenType.逗号):
                break
        self.expect(TokenType.右括号, "元组解构需要 ')'")
        return DestructureTarget(is_list=True, list_targets=targets)

    def _parse_list_destructure_target(self) -> DestructureTarget:
        """递归解析列表解构目标：[甲, [乙, 丙], ...尾]"""
        self.advance()  # 消费 [
        targets = []
        rest = None
        while self.current.type != TokenType.右方括号:
            if self.current.type == TokenType.展开:
                self.advance()
                rest_name = self.expect(TokenType.标识符, "展开操作符后需要变量名")
                rest = rest_name.value
                break
            if self.current.type == TokenType.左方括号:
                targets.append(self._parse_list_destructure_target())
            elif self.current.type == TokenType.左花括号:
                targets.append(self._parse_dict_destructure_target())
            else:
                name = self.expect(TokenType.标识符, "解构赋值需要变量名")
                targets.append(DestructureTarget(name=name.value))
            if not self.match(TokenType.逗号):
                break
        self.expect(TokenType.右方括号, "解构赋值需要 ']'")
        return DestructureTarget(is_list=True, list_targets=targets, list_rest=rest)

    def _parse_dict_destructure_target(self) -> DestructureTarget:
        """递归解析字典解构目标：{姓名, 地址: {城市}}"""
        self.advance()  # 消费 {
        dict_targets = {}
        while self.current.type != TokenType.右花括号:
            key_token = self.expect(TokenType.标识符, "字典解构需要键名")
            key = key_token.value
            if self.match(TokenType.冒号):
                if self.current.type == TokenType.左方括号:
                    dict_targets[key] = self._parse_list_destructure_target()
                elif self.current.type == TokenType.左花括号:
                    dict_targets[key] = self._parse_dict_destructure_target()
                else:
                    value_token = self.expect(TokenType.标识符, "字典解构需要变量名")
                    dict_targets[key] = DestructureTarget(name=value_token.value)
            else:
                dict_targets[key] = DestructureTarget(name=key)
            if not self.match(TokenType.逗号):
                break
        self.expect(TokenType.右花括号, "字典解构需要 '}'")
        return DestructureTarget(is_dict=True, dict_targets=dict_targets)

    def _parse_dict_destructure_decl(self, token, is_constant: bool) -> DestructureAssign:
        """解析字典解构声明：定义 {姓名, 年龄} = 人 或 定义 {姓名: 名} = 人"""
        pattern = self._parse_dict_destructure_target()
        self.expect(TokenType.赋值, "字典解构需要 '='")
        value = self.parse_expression()
        self.match(TokenType.换行)
        flat_targets = []
        flat_dict = {}
        self._flatten_dict_pattern(pattern, flat_targets, flat_dict)
        return DestructureAssign(
            targets=flat_targets,
            value=value,
            is_declaration=True,
            dict_targets=flat_dict,
            is_dict_destructure=True,
            pattern=pattern,
            line=token.line,
            column=token.column,
        )

    def _flatten_dict_pattern(self, pattern: DestructureTarget, targets: list, dict_targets: dict):
        """将字典解构模式展平为兼容格式"""
        for key, target in pattern.dict_targets.items():
            if target.name is not None:
                dict_targets[key] = target.name
                targets.append(target.name)

    def _parse_destructure_decl(self, token, is_constant: bool) -> DestructureAssign:
        """解析解构声明：定义 [甲, 乙, ...尾] = [1, 2, 3, 4]"""
        pattern = self._parse_list_destructure_target()
        self.expect(TokenType.赋值, "解构赋值需要 '='")
        value = self.parse_expression()
        self.match(TokenType.换行)
        flat_targets = []
        rest = None
        self._flatten_list_pattern(pattern, flat_targets)
        if pattern.list_rest:
            rest = pattern.list_rest
        return DestructureAssign(
            targets=flat_targets,
            value=value,
            is_declaration=True,
            rest_target=rest,
            pattern=pattern,
            line=token.line,
            column=token.column,
        )

    def _flatten_list_pattern(self, pattern: DestructureTarget, targets: list):
        """将列表解构模式展平为兼容格式"""
        for target in pattern.list_targets:
            if target.name is not None:
                targets.append(target.name)
            elif target.is_list:
                self._flatten_list_pattern(target, targets)
            elif target.is_dict:
                self._flatten_dict_pattern(target, targets, {})
