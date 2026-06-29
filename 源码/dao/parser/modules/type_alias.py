from ...ast_nodes import BasicTypeAnnotation, TypeAliasDecl
from ...tokens import TokenType


class TypeAliasParser:
    def parse_type_alias_decl(self) -> TypeAliasDecl:
        token = self.advance()  # 消费 类型别名
        name_token = self.expect_identifier_or_keyword("类型别名需要名称")
        self.expect(TokenType.赋值, "类型别名需要 '='")
        target_type = self.parse_type_annotation()
        self.match(TokenType.换行)
        return TypeAliasDecl(
            name=name_token.value,
            target_type=target_type,
            line=token.line,
            column=token.column,
        )