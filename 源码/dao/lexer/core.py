"""
词法分析器核心
=============

Lexer 类：组合 LexerReaders 混入，
提供初始化、字符流基础设施、主循环 tokenize() 以及缩进处理逻辑。
"""

from ..tokens import Token, TokenType, KEYWORDS
from ..errors import 词法错误
from .readers import LexerReaders


class Lexer(LexerReaders):
    """
    词法分析器

    使用方法：
        lexer = Lexer(源代码字符串)
        tokens = lexer.tokenize()
    """

    def __init__(self, source: str, filename: str = "<输入>"):
        self.source = source
        self.filename = filename
        self.pos = 0  # 当前字符位置
        self.line = 1  # 当前行号
        self.column = 1  # 当前列号
        self.tokens: list[Token] = []
        self.indent_stack: list[int] = [0]  # 缩进层级栈
        self._at_line_start = True  # 是否在行首（用于缩进检测）
        self._bracket_depth = 0  # 括号嵌套深度（> 0 时忽略缩进和换行）

    # ========================
    # 字符流基础设施
    # ========================

    @property
    def current_char(self) -> str | None:
        """获取当前字符，超出源代码范围返回None"""
        if self.pos >= len(self.source):
            return None
        return self.source[self.pos]

    def peek(self, offset: int = 1) -> str | None:
        """向前查看第offset个字符（不移动位置）"""
        pos = self.pos + offset
        if pos >= len(self.source):
            return None
        return self.source[pos]

    def advance(self) -> str:
        """读取当前字符并向前移动一位"""
        char = self.source[self.pos]
        self.pos += 1
        if char == "\n":
            self.line += 1
            self.column = 1
        else:
            self.column += 1
        return char

    def _make_token(
        self, token_type: TokenType, value, line: int = 0, column: int = 0
    ) -> Token:
        """创建一个Token"""
        return Token(
            type=token_type,
            value=value,
            line=line or self.line,
            column=column or self.column,
        )

    def _error(self, message: str) -> 词法错误:
        """生成词法错误"""
        return 词法错误(message, self.line, self.column, self.source)

    # ========================
    # 缩进处理
    # ========================

    def _handle_indentation(self, indent_level: int):
        """处理缩进变化，生成 INDENT/DEDENT Token"""
        current = self.indent_stack[-1]

        if indent_level > current:
            self.indent_stack.append(indent_level)
            self.tokens.append(self._make_token(TokenType.缩进, indent_level))
        elif indent_level < current:
            while self.indent_stack[-1] > indent_level:
                self.indent_stack.pop()
                self.tokens.append(self._make_token(TokenType.回退, indent_level))
            if self.indent_stack[-1] != indent_level:
                raise self._error(
                    f"缩进不一致：期望 {self.indent_stack[-1]} 个空格，实际 {indent_level} 个"
                )

    # ========================
    # 主循环
    # ========================

    def tokenize(self) -> list[Token]:
        """
        执行词法分析，将源代码转换为Token列表

        返回：Token列表（以EOF结尾）
        """
        self.tokens = []
        self.pos = 0
        self.line = 1
        self.column = 1
        self.indent_stack = [0]
        self._at_line_start = True
        self._bracket_depth = 0

        while self.pos < len(self.source):
            # 行首处理缩进
            if self._at_line_start:
                indent_level = 0
                while self.current_char == " ":
                    indent_level += 1
                    self.advance()
                if self.current_char == "\t":
                    raise self._error("请使用空格缩进，不支持制表符与空格混用")

                # 跳过空行
                if self.current_char == "\n":
                    self.advance()
                    continue
                # 跳过注释行
                if self.current_char == "/" and self.peek() == "/":
                    self._skip_line_comment()
                    continue
                if self.current_char == "注" and self.peek() == "：":
                    self._skip_line_comment()
                    continue

                self._at_line_start = False
                # 在括号内部时不处理缩进（支持多行表达式）
                if self._bracket_depth == 0:
                    self._handle_indentation(indent_level)

            char = self.current_char

            # 文件结束
            if char is None:
                break

            # 换行
            if char == "\n":
                if self._bracket_depth == 0:
                    self.tokens.append(self._make_token(TokenType.换行, "\\n"))
                self.advance()
                if self._bracket_depth == 0:
                    self._at_line_start = True
                continue

            # 跳过行内空白
            if char in (" ", "\t", "\r"):
                self.advance()
                continue

            # 注释
            if char == "/" and self.peek() == "/":
                self._skip_line_comment()
                continue
            if char == "/" and self.peek() == "*":
                self.advance()  # 跳过 /
                self._skip_block_comment()
                continue
            if char == "注" and self.peek() == "：":
                self._skip_line_comment()
                continue

            # 数值
            if char is not None and char.isdigit():
                self.tokens.append(self._read_number())
                continue

            # 字符串（西文引号 + 中文引号）
            if char in ('"', "'", "\u201c", "\u2018", "\u300c"):
                self.tokens.append(self._read_string(char))
                continue

            # 模板字符串
            if char == "`":
                self.tokens.append(self._read_template_string())
                continue

            # 标识符 / 关键字
            if self._is_identifier_start(char):
                self.tokens.append(self._read_identifier())
                continue

            # 运算符和标点
            token = self._read_operator_or_punctuation()
            if token:
                self.tokens.append(token)
                continue

            raise self._error(f"无法识别的字符: '{char}'")

        # 文件结束时关闭所有缩进
        if self.tokens and self.tokens[-1].type != TokenType.换行:
            self.tokens.append(self._make_token(TokenType.换行, "\\n"))
        while len(self.indent_stack) > 1:
            self.indent_stack.pop()
            self.tokens.append(self._make_token(TokenType.回退, 0))

        self.tokens.append(self._make_token(TokenType.文件结束, None))
        return self.tokens
