"""
词法分析器 (Lexer)
=================

将"道"源代码字符串转换为Token（词元）序列。

主要职责：
1. 识别关键字、标识符、数值、字符串等
2. 处理中/西文标点符号的兼容
3. 生成缩进/回退（INDENT/DEDENT）Token以支持缩进语法
4. 跳过注释和空白
"""

from .tokens import Token, TokenType, KEYWORDS
from .errors import 词法错误


class Lexer:
    """
    词法分析器

    使用方法：
        lexer = Lexer(源代码字符串)
        tokens = lexer.tokenize()
    """

    def __init__(self, source: str, filename: str = "<输入>"):
        self.source = source
        self.filename = filename
        self.pos = 0          # 当前字符位置
        self.line = 1         # 当前行号
        self.column = 1       # 当前列号
        self.tokens: list[Token] = []
        self.indent_stack: list[int] = [0]  # 缩进层级栈
        self._at_line_start = True          # 是否在行首（用于缩进检测）

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
        if char == '\n':
            self.line += 1
            self.column = 1
        else:
            self.column += 1
        return char

    def _make_token(self, token_type: TokenType, value, line: int = 0, column: int = 0) -> Token:
        """创建一个Token"""
        return Token(
            type=token_type,
            value=value,
            line=line or self.line,
            column=column or self.column,
        )

    def _error(self, message: str) -> 词法错误:
        """生成词法错误"""
        return 词法错误(message, self.line, self.column)

    def _skip_line_comment(self):
        """跳过单行注释 (// 或 注：)"""
        while self.current_char is not None and self.current_char != '\n':
            self.advance()

    def _skip_block_comment(self):
        """跳过多行注释 /* ... */，支持嵌套"""
        depth = 1
        start_line = self.line
        self.advance()  # 跳过 *
        self.advance()  # 跳过 *后的字符... wait, we already consumed / and *

        while self.current_char is not None and depth > 0:
            if self.current_char == '/' and self.peek() == '*':
                depth += 1
                self.advance()
                self.advance()
            elif self.current_char == '*' and self.peek() == '/':
                depth -= 1
                self.advance()
                self.advance()
            else:
                self.advance()

        if depth > 0:
            raise self._error(f"未闭合的多行注释，从第 {start_line} 行开始")

    def _read_string(self, quote_char: str) -> Token:
        """读取字符串字面量"""
        start_line = self.line
        start_col = self.column
        self.advance()  # 跳过开头引号
        result = []

        while self.current_char is not None and self.current_char != quote_char:
            if self.current_char == '\\':
                self.advance()
                escape_map = {
                    'n': '\n', 't': '\t', 'r': '\r',
                    '\\': '\\', "'": "'", '"': '"',
                }
                if self.current_char in escape_map:
                    result.append(escape_map[self.current_char])
                    self.advance()
                else:
                    raise self._error(f"未知的转义序列: \\{self.current_char}")
            else:
                result.append(self.advance())

        if self.current_char is None:
            raise self._error(f"未闭合的字符串，从第 {start_line} 行开始")

        self.advance()  # 跳过结束引号
        return self._make_token(TokenType.文本, ''.join(result), start_line, start_col)

    def _read_number(self) -> Token:
        """读取数值字面量（支持整数、浮点数、下划线分隔）"""
        start_line = self.line
        start_col = self.column
        result = []
        has_dot = False

        while self.current_char is not None:
            if self.current_char.isdigit():
                result.append(self.advance())
            elif self.current_char == '_' and self.peek() is not None and self.peek().isdigit():
                self.advance()  # 跳过下划线
            elif self.current_char == '.' and not has_dot and self.peek() is not None and self.peek().isdigit():
                has_dot = True
                result.append(self.advance())
            else:
                break

        value_str = ''.join(result)
        value = float(value_str) if has_dot else int(value_str)
        return self._make_token(TokenType.数值, value, start_line, start_col)

    def _read_identifier(self) -> Token:
        """读取标识符或关键字"""
        start_line = self.line
        start_col = self.column
        result = []

        while self.current_char is not None and self._is_identifier_char(self.current_char):
            result.append(self.advance())

        word = ''.join(result)

        # 特殊处理：否则如果（两个词组合的关键字）
        if word == "否则":
            # 向前看是否紧跟"如果"
            saved_pos = self.pos
            saved_line = self.line
            saved_col = self.column

            # 跳过空格
            while self.current_char == ' ':
                self.advance()

            if self.current_char is not None and self._is_identifier_start(self.current_char):
                next_start = self.pos
                next_chars = []
                while self.current_char is not None and self._is_identifier_char(self.current_char):
                    next_chars.append(self.advance())
                next_word = ''.join(next_chars)
                if next_word == "如果":
                    return self._make_token(TokenType.否则如果, "否则如果", start_line, start_col)

            # 回退
            self.pos = saved_pos
            self.line = saved_line
            self.column = saved_col

        # 检查是否是关键字
        token_type = KEYWORDS.get(word, TokenType.标识符)
        return self._make_token(token_type, word, start_line, start_col)

    def _is_identifier_start(self, char: str) -> bool:
        """判断字符是否可以作为标识符的开头"""
        return char.isalpha() or char == '_' or '\u4e00' <= char <= '\u9fff'

    def _is_identifier_char(self, char: str) -> bool:
        """判断字符是否可以作为标识符的一部分"""
        return self._is_identifier_start(char) or char.isdigit()

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
                raise self._error(f"缩进不一致：期望 {self.indent_stack[-1]} 个空格，实际 {indent_level} 个")

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

        while self.pos < len(self.source):
            # 行首处理缩进
            if self._at_line_start:
                indent_level = 0
                while self.current_char == ' ':
                    indent_level += 1
                    self.advance()
                if self.current_char == '\t':
                    raise self._error("请使用空格缩进，不支持制表符与空格混用")

                # 跳过空行
                if self.current_char == '\n':
                    self.advance()
                    continue
                # 跳过注释行
                if self.current_char == '/' and self.peek() == '/':
                    self._skip_line_comment()
                    continue
                if self.current_char == '注' and self.peek() == '：':
                    self._skip_line_comment()
                    continue

                self._at_line_start = False
                self._handle_indentation(indent_level)

            char = self.current_char

            # 换行
            if char == '\n':
                self.tokens.append(self._make_token(TokenType.换行, '\\n'))
                self.advance()
                self._at_line_start = True
                continue

            # 跳过行内空白
            if char in (' ', '\t', '\r'):
                self.advance()
                continue

            # 注释
            if char == '/' and self.peek() == '/':
                self._skip_line_comment()
                continue
            if char == '/' and self.peek() == '*':
                self.advance()  # 跳过 /
                self._skip_block_comment()
                continue
            if char == '注' and self.peek() == '：':
                self._skip_line_comment()
                continue

            # 数值
            if char.isdigit():
                self.tokens.append(self._read_number())
                continue

            # 字符串
            if char in ('"', "'"):
                self.tokens.append(self._read_string(char))
                continue

            # 模板字符串
            if char == '`':
                # TODO: 实现模板字符串解析
                self.tokens.append(self._read_string(char))
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
            self.tokens.append(self._make_token(TokenType.换行, '\\n'))
        while len(self.indent_stack) > 1:
            self.indent_stack.pop()
            self.tokens.append(self._make_token(TokenType.回退, 0))

        self.tokens.append(self._make_token(TokenType.文件结束, None))
        return self.tokens

    def _read_operator_or_punctuation(self) -> Token | None:
        """读取运算符或标点符号"""
        char = self.current_char
        line, col = self.line, self.column

        # 双字符运算符（先检查）
        two_chars = char + (self.peek() or '')
        three_chars = two_chars + (self.peek(2) or '')

        if three_chars == '...':
            self.advance(); self.advance(); self.advance()
            return self._make_token(TokenType.展开, '...', line, col)

        if two_chars == '=>':
            self.advance(); self.advance()
            return self._make_token(TokenType.箭头, '=>', line, col)
        if two_chars == '|>':
            self.advance(); self.advance()
            return self._make_token(TokenType.管道, '|>', line, col)
        if two_chars == '==':
            self.advance(); self.advance()
            return self._make_token(TokenType.等于, '==', line, col)
        if two_chars == '!=':
            self.advance(); self.advance()
            return self._make_token(TokenType.不等于, '!=', line, col)
        if two_chars == '>=':
            self.advance(); self.advance()
            return self._make_token(TokenType.大于等于, '>=', line, col)
        if two_chars == '<=':
            self.advance(); self.advance()
            return self._make_token(TokenType.小于等于, '<=', line, col)
        if two_chars == '**':
            self.advance(); self.advance()
            return self._make_token(TokenType.幂, '**', line, col)

        # 单字符运算符
        single_ops = {
            '+': TokenType.加,
            '-': TokenType.减,
            '*': TokenType.乘,
            '/': TokenType.除,
            '%': TokenType.取余,
            '=': TokenType.赋值,
            '>': TokenType.大于,
            '<': TokenType.小于,
            '.': TokenType.点,
            '!': TokenType.感叹号,
        }

        # 标点符号（兼容中/西文）
        punctuation = {
            '(': TokenType.左括号, '（': TokenType.左括号,
            ')': TokenType.右括号, '）': TokenType.右括号,
            '[': TokenType.左方括号,
            ']': TokenType.右方括号,
            '{': TokenType.左花括号,
            '}': TokenType.右花括号,
            ',': TokenType.逗号, '，': TokenType.逗号,
            ':': TokenType.冒号, '：': TokenType.冒号,
        }

        if char in single_ops:
            self.advance()
            return self._make_token(single_ops[char], char, line, col)

        if char in punctuation:
            self.advance()
            return self._make_token(punctuation[char], char, line, col)

        return None
