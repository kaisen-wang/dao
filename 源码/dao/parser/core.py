"""
语法分析器核心
=============

Parser 类：组合 StatementParser 和 ExpressionParser 混入，
提供初始化、基础设施方法、顶层解析入口和代码块解析。
"""

import logging

logger = logging.getLogger('dao.parser')

from ..ast_nodes import Identifier, Program, Statement
from ..errors import 语法错误
from ..tokens import KEYWORDS, Token, TokenType
from .expressions import ExpressionParser
from .modules.logic_programming import LogicProgrammingParser
from .modules.macros import MacroParser
from .statements import StatementParser

# 上下文关键字：这些词保留各自的结构语法，但在「变量名/参数名/赋值目标」等
# 期望名称的位置可当作普通标识符使用，避免占用日常高频词。
CONTEXTUAL_KEYWORDS: frozenset[TokenType] = frozenset({
    TokenType.初始化,
    TokenType.本对象,
    TokenType.父对象,
    TokenType.真,
    TokenType.假,
    TokenType.空,
    TokenType.类型,
    # OOP 属性访问器
    TokenType.获取,
    TokenType.设置,
    # 控制流 / 修饰
    TokenType.步长,
    TokenType.默认,
    TokenType.静态,
    # 并发编程
    TokenType.异步,
    TokenType.等待,
    TokenType.全部,
    TokenType.竞速,
    TokenType.并行,
    TokenType.通道,
    TokenType.发送,
    TokenType.接收,
    TokenType.选择,
    TokenType.超时,
    TokenType.互斥锁,
    TokenType.同步,
    # 逻辑编程 / 查询
    TokenType.查询,
    TokenType.事实,
    TokenType.规则,
})

# 这些上下文关键字在表达式中有固定的字面量/结构含义，不能退化为变量名
_NON_IDENTIFIER_EXPR_KEYWORDS: frozenset[TokenType] = frozenset({
    TokenType.真,
    TokenType.假,
    TokenType.空,
    TokenType.初始化,
    TokenType.本对象,
    TokenType.父对象,
    TokenType.类型,
    # 这些关键字在表达式解析器中已有「否则视为标识符」的回退逻辑，
    # 交给原解析器处理可避免破坏 通道()/接收 通道 等结构语法。
    TokenType.通道,
    TokenType.接收,
    TokenType.发送,
    TokenType.互斥锁,
})

# 跟在这些 token 后面时，"等待" 是变量名而不是等待表达式的前缀
_NON_EXPR_START: frozenset[TokenType] = frozenset({
    TokenType.换行,
    TokenType.回退,
    TokenType.文件结束,
    TokenType.右括号,
    TokenType.右方括号,
    TokenType.右花括号,
    TokenType.逗号,
    TokenType.冒号,
    TokenType.赋值,
    TokenType.点,
    TokenType.加,
    TokenType.减,
    TokenType.乘,
    TokenType.除,
    TokenType.取余,
    TokenType.幂,
    TokenType.等于,
    TokenType.不等于,
    TokenType.小于,
    TokenType.小于等于,
    TokenType.大于,
    TokenType.大于等于,
    TokenType.并且,
    TokenType.或者,
})


