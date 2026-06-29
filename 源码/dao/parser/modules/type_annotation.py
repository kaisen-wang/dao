from ...ast_nodes import (
    BasicTypeAnnotation,
    FunctionTypeAnnotation,
    GenericTypeAnnotation,
    OptionalTypeAnnotation,
    TypeAnnotation,
    UnionTypeAnnotation,
)
from ...tokens import TokenType


class TypeAnnotationParser:
    def parse_type_annotation(self) -> TypeAnnotation:
        return self._parse_union_type_annotation()

    def _parse_union_type_annotation(self) -> TypeAnnotation:
        left = self._parse_primary_type_annotation()
        if self.current.type == TokenType.竖线:
            types = [left]
            while self.match(TokenType.竖线):
                right = self._parse_primary_type_annotation()
                types.append(right)
            if len(types) == 2 and isinstance(types[1], BasicTypeAnnotation) and types[1].name == "空":
                return OptionalTypeAnnotation(
                    inner=types[0],
                    line=left.line,
                    column=left.column,
                )
            return UnionTypeAnnotation(
                types=types,
                line=left.line,
                column=left.column,
            )
        return left

    def _parse_primary_type_annotation(self) -> TypeAnnotation:
        if self.current.type == TokenType.函数:
            return self._parse_function_type_annotation()

        name_token = self.expect_identifier_or_keyword("期望类型名称")
        name = name_token.value
        line, col = name_token.line, name_token.column

        if self.current.type == TokenType.左方括号:
            return self._parse_generic_type_annotation(name, line, col)

        return BasicTypeAnnotation(name=name, line=line, column=col)

    def _parse_generic_type_annotation(self, name: str, line: int, col: int) -> GenericTypeAnnotation:
        self.advance()  # 消费 [
        type_args = []
        while self.current.type != TokenType.右方括号:
            type_args.append(self.parse_type_annotation())
            if not self.match(TokenType.逗号):
                break
        self.expect(TokenType.右方括号, "泛型类型注解需要 ']'")
        return GenericTypeAnnotation(name=name, type_args=type_args, line=line, column=col)

    def _parse_function_type_annotation(self) -> FunctionTypeAnnotation:
        token = self.advance()  # 消费 函数
        line, col = token.line, token.column
        self.expect(TokenType.左括号, "函数类型注解需要 '('")
        param_types = []
        while self.current.type != TokenType.右括号:
            param_types.append(self.parse_type_annotation())
            if not self.match(TokenType.逗号):
                break
        self.expect(TokenType.右括号, "函数类型注解需要 ')'")
        self.expect(TokenType.返回箭头, "函数类型注解需要 '->'")
        return_type = self.parse_type_annotation()
        return FunctionTypeAnnotation(
            param_types=param_types,
            return_type=return_type,
            line=line,
            column=col,
        )