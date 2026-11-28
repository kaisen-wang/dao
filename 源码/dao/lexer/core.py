"""
词法分析器核心
=============

Lexer 类：组合 LexerReaders 混入，
提供初始化、字符流基础设施、主循环 tokenize() 以及缩进处理逻辑。
"""

from ..errors import 词法错误
from ..tokens import Token, TokenType
from .readers import LexerReaders

# 可结束表达式的 token 类型：其值右侧允许紧跟二元运算符（如 //）
_EXPR_END_TYPES = frozenset({
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
})

# // 之后出现这些标点时，可确定右侧是显式数值操作数
_OPERAND_START_PUNCT = frozenset({'(', '（', '[', '-', '+'})


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
    # // 歧义判别（显式状态机）
    # ========================

    def _peek_after_slashes(self) -> str | None:
        """返回 `//` 之后的首个非横向空白字符（纯前瞻，不移动游标）。"""
        pos = self.pos + 2
        length = len(self.source)
        while pos < length and self.source[pos] in (" ", "\t"):
            pos += 1
        return self.source[pos] if pos < length else None

    def _after_identifier_is_comment_text(self) -> bool:
        """`//` 后读取一个标识符，判断其后的内容是否表明这是注释文字。

        注释常带中文标点（`，。、` 等）或后续独立词；表达式则以后续运算符、
        西文逗号或行尾结束。仅用于「上一 token 为变量」的歧义场景。
        """
        pos = self.pos + 2
        length = len(self.source)
        while pos < length and self.source[pos] in (" ", "\t"):
            pos += 1
        if pos >= length or not self._is_identifier_start(self.source[pos]):
            return True
        while pos < length and self._is_identifier_char(self.source[pos]):
            pos += 1
        while pos < length and self.source[pos] in (" ", "\t", "\r"):
            pos += 1
        if pos >= length or self.source[pos] == "\n":
            return False
        ch = self.source[pos]
        if ch in "，。、；：！？）】》”’‘“【《":
            return True
        if self._is_identifier_start(ch):
            return True
        return False

    def _is_floor_div_context(self) -> bool:
        """判定当前 `//` 是整除运算符还是行内注释。

        状态机依赖「上一 token」与「`//` 后的内容」：

        1. 上一 token 不能结束表达式（如 `=`、`+`、`(`、行首）→ 注释。
        2. `//` 之后没有内容（行尾）→ 注释。
        3. 后继首字符是数字或 `(`/`[`/`+`/`-` → 整除（右侧为显式数值操作数）。
        4. 后继首字符是标识符：
           - 上一 token 是变量且该标识符后无注释特征（中文标点/后续词）→ 整除
             （保留 ``返回 被除数 // 除数, ...`` 这类用法）；
           - 其余情况 → 注释。

        这样 ``甲 = "a" // 说明``、``定义 x = 5 // 说明，这里是文字`` 等行尾注释
        都能被正确跳过，而 ``10 // 3``、``被除数 // 除数`` 等整除写法不受影响。
        若右操作数需为字面量之外的复杂表达式，请改用括号（如 ``x // (y + 1)``）。

        注：独占一行的 `//` 已在 tokenize() 的行首处理阶段跳过，不会进入此判定。
        """
        if not self.tokens or self.tokens[-1].type not in _EXPR_END_TYPES:
            return False

        ch = self._peek_after_slashes()
        if ch is None:
            return False
        if ch.isdigit() or ch in _OPERAND_START_PUNCT:
            return True
        if self._is_identifier_start(ch):
            return (
                self.tokens[-1].type == TokenType.标识符
                and not self._after_identifier_is_comment_text()
            )
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

            # 注释 或 整除运算符（判别交给显式状态机）
            if char == "/" and self.peek() == "/":
                if self._is_floor_div_context():
                    self.advance()
                    self.advance()
                    self.tokens.append(self._make_token(TokenType.整除, "//"))
                else:
                    self._skip_line_comment()
                continue
            if char == "/" and self.peek() == "*":
                # _skip_block_comment 内部会自行消费开头的 /*
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

            # 注解前缀 @
            if char == "@":
                self.tokens.append(self._read_annotation())
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
