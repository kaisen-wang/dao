"""面向对象声明解析混入"""

from ...ast_nodes import (
    AbstractDecl,
    ClassDecl,
    EnumDecl,
    EnumVariant,
    FunctionDecl,
    Statement,
    TraitDecl,
)
from ...errors import 语法错误
from ...tokens import Token, TokenType


class OOPDeclParser:
    """面向对象声明解析方法集"""

    def parse_enum_decl(self) -> EnumDecl:
        """解析枚举声明：枚举 名字 ..."""

        token = self.advance()  # 消费 枚举
        name_token = self.expect(TokenType.标识符, "枚举声明需要一个枚举名")

        self.expect(TokenType.换行, "枚举声明后需要换行")
        self.expect(TokenType.缩进, "枚举值需要缩进块")

        values = []
        variants = []
        while self.current.type not in (TokenType.回退, TokenType.文件结束):
            self.skip_newlines()
            if self.current.type in (TokenType.回退, TokenType.文件结束):
                break

            value_token = self.expect(TokenType.标识符, "枚举值需要是标识符")
            variant_name = value_token.value

            # 检查是否有参数列表：变体名(参数1, 参数2)
            params = []
            if self.current.type == TokenType.左括号:
                self.advance()  # 消费 (
                while self.current.type != TokenType.右括号:
                    param_token = self.expect(TokenType.标识符, "枚举变体参数需要是标识符")
                    params.append(param_token.value)
                    if not self.match(TokenType.逗号):
                        break
                self.expect(TokenType.右括号, "枚举变体参数需要 ')'")

            values.append(variant_name)
            variants.append(EnumVariant(
                name=variant_name,
                params=params,
                line=value_token.line,
                column=value_token.column,
            ))

            # 逗号是可选的
            self.match(TokenType.逗号)
            self.skip_newlines()

        self.expect(TokenType.回退, "枚举声明需要回退")

        return EnumDecl(
            name=name_token.value,
            values=values,
            variants=variants,
            line=token.line,
            column=token.column,
        )

    def parse_abstract_decl(self) -> AbstractDecl:
        """解析抽象类型声明：抽象 类型 名字 [继承自 父类] ..."""
        token = self.advance()  # 消费 抽象
        self.expect(TokenType.类型, "'抽象' 后需要 '类型' 关键字")
        name_token = self.expect(TokenType.标识符, "抽象类型声明需要一个类名")

        parent_name = None
        if self.match(TokenType.继承自):
            parent_token = self.expect(TokenType.标识符, "'继承自' 后需要父类名")
            parent_name = parent_token.value

        self.expect(TokenType.换行, "抽象类型声明后需要换行")

        body = self.parse_class_body(indent_consumed=False)

        return AbstractDecl(
            name=name_token.value,
            parent_name=parent_name,
            body=body,
            line=token.line,
            column=token.column,
        )

    def parse_class_decl(self) -> ClassDecl:
        """解析类型声明：类型 名字 [继承自 父类] [实现 特征1, 特征2] ..."""
        token = self.advance()  # 消费 类型
        name_token = self.expect(TokenType.标识符, "类型声明需要一个类名")

        parent_name = None
        if self.match(TokenType.继承自):
            parent_token = self.expect(TokenType.标识符, "'继承自' 后需要父类名")
            parent_name = parent_token.value

        implemented_traits = []

        self.expect(TokenType.换行, "类型声明后需要换行")

        # 实现 clause can appear after newline/indent (in class body)
        # 检查是否是错误类型（继承自 DaoError）
        is_error_class = False
        is_abstract = False
        if parent_name == "错误":
            is_error_class = True

        # Skip INDENT if present and check for '实现'
        has_indent = self.match(TokenType.缩进)
        if has_indent:
            # Check if the first token in class body is '实现'
            if self.match(TokenType.实现):
                # 解析特征列表
                while True:
                    trait_token = self.expect(TokenType.标识符, "'实现' 后需要特征名")
                    implemented_traits.append(trait_token.value)
                    if not self.match(TokenType.逗号):
                        break
                # Skip newline after implements clause
                self.skip_newlines()
            elif not is_error_class:
                # 错误类型不需要类体，如果不是错误类型则放回缩进
                self.pos -= 1  # Undo the match(TokenType.缩进)

        # 错误类型可能有类体，也可能没有类体
        if is_error_class:
            # 检查是否有缩进块，如果没有则不解析类体
            if has_indent or (self.current.type == TokenType.缩进):
                body = self.parse_class_body(indent_consumed=has_indent)
            else:
                body = []
        else:
            body = self.parse_class_body(indent_consumed=has_indent)

        return ClassDecl(
            name=name_token.value,
            parent_name=parent_name,
            implemented_traits=implemented_traits,
            body=body,
            line=token.line,
            column=token.column,
            is_error_class=is_error_class,
            is_abstract=is_abstract,
        )

    def parse_trait_decl(self) -> TraitDecl:
        """解析特征声明：特征 名字 ..."""
        token = self.advance()  # 消费 特征
        name_token = self.expect(TokenType.标识符, "特征声明需要一个特征名")

        self.expect(TokenType.换行, "特征声明后需要换行")
        body = self.parse_class_body()  # 特征体和类体结构相同

        return TraitDecl(
            name=name_token.value,
            body=body,
            line=token.line,
            column=token.column,
        )

    def parse_class_body(self, indent_consumed: bool = False) -> list[Statement]:
        """解析类体（缩进块，包含构造函数和方法）"""
        # 允许空类体：检查是否有缩进，如果没有，则返回空语句列表
        if not indent_consumed:
            # 检查下一个 token 是否是缩进，如果不是，则返回空类体
            if self.current.type != TokenType.缩进:
                return []
            # 如果有缩进，则继续解析
            self.advance()
        statements = []

        while self.current.type not in (TokenType.回退, TokenType.文件结束):
            self.skip_newlines()
            if self.current.type in (TokenType.回退, TokenType.文件结束):
                break

            # 修饰符
            is_static = False
            is_private = False
            is_protected = False
            if self.current.type == TokenType.私有:
                is_private = True
                self.advance()
            if self.current.type == TokenType.受保护:
                is_protected = True
                self.advance()
            if self.current.type == TokenType.静态:
                is_static = True
                self.advance()

            # '实现' 子句已在 parse_class_decl 中处理，这里不再需要
            if self.current.type == TokenType.实现:
                raise 语法错误(
                    "'实现' 子句必须在类型声明的开始处",
                    self.current.line,
                    self.current.column,
                    self.source,
                )

            if self.current.type == TokenType.初始化:
                # 构造函数：初始化(参数) ...
                func = self.parse_constructor()
                func.is_private = is_private
                func.is_protected = is_protected
                statements.append(func)
            elif self.current.type == TokenType.函数:
                # 方法：函数 名字(参数) ...
                func = self.parse_function_decl()
                func.is_static = is_static
                func.is_private = is_private
                func.is_protected = is_protected
                statements.append(func)
            elif self.current.type == TokenType.抽象:
                # 抽象方法：抽象 方法名(参数)
                token = self.advance()  # 消费 抽象
                func = self._parse_method_signature(token)
                func.is_abstract = True
                func.is_static = is_static
                func.is_private = is_private
                func.is_protected = is_protected
                statements.append(func)
            elif self.current.type == TokenType.运算符:
                # 运算符重载：运算符+(参数)
                func = self._parse_operator_overload(is_static, is_private)
                func.is_protected = is_protected
                statements.append(func)
            elif self.current.type == TokenType.获取:
                # 属性 getter：获取 属性名()
                func = self._parse_property_accessor(
                    is_static, is_private, is_getter=True
                )
                func.is_protected = is_protected
                statements.append(func)
            elif self.current.type == TokenType.设置:
                # 属性 setter：设置 属性名(value)
                func = self._parse_property_accessor(
                    is_static, is_private, is_getter=False
                )
                func.is_protected = is_protected
                statements.append(func)
            else:
                # 其他语句（如类级别的属性声明）
                statements.append(self.parse_statement())

        self.match(TokenType.回退)
        return statements

    def parse_constructor(self) -> FunctionDecl:
        """解析构造函数：初始化(参数) ..."""
        token = self.advance()  # 消费 初始化
        self.expect(TokenType.左括号, "构造函数需要 '('")
        params, default_values, rest_param, _ = self._parse_param_list()
        self.expect(TokenType.右括号, "构造函数需要 ')'")
        self.expect(TokenType.换行, "构造函数头部后需要换行")
        body = self.parse_block()

        return FunctionDecl(
            name="初始化",
            params=params,
            default_values=default_values,
            body=body,
            line=token.line,
            column=token.column,
        )
