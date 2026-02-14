"""
语法分析器核心
=============

Parser 类：组合 StatementParser 和 ExpressionParser 混入，
提供初始化、基础设施方法、顶层解析入口和代码块解析。
"""

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
        """解析代码块 - 支持缩进块或花括号块"""
        if self.match(TokenType.左花括号):
            # 花括号块 - 支持左花括号后直接跟着语句而不需要换行
            statements = []
            self.advance()  # 消费左花括号

            print(
                f"parse_block 开始解析，pos={self.pos}, current token: {self.tokens[self.pos].type.name} -> '{self.tokens[self.pos].value}'"
            )

            while (
                not self.match(TokenType.右花括号)
                and self.current.type != TokenType.文件结束
            ):
                # 跳过换行或缩进
                if self.current.type in (TokenType.换行, TokenType.缩进):
                    print(f"parse_block 跳过换行/缩进，pos={self.pos}")
                    self.advance()
                    continue

                if (
                    self.match(TokenType.右花括号)
                    or self.current.type == TokenType.文件结束
                ):
                    break

                # 特别处理 $块 标识符，确保它被正确解析
                if (
                    self.current.type == TokenType.标识符
                    and self.current.value == "$块"
                ):
                    print(f"parse_block 找到 $块，pos={self.pos}")
                    from ..ast_nodes import ExpressionStmt

                    expr = self.parse_primary()
                    stmt = ExpressionStmt(
                        expression=expr,
                        line=self.current.line,
                        column=self.current.column,
                    )
                    statements.append(stmt)
                    print(f"parse_block 添加 $块 语句，type={type(stmt).__name__}")
                    continue

                # 处理其他以 $ 开头的标识符
                elif (
                    self.current.type == TokenType.标识符
                    and self.current.value.startswith("$")
                ):
                    print(
                        f"parse_block 找到 $ 标识符，value={self.current.value}, pos={self.pos}"
                    )
                    from ..ast_nodes import ExpressionStmt

                    expr = self.parse_primary()
                    stmt = ExpressionStmt(
                        expression=expr,
                        line=self.current.line,
                        column=self.current.column,
                    )
                    statements.append(stmt)

                else:
                    print(
                        f"parse_block 解析语句，pos={self.pos}, type={self.current.type.name}"
                    )
                    stmt = self.parse_statement()
                    if stmt:
                        statements.append(stmt)
                        print(f"parse_block 添加语句，type={type(stmt).__name__}")
                    else:
                        print(f"parse_block 跳过无效语句，pos={self.pos}")
                        self.advance()

            print(f"parse_block 结束解析，共 {len(statements)} 个语句")
            self.advance()  # 消费右花括号
            return statements
        else:
            # 检查是否在引号块中（通过调用堆栈）
            import inspect

            is_in_quote_block = False
            for frame in inspect.stack():
                if "parse_quote_block" in frame.function:
                    is_in_quote_block = True
                    break

            if is_in_quote_block:
                # 在引号块中接受单行语句作为块
                statement = self.parse_statement()
                return [statement] if statement else []
            else:
                # 缩进块（正常情况）
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