class Parser(StatementParser, ExpressionParser, MacroParser, LogicProgrammingParser):
    """
    语法分析器

    采用递归下降（Recursive Descent）解析策略：
    - 每个语法规则对应一个解析方法
    - 自顶向下解析，从 parse() 开始
    - 运算符优先级通过方法调用层级实现

    优先级（从低到高）：
    1. 管道 (|>)
    2. 或者
    3. 并且
    4. 不是
    5. 比较 (==, !=, <, >, <=, >=, 在, 不在)
    6. 加减 (+, -)
    7. 乘除余 (*, /, %, //)
    8. 幂 (**)
    9. 一元 (-, 不是)
    10. 调用/成员访问 (f(), obj.x, list[0])
    11. 基本 (字面量, 标识符, 括号表达式)

    使用方法：
        parser = Parser(token_list)
        ast = parser.parse()
    """

    def __init__(self, tokens: list[Token], source: str = ""):
        self.tokens = tokens
        self.pos = 0
        self.source = source

    # ========================
    # 基础设施
    # ========================

    @property
    def current(self) -> Token:
        """获取当前Token"""
        if self.pos < len(self.tokens):
            return self.tokens[self.pos]
        return self.tokens[-1]  # EOF

    def peek(self, offset: int = 1) -> Token:
        """向前查看"""
        pos = self.pos + offset
        if pos < len(self.tokens):
            return self.tokens[pos]
        return self.tokens[-1]

    def advance(self) -> Token:
        """消费当前Token并返回"""
        token = self.current
        self.pos += 1
        return token

    def _is_identifier_like(self, token: Token) -> bool:
        """该 token 是否可以在期望名称的位置当作标识符使用"""
        return token.type == TokenType.标识符 or token.type in CONTEXTUAL_KEYWORDS

    def _identifier_error_message(self, message: str) -> str:
        """保留字出现在名称位置时，给出明确的中文提示"""
        current = self.current
        if current.type != TokenType.标识符 and current.value in KEYWORDS:
            if "参数" in message:
                role = "参数名"
            elif "变量" in message or "名称" in message:
                role = "变量名"
            else:
                role = "标识符"
            return f"“{current.value}”是保留关键字，不能用作{role}"
        return message

    def expect(self, token_type: TokenType, message: str = "") -> Token:
        """期望当前Token为指定类型，否则报错"""
        if self.current.type != token_type:
            msg = (
                message
                or f"期望 {token_type.name}，但得到 {self.current.type.name} ('{self.current.value}')"
            )
            if token_type == TokenType.标识符:
                msg = self._identifier_error_message(msg)
            raise 语法错误(msg, self.current.line, self.current.column, self.source)
        return self.advance()

    def match(self, *types: TokenType) -> Token | None:
        """如果当前Token是指定类型之一，消费并返回；否则返回None"""
        if self.current.type in types:
            return self.advance()
        return None

    def expect_identifier_or_keyword(self, message: str = "") -> Token:
        """期望当前Token为标识符或上下文关键字，否则报错"""
        if self._is_identifier_like(self.current):
            return self.advance()

        msg = (
            message
            or f"期望标识符或关键字，但得到 {self.current.type.name} ('{self.current.value}')"
        )
        msg = self._identifier_error_message(msg)
        raise 语法错误(msg, self.current.line, self.current.column, self.source)

    def skip_newlines(self):
        """跳过所有换行Token"""
        while self.current.type == TokenType.换行:
            self.advance()
        # Also skip any INDENT tokens after newlines (e.g., after implements clause, or from empty lines)
        while self.current.type == TokenType.缩进:
            self.advance()
            # Skip any newlines that followed the INDENT (for consecutive empty lines)
            while self.current.type == TokenType.换行:
                self.advance()
        # Also skip any INDENT tokens after newlines (e.g., after implements clause, or from empty lines)
        # Keep skipping INDENTs as long as they appear (empty lines at same indent level)
        while self.current.type == TokenType.缩进:
            self.advance()
            # Skip any newlines that followed the INDENT (e.g., from empty lines)
            while self.current.type == TokenType.换行:
                self.advance()

    def _error(self, message: str) -> 语法错误:
        return 语法错误(message, self.current.line, self.current.column, self.source)

    def parse_primary(self):
        """上下文关键字用作变量时，按标识符解析；结构语法仍交给原解析器。"""
        token = self.current
        if (
            token.type in CONTEXTUAL_KEYWORDS
            and token.type not in _NON_IDENTIFIER_EXPR_KEYWORDS
        ):
            is_value = True
            if token.type in (TokenType.全部, TokenType.竞速, TokenType.查询):
                # 全部(...) / 竞速(...) / 查询(...) 才是结构语法
                is_value = self.peek().type != TokenType.左括号
            elif token.type == TokenType.等待:
                # 等待 表达式 才是等待语法；后面是运算符/结束符时是变量名
                is_value = self.peek().type in _NON_EXPR_START
            if is_value:
                self.advance()
                return Identifier(
                    name=token.value, line=token.line, column=token.column
                )
        return super().parse_primary()

    # ========================
    # 顶层解析入口
    # ========================

    def parse(self) -> Program:
        """解析整个程序"""
        program = Program(statements=[])
        self.skip_newlines()

        while self.current.type != TokenType.文件结束:
            stmt = self.parse_statement()
            if stmt:
                program.statements.append(stmt)
            else:
                # 如果返回 None，说明遇到回退 token，直接跳过
                if self.current.type == TokenType.回退:
                    self.advance()
            self.skip_newlines()

        return program

    # ========================
    # 代码块解析
    # ========================

    def parse_block(self) -> list[Statement]:
        """解析代码块（缩进块）"""
        self.expect(TokenType.缩进, "期望缩进块")
        statements = []
        while self.current.type not in (TokenType.回退, TokenType.文件结束):
            self.skip_newlines()
            # 跳过同一缩进级别的空行导致的额外缩进标记
            while self.current.type == TokenType.缩进:
                self.advance()
                self.skip_newlines()
            if self.current.type in (TokenType.回退, TokenType.文件结束):
                break
            statements.append(self.parse_statement())
        self.expect(TokenType.回退, "期望回退")
        return statements

    def read_block_no_consume(self) -> list[Statement]:
        """读取缩进块，但不消费最后的回退 Token

        用于需要在回退后继续检查的外层解析器（如选择语句）。
        """
        self.expect(TokenType.缩进, "期望缩进块")
        statements = []
        while self.current.type not in (TokenType.回退, TokenType.文件结束):
            self.skip_newlines()
            while self.current.type == TokenType.缩进:
                self.advance()
                self.skip_newlines()
            if self.current.type in (TokenType.回退, TokenType.文件结束):
                break
            statements.append(self.parse_statement())
        return statements
