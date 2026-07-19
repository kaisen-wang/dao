"""
词法分析器核心
=============

Lexer 类：组合 LexerReaders 混入，
提供初始化、字符流基础设施、主循环 tokenize() 以及缩进处理逻辑。
"""

from ..errors import 词法错误
from ..tokens import KEYWORDS, Token, TokenType
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
        self._pipe_continuation = False  # 管道续行标志：当行首为 |> 时为 True

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
                source_level = self.indent_stack.pop()
                self.tokens.append(self._make_token(TokenType.回退, source_level))
            if self.indent_stack[-1] != indent_level:
                raise self._error(
                    f"缩进不一致：期望 {self.indent_stack[-1]} 个空格，实际 {indent_level} 个"
                )

    def _is_line_starting_with_pipe(self, start_pos: int) -> bool:
        """前瞻检测从 start_pos 开始是否以 |> 运算符开头（不修改词法分析器状态）"""
        pos = start_pos
        while pos < len(self.source) and self.source[pos] in (" ", "\t"):
            pos += 1
        if pos + 1 < len(self.source):
            return self.source[pos] == "|" and self.source[pos + 1] == ">"
        return False

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
        self._pipe_continuation = False

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
                if self._is_line_starting_with_pipe(self.pos):
                    self._pipe_continuation = True
                    if self.tokens and self.tokens[-1].type == TokenType.换行:
                        self.tokens.pop()
                else:
                    self._pipe_continuation = False
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

            # 注释 或 整除运算符
            if char == "/" and self.peek() == "/":
                # 判断 // 是整除运算符还是注释：
                # 1. // 后面紧跟数值、括号等 → 整除
                # 2. // 后面紧跟标识符时，需要结合前一个 token 判断
                is_floor_div = False
                if self.tokens and self.tokens[-1].type in (
                    TokenType.数值,
                    TokenType.标识符,
                    TokenType.右括号,
                    TokenType.右方括号,
                    TokenType.右花括号,
                    TokenType.真,
                    TokenType.假,
                    TokenType.空,
                    TokenType.文本,
                    TokenType.模板文本,
                ):
                    check_pos = self.pos + 2
                    while check_pos < len(self.source) and self.source[check_pos] in (' ', '\t'):
                        check_pos += 1
                    if check_pos < len(self.source):
                        ch = self.source[check_pos]
                        if ch.isdigit() or ch in ('(', '（', '[', '-', '+'):
                            is_floor_div = True
                        elif self._is_identifier_start(ch):
                            # // 后面是标识符：只有前一个 token 是 数值/标识符 时才判定为整除
                            # 例如: x // y 是整除，但 f() // 注释 是注释
                            if self.tokens[-1].type in (
                                TokenType.数值,
                                TokenType.标识符,
                                TokenType.真,
                                TokenType.假,
                                TokenType.空,
                                TokenType.文本,
                                TokenType.模板文本,
                            ):
                                is_floor_div = True

                if is_floor_div:
                    self.advance()
                    self.advance()
                    self.tokens.append(self._make_token(TokenType.整除, "//"))
                else:
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
                # 检查是否是三引号字符串
                if char in ('"', "'") and self.peek() == char and self.peek(2) == char:
                    self.tokens.append(self._read_triple_quoted_string(char))
                else:
                    self.tokens.append(self._read_string(char))
                continue

            # 模板字符串
            if char == "`":
                self.tokens.append(self._read_template_string())
                continue

            # 标识符 / 关键字
            if self._is_identifier_start(char):
                token = self._read_identifier()
                if isinstance(token, tuple):
                    # 处理返回多个 token 的情况（如 异步函数）
                    self.tokens.extend(token)
                else:
                    self.tokens.append(token)
                continue

            # 逻辑变量前缀 ?
            if char == "?":
                self.tokens.append(self._read_logic_variable())
                continue

            # 宏注入前缀 $
            if char == "$":
                self.tokens.append(self._read_macro_injection())
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
