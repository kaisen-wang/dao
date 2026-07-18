"""
宏系统解析混入
=============

提供对宏系统相关语法的解析支持。

新增的解析方法：
- parse_macro_definition()：解析宏定义语句
- parse_pattern_macro_definition()：解析模式匹配宏定义语句
- parse_quote_block()：解析引述块
- parse_unquote_expr()：解析注入表达式
- parse_macro_call()：解析宏调用表达式

支持的语法：
- 定义宏 名称(参数列表)
      宏体
- 定义宏 名称(参数列表) 匹配
      模式1 => 引述体1
      模式2 => 引述体2
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
    EnumVariantPattern,
    Expression,
    FunctionCall,
    Identifier,
    MacroCall,
    MacroDefinition,
    NullLiteral,
    NumberLiteral,
    PatternBranch,
    PatternMatchBody,
    QuoteBlock,
    Statement,
    StringLiteral,
    TypeCheckPattern,
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

        # 解析参数列表（共用方法）
        parameters = self._parse_parameter_list()

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

    def _parse_parameter_list(self) -> list[str]:
        """解析参数列表（供普通宏和模式匹配宏共用）"""
        parameters = []
        self.expect(TokenType.左括号, "宏定义需要参数列表")

        if self.current.type != TokenType.右括号:
            while True:
                if self.current.type == TokenType.标识符:
                    param_str = self.advance().value
                elif self.current.type in (TokenType.类型,):
                    param_str = self.advance().value
                else:
                    raise self._error("参数名必须是标识符")

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

        return parameters

    def _is_pattern_macro(self) -> bool:
        """判断宏定义是否为模式匹配宏（前看方法）"""
        saved_pos = self.pos

        try:
            self.advance()  # 跳过 "定义宏"

            # 跳过名称（可能是标识符或关键字）
            self.advance()

            # 跳过参数列表
            if self.pos < len(self.tokens) and self.current.type == TokenType.左括号:
                depth = 1
                self.advance()
                while depth > 0 and self.pos < len(self.tokens):
                    if self.current.type == TokenType.左括号:
                        depth += 1
                    elif self.current.type == TokenType.右括号:
                        depth -= 1
                    self.advance()

            # 检查下一个token是否为 "匹配"
            result = self.pos < len(self.tokens) and self.current.type == TokenType.匹配
            return result
        finally:
            self.pos = saved_pos

    def parse_pattern_macro_definition(self) -> MacroDefinition:
        """解析模式匹配宏定义：定义宏 名称(参数) 匹配 模式分支..."""
        logger.debug("parse_pattern_macro_definition 内部 pos=%d", self.pos)
        token = self.advance()  # 消费 "定义宏"

        # 解析宏名称
        name_token = self.expect(TokenType.标识符, "宏定义需要一个名称")
        name = name_token.value

        # 解析参数列表（共用方法）
        parameters = self._parse_parameter_list()

        # 期望 "匹配" 关键字
        self.expect(TokenType.匹配, "模式匹配宏需要 '匹配' 关键字")

        # 期望换行 + 缩进
        self.expect(TokenType.换行, "'匹配' 后需要换行")
        self.expect(TokenType.缩进, "模式分支需要缩进")

        # 循环解析模式分支
        branches = []
        while self.current.type not in (TokenType.回退, TokenType.文件结束):
            self.skip_newlines()
            if self.current.type in (TokenType.回退, TokenType.文件结束):
                break
            branches.append(self._parse_pattern_branch())

        self.match(TokenType.回退)

        if not branches:
            raise 语法错误(
                "模式匹配宏至少需要一个模式分支",
                token.line,
                token.column,
                self.source,
            )

        # 构建 PatternMatchBody
        pattern_body = PatternMatchBody(
            branches=branches,
            line=token.line,
            column=token.column,
        )

        return MacroDefinition(
            name=name,
            parameters=parameters,
            body=pattern_body,
            line=token.line,
            column=token.column,
        )

    def _parse_pattern_branch(self) -> PatternBranch:
        """解析模式分支：模式 [当 守卫] => 引述体"""
        line, col = self.current.line, self.current.column

        # 解析匹配模式
        pattern = self._parse_pattern()

        # 可选守卫条件
        guard = None
        if self.match(TokenType.当):
            guard = self.parse_expression()

        # 期望 =>
        self.expect(TokenType.箭头, "模式分支需要 '=>'")

        # 解析引述体
        body = self.parse_quote_block()

        return PatternBranch(
            pattern=pattern,
            guard=guard,
            body=body,
            line=line,
            column=col,
        )

    def _parse_pattern(self) -> Expression:
        """解析匹配模式"""
        # 通配符 _
        if self.current.type == TokenType.标识符 and self.current.value == "_":
            token = self.advance()
            return Identifier(name="_", line=token.line, column=token.column)

        # 列表模式 [...]
        if self.current.type == TokenType.左方括号:
            return self.parse_list_pattern()

        # 字典模式 {...}
        if self.current.type == TokenType.左花括号:
            return self.parse_dict_pattern()

        # 类型检查模式 类型:类型名
        if self.current.type == TokenType.类型 and self.peek().type == TokenType.冒号:
            return self._parse_type_check_pattern()

        # 枚举变体模式 标识符.标识符(绑定)
        if (
            self.current.type == TokenType.标识符
            and self.peek().type == TokenType.点
        ):
            return self._parse_enum_variant_pattern()

        # 字面量模式（数值、文本、布尔、空）
        if self.current.type in (
            TokenType.数值,
            TokenType.文本,
            TokenType.真,
            TokenType.假,
            TokenType.空,
        ):
            return self.parse_expression()

        # 变量绑定模式（标识符）
        if self.current.type == TokenType.标识符:
            token = self.advance()
            return Identifier(name=token.value, line=token.line, column=token.column)

        raise 语法错误(
            f"无效的模式: {self.current.value}",
            self.current.line,
            self.current.column,
            self.source,
        )

    def _parse_type_check_pattern(self) -> TypeCheckPattern:
        """解析类型检查模式：类型:类型名"""
        token = self.advance()  # 消费 "类型"
        self.expect(TokenType.冒号, "类型检查模式需要 ':'")

        type_name_token = self.expect(TokenType.标识符, "类型检查模式需要类型名")
        type_name = type_name_token.value

        return TypeCheckPattern(
            type_name=type_name,
            line=token.line,
            column=token.column,
        )

    def _parse_enum_variant_pattern(self) -> EnumVariantPattern:
        """解析枚举变体模式：枚举名.变体名(绑定变量)"""
        enum_token = self.advance()  # 消费枚举名
        enum_name = enum_token.value

        self.expect(TokenType.点, "枚举变体模式需要 '.'")

        variant_token = self.expect(TokenType.标识符, "枚举变体模式需要变体名")
        variant_name = variant_token.value

        # 可选解析括号内的绑定变量名
        binding = None
        if self.match(TokenType.左括号):
            binding_token = self.expect(TokenType.标识符, "枚举变体绑定需要变量名")
            binding = binding_token.value
            self.expect(TokenType.右括号, "枚举变体绑定需要 ')'")

        return EnumVariantPattern(
            enum_name=enum_name,
            variant_name=variant_name,
            binding=binding,
            line=enum_token.line,
            column=enum_token.column,
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
