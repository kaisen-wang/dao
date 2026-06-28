"""
宏系统解析混入
=============

提供对宏系统相关语法的解析支持。

新增的解析方法：
- parse_macro_definition()：解析宏定义语句
- parse_quote_block()：解析引述块
- parse_unquote_expr()：解析注入表达式
- parse_macro_call()：解析宏调用表达式

支持的语法：
- 定义宏 名称(参数列表)
      宏体
- 引述
      引述体
- 引述 表达式          （单行引述）
- 注入(表达式)
- !宏名(参数)
- !宏名(参数)          （带缩进块参数）
      块体
"""

import logging

from ...ast_nodes import (
    BinaryOp,
    BlockExpr,
    BooleanLiteral,
    Expression,
    FunctionCall,
    Identifier,
    MacroCall,
    MacroDefinition,
    NullLiteral,
    NumberLiteral,
    QuoteBlock,
    Statement,
    StringLiteral,
    UnaryOp,
    UnquoteExpr,
    VariableDecl,
)
from ...errors import 语法错误
from ...tokens import TokenType

logger = logging.getLogger('dao.macros')


class MacroParser:
    """宏系统解析方法集"""

    def parse_macro_definition(self) -> MacroDefinition:
        """解析宏定义：定义宏 名称(参数) 换行 缩进体"""
        logger.debug("parse_macro_definition 内部 pos=%d", self.pos)
        token = self.advance()  # 消费 "定义宏"

        # 解析宏名称
        name_token = self.expect(TokenType.标识符, "宏定义需要一个名称")
        name = name_token.value

        # 解析参数列表
        parameters = []
        self.expect(TokenType.左括号, "宏定义需要参数列表")

        if self.current.type != TokenType.右括号:
            while True:
                param_token = self.expect(TokenType.标识符, "参数名必须是标识符")
                param_str = param_token.value

                # 解析可选的默认值（如 x=10）
                if self.current.type == TokenType.赋值:
                    self.advance()

                    # 解析默认值表达式，但不解析括号
                    value_str = ""
                    while self.current.type not in (TokenType.逗号, TokenType.右括号):
                        # 根据token类型处理值的获取
                        if self.current.type == TokenType.数值:
                            value_str += str(self.current.value)
                        elif self.current.type == TokenType.文本:
                            value_str += f'"{self.current.value}"'
                        else:
                            value_str += str(self.current.value)
                        self.advance()
                    # 保存参数名和默认值（作为字符串）
                    param_str += f"={value_str.strip()}"

                parameters.append(param_str)

                if self.match(TokenType.右括号):
                    # match 已经消费了右括号，不需要再 advance
                    break
                self.expect(TokenType.逗号, "参数之间需要逗号分隔")
        else:
            self.advance()  # 消费右括号

        # 期望换行
        self.expect(TokenType.换行, "宏定义头部后需要换行")

        # 解析宏体（缩进块）
        body = self.parse_block()

        return MacroDefinition(
            name=name,
            parameters=parameters,
            body=body,
            line=token.line,
            column=token.column,
        )

    def parse_quote_block(self) -> QuoteBlock:
        """解析引述块：引述 换行 缩进体 或 引述 表达式（单行）"""
        if self.current.type == TokenType.引述 or self.current.type == TokenType.引用:
            token = self.advance()  # 消费 "引述" 或 "引用"
        else:
            raise 语法错误(
                "引述块需要以'引述'或'引用'关键字开头",
                self.current.line,
                self.current.column,
                self.source,
            )

        body = []

        logger.debug("=== parse_quote_block ===")

        if self.current.type == TokenType.换行:
            # 缩进块模式：引述后换行，然后缩进体
            self.advance()  # 消费换行
            body = self.parse_block()
        else:
            # 单行模式：引述后直接跟表达式
            stmt = self.parse_statement()
            if stmt:
                logger.debug("  Adding stmt: %s", type(stmt).__name__)
                body.append(stmt)

        return QuoteBlock(
            body=body,
            line=token.line,
            column=token.column,
        )

    def parse_unquote_expr(self) -> UnquoteExpr:
        """解析注入表达式：注入(表达式) 或 注入 表达式"""
        token = self.advance()  # 消费 "注入"

        # 检查是否有括号
        if self.match(TokenType.左括号):
            expr = self.parse_expression()
            self.expect(TokenType.右括号, "注入表达式需要右括号")
        else:
            expr = self.parse_expression()

        return UnquoteExpr(
            expression=expr,
            line=token.line,
            column=token.column,
        )

    def parse_macro_call(self) -> MacroCall:
        """解析宏调用：!宏名(参数) 或 !宏名(参数) 换行 缩进块"""
        token = self.advance()  # 消费 "!"

        name_token = self.expect(TokenType.标识符, "宏调用需要宏名称")
        name = name_token.value

        # 解析参数
        arguments = []
        self.expect(TokenType.左括号, "宏调用需要参数列表")

        if self.current.type != TokenType.右括号:
            while True:
                arg = self.parse_expression()
                arguments.append(arg)

                if self.match(TokenType.右括号):
                    # match 已经消费了右括号
                    break
                self.expect(TokenType.逗号, "参数之间需要逗号分隔")
        else:
            self.advance()  # 消费右括号

        logger.debug("After parsing macro call: pos=%d, arguments=%d", self.pos, len(arguments))

        # 检查是否有块参数
        # 跳过换行
        while self.pos < len(self.tokens) and self.current.type == TokenType.换行:
            self.advance()

        # 检查是否有缩进块
        if self.current.type == TokenType.缩进:
            block_body = self.parse_block()
            if block_body:
                arguments.append(BlockExpr(body=block_body))
                logger.debug("Added block argument with %d statements", len(block_body))

        return MacroCall(
            name=name,
            arguments=arguments,
            line=token.line,
            column=token.column,
        )

    def parse_macro_expression(self):
        """解析宏相关的表达式类型"""
        if (
            self.current.type == TokenType.感叹号
            and self.peek().type == TokenType.标识符
        ):
            return self.parse_macro_call()

        if self.current.type == TokenType.引述 or self.current.type == TokenType.引用:
            return self.parse_quote_block()

        if self.current.type == TokenType.注入:
            return self.parse_unquote_expr()

        if self.current.type == TokenType.美元注入:
            token = self.advance()  # 消费 $注入 Token
            return UnquoteExpr(
                expression=Identifier(token.value, token.line, token.column),
                line=token.line,
                column=token.column,
            )

        return None
