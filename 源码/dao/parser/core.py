"""
语法分析器核心
=============

Parser 类：组合 StatementParser 和 ExpressionParser 混入，
提供初始化、基础设施方法、顶层解析入口和代码块解析。
"""

import logging

logger = logging.getLogger('dao.parser')

from ..ast_nodes import Program, Statement
from ..errors import 语法错误
from ..tokens import Token, TokenType
from .expressions import ExpressionParser
from .modules.logic_programming import LogicProgrammingParser
from .modules.macros import MacroParser
from .statements import StatementParser


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

    def expect(self, token_type: TokenType, message: str = "") -> Token:
        """期望当前Token为指定类型，否则报错"""
        if self.current.type != token_type:
            msg = (
                message
                or f"期望 {token_type.name}，但得到 {self.current.type.name} ('{self.current.value}')"
            )
            raise 语法错误(msg, self.current.line, self.current.column, self.source)
        return self.advance()

    def match(self, *types: TokenType) -> Token | None:
        """如果当前Token是指定类型之一，消费并返回；否则返回None"""
        if self.current.type in types:
            return self.advance()
        return None

    def expect_identifier_or_keyword(self, message: str = "") -> Token:
        """期望当前Token为标识符或允许的关键字，否则报错"""
        # 允许的关键字列表（这些可以用作函数名、变量名等）
        allowed_keywords = (
            TokenType.初始化,
            TokenType.本对象,
            TokenType.父对象,
            TokenType.真,
            TokenType.假,
            TokenType.空,
            TokenType.类型,
            # 并发编程相关的关键字
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
            TokenType.查询,
        )

        if (
            self.current.type == TokenType.标识符
            or self.current.type in allowed_keywords
        ):
            return self.advance()

        msg = (
            message
            or f"期望标识符或关键字，但得到 {self.current.type.name} ('{self.current.value}')"
        )
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
