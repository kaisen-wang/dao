"""函数声明解析混入"""

from ...tokens import TokenType, Token
from ...ast_nodes import FunctionDecl, ReturnStmt, TupleLiteral, YieldStmt
from ...errors import 语法错误


class FunctionDeclParser:
    """函数声明解析方法集"""

    def parse_function_decl(self) -> FunctionDecl:
        """解析函数声明：函数 名字(参数) ..."""
        token = self.advance()  # 消费 函数

        name_token = self.expect_identifier_or_keyword("函数声明需要函数名")
        self.expect(TokenType.左括号, "函数声明需要 '('")

        params, default_values, rest_param = self._parse_param_list()

        self.expect(TokenType.右括号, "函数声明需要 ')'")
        self.expect(TokenType.换行, "函数头部后需要换行")
        body = self.parse_block()

        return FunctionDecl(
            name=name_token.value,
            params=params,
            default_values=default_values,
            body=body,
            rest_param=rest_param,
            line=token.line,
            column=token.column,
        )


    def _parse_method_signature(self, token: Token) -> FunctionDecl:
        """解析方法签名（用于抽象方法，不需要函数关键字）：方法名(参数)"""
        name_token = self.expect_identifier_or_keyword("方法声明需要方法名")
        self.expect(TokenType.左括号, "方法声明需要 '('")

        params, default_values, rest_param = self._parse_param_list()

        self.expect(TokenType.右括号, "方法声明需要 ')'")
        self.expect(TokenType.换行, "方法头部后需要换行")

        return FunctionDecl(
            name=name_token.value,
            params=params,
            default_values=default_values,
            body=[],
            rest_param=rest_param,
            line=token.line,
            column=token.column,
        )


    def _parse_operator_overload(self, is_static: bool, is_private: bool) -> FunctionDecl:
        """解析运算符重载：运算符+(参数)"""
        token = self.advance()  # 消费 运算符

        # 期望运算符符号
        operator_token = self.current
        operator_symbol = ""

        # 支持的运算符符号
        operator_token_types = {
            TokenType.加: "+",
            TokenType.减: "-",
            TokenType.乘: "*",
            TokenType.除: "/",
            TokenType.取余: "%",
            TokenType.幂: "**",
            TokenType.等于: "==",
            TokenType.不等于: "!=",
            TokenType.小于: "<",
            TokenType.小于等于: "<=",
            TokenType.大于: ">",
            TokenType.大于等于: ">=",
        }

        if operator_token.type in operator_token_types:
            operator_symbol = operator_token_types[operator_token.type]
            self.advance()
        else:
            raise 语法错误(
                f"运算符重载需要一个有效的运算符符号 (+, -, *, /, %, **, ==, !=, <, <=, >, >=)",
                operator_token.line,
                operator_token.column,
                self.source,
            )

        # 解析参数列表
        self.expect(TokenType.左括号, "运算符重载需要 '('")
        params, default_values, rest_param = self._parse_param_list()
        self.expect(TokenType.右括号, "运算符重载需要 ')'")

        # 运算符通常接受一个参数（右操作数）
        if len(params) != 1:
            raise 语法错误(
                f"运算符重载需要一个参数（右操作数），但得到 {len(params)} 个参数",
                token.line,
                token.column,
                self.source,
            )

        self.expect(TokenType.换行, "运算符重载后需要换行")

        # 解析方法体
        body = self.parse_block()

        return FunctionDecl(
            name=f"运算符{operator_symbol}",  # 使用特殊名称存储
            params=params,
            default_values=default_values,
            body=body,
            line=token.line,
            column=token.column,
            is_static=is_static,
            is_private=is_private,
            is_operator=True,
            operator_symbol=operator_symbol,
        )


    def _parse_property_accessor(self, is_static: bool, is_private: bool, is_getter: bool) -> FunctionDecl:
        """解析属性访问器：获取 属性名() 或 设置 属性名(值)"""
        token = self.advance()  # 消费 获取或设置

        # 获取属性名
        property_name_token = self.expect_identifier_or_keyword("属性访问器需要一个属性名")
        property_name = property_name_token.value

        # 解析参数列表
        self.expect(TokenType.左括号, "属性访问器需要 '('")
        params, default_values, rest_param = self._parse_param_list()
        self.expect(TokenType.右括号, "属性访问器需要 ')'")

        # 验证参数
        if is_getter:
            # getter 不应该有参数
            if len(params) > 0:
                raise 语法错误(
                    f"属性 getter '{property_name}' 不应该有参数，但得到 {len(params)} 个参数",
                    token.line,
                    token.column,
                    self.source,
                )
        else:
            # setter 必须有一个参数
            if len(params) != 1:
                raise 语法错误(
                    f"属性 setter '{property_name}' 必须有一个参数，但得到 {len(params)} 个参数",
                    token.line,
                    token.column,
                    self.source,
                )

        self.expect(TokenType.换行, "属性访问器后需要换行")

        # 解析方法体
        body = self.parse_block()

        # 使用特殊名称存储属性访问器
        accessor_name = f"获取{property_name}" if is_getter else f"设置{property_name}"

        return FunctionDecl(
            name=accessor_name,
            params=params,
            default_values=default_values,
            body=body,
            line=token.line,
            column=token.column,
            is_static=is_static,
            is_private=is_private,
            is_getter=is_getter,
            is_setter=not is_getter,
        )



    def _parse_param_list(self) -> tuple[list[str], dict, str | None]:
        """解析参数列表，返回 (参数列表, 默认值字典, 可变参数名)"""
        params = []
        default_values = {}
        rest_param = None
        while self.current.type != TokenType.右括号:
            if self.current.type == TokenType.展开:
                self.advance()  # 消费 ...
                rest_token = self.expect_identifier_or_keyword("可变参数需要参数名")
                rest_param = rest_token.value
                break
            param = self.expect_identifier_or_keyword("期望参数名")
            params.append(param.value)
            if self.match(TokenType.赋值):
                default_values[param.value] = self.parse_expression()
            if not self.match(TokenType.逗号):
                break
        return params, default_values, rest_param


    def parse_return_stmt(self) -> ReturnStmt:
        """解析返回语句，支持多返回值语法糖：返回 甲, 乙 等价于 返回 (甲, 乙)"""
        token = self.advance()  # 消费 返回
        value = None
        if (
            self.current.type != TokenType.换行
            and self.current.type != TokenType.文件结束
        ):
            value = self.parse_expression()
            if self.match(TokenType.逗号):
                elements = [value]
                while True:
                    elements.append(self.parse_expression())
                    if not self.match(TokenType.逗号):
                        break
                value = TupleLiteral(elements=elements, line=token.line, column=token.column)
        self.match(TokenType.换行)
        return ReturnStmt(value=value, line=token.line, column=token.column)


    def parse_yield_stmt(self) -> YieldStmt:
        """解析产出语句"""
        token = self.advance()  # 消费 产出
        value = None
        if (
            self.current.type != TokenType.换行
            and self.current.type != TokenType.文件结束
        ):
            value = self.parse_expression()
        self.match(TokenType.换行)
        return YieldStmt(value=value, line=token.line, column=token.column)

    # 控制流

