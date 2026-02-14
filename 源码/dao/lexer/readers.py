"""
词法读取方法混入
===============

包含所有具体 Token 的读取方法：
- 注释跳过（单行、多行）
- 字符串字面量（西文引号、中文引号、转义序列）
- 模板字符串（`你好 {名字}`）
- 数值字面量（整数、浮点数、下划线分隔）
- 标识符与关键字
- 运算符与标点符号（含中西文标点兼容）

通过 Python mixin 模式，在运行时与 Lexer 组合。
"""

from ..errors import 词法错误
from ..tokens import KEYWORDS, Token, TokenType


class LexerReaders:
    """Token 读取方法集（混入类）"""

    # ========================
    # 注释
    # ========================

    def _skip_line_comment(self):
        """跳过单行注释 (// 或 注：)"""
        while self.current_char is not None and self.current_char != "\n":
            if self.current_char == "/" and self.peek() == "/":
                self.advance()
                self.advance()
                while self.current_char is not None and self.current_char != "\n":
                    self.advance()
            elif self.current_char == "注" and self.peek() == "：":
                self.advance()
                self.advance()
                while self.current_char is not None and self.current_char != "\n":
                    self.advance()
            else:
                break

    def _skip_block_comment(self):
        """跳过多行注释 /* ... */，支持嵌套"""
        if self.current_char == "/" and self.peek() == "*":
            depth = 1
            self.advance()
            self.advance()
            while depth > 0:
                if self.current_char is None:
                    raise 词法错误("未闭合的多行注释")
                elif self.current_char == "/" and self.peek() == "*":
                    depth += 1
                    self.advance()
                    self.advance()
                elif self.current_char == "*" and self.peek() == "/":
                    depth -= 1
                    self.advance()
                    self.advance()
                else:
                    self.advance()

    # ========================
    # 字符串
    # ========================

    # 中文引号 → 对应闭合引号的映射
    _QUOTE_PAIRS = {
        "\u201c": "\u201d",  # " → "
        "\u2018": "\u2019",  # ' → '
        "\u300c": "\u300d",  # 「 → 」
    }

    def _read_string(self, quote_char: str) -> Token:
        """读取字符串字面量（支持中/西文引号）"""
        start_line = self.line
        start_col = self.column
        # 确定闭合引号：中文引号左右不同，西文引号左右相同
        close_char = self._QUOTE_PAIRS.get(quote_char, quote_char)
        self.advance()  # 跳过开头引号
        result = []

        while self.current_char is not None and self.current_char != close_char:
            if self.current_char == "\\":
                self.advance()
                escape_map = {
                    "n": "\n",
                    "t": "\t",
                    "r": "\r",
                    "\\": "\\",
                    "'": "'",
                    '"': '"',
                }
                if self.current_char in escape_map:
                    result.append(escape_map[self.current_char])
                    self.advance()
                else:
                    raise 词法错误(f"未知的转义序列: \\{self.current_char}")
            else:
                result.append(self.advance())

        if self.current_char is None:
            raise 词法错误(f"未闭合的字符串，从第 {start_line} 行开始")

        self.advance()  # 跳过结束引号
        return self._make_token(TokenType.文本, "".join(result), start_line, start_col)

    # ========================
    # 模板字符串
    # ========================

    def _read_template_string(self) -> Token:
        """读取模板字符串 `你好 {名字}，{年龄}岁`"""
        start_line = self.line
        start_col = self.column
        self.advance()  # 跳过开头的 `

        parts = []  # 字符串片段列表
        expr_strings = []  # 表达式源码列表
        current_part = []  # 当前正在构建的字符串片段

        while self.current_char is not None and self.current_char != "`":
            if self.current_char == "{":
                # 保存当前字符串片段，开始读取表达式
                parts.append("".join(current_part))
                current_part = []
                self.advance()  # 跳过 {

                # 读取表达式源码，直到匹配的 }
                depth = 1
                expr_chars = []
                while self.current_char is not None and depth > 0:
                    if self.current_char == "{":
                        depth += 1
                        expr_chars.append(self.advance())
                    elif self.current_char == "}":
                        depth -= 1
                        if depth == 0:
                            break
                        expr_chars.append(self.advance())
                    elif self.current_char == '"' or self.current_char == "'":
                        # 字符串内的引号不影响 {} 匹配
                        q = self.current_char
                        expr_chars.append(self.advance())
                        while self.current_char is not None and self.current_char != q:
                            if self.current_char == "\\":
                                expr_chars.append(self.advance())
                            expr_chars.append(self.advance())
                        if self.current_char == q:
                            expr_chars.append(self.advance())
                    else:
                        expr_chars.append(self.advance())

                if self.current_char != "}":
                    raise 词法错误("模板字符串中的表达式未闭合")
                self.advance()  # 跳过 }
                expr_strings.append("".join(expr_chars))

            elif self.current_char == "\\":
                # 转义字符
                self.advance()
                escape_map = {
                    "n": "\n",
                    "t": "\t",
                    "r": "\r",
                    "\\": "\\",
                    "`": "`",
                    "{": "{",
                    "}": "}",
                }
                if self.current_char in escape_map:
                    current_part.append(escape_map[self.current_char])
                    self.advance()
                else:
                    raise 词法错误(f"未知的转义序列: \\{self.current_char}")
            else:
                current_part.append(self.advance())

        if self.current_char is None:
            raise 词法错误(f"未闭合的模板字符串，从第 {start_line} 行开始")

        self.advance()  # 跳过结束的 `
        parts.append("".join(current_part))  # 添加最后一个字符串片段

        return self._make_token(
            TokenType.模板文本,
            {"parts": parts, "exprs": expr_strings},
            start_line,
            start_col,
        )

    # ========================
    # 数值
    # ========================

    def _read_number(self) -> Token:
        """读取数值字面量（支持整数、浮点数、下划线分隔）"""
        start_line = self.line
        start_col = self.column
        result = []
        has_dot = False

        while self.current_char is not None:
            if self.current_char.isdigit():
                result.append(self.advance())
            elif (
                self.current_char == "_"
                and self.peek() is not None
                and self.peek().isdigit()
            ):
                self.advance()  # 跳过下划线
            elif (
                self.current_char == "."
                and not has_dot
                and self.peek() is not None
                and self.peek().isdigit()
            ):
                has_dot = True
                result.append(self.advance())
            else:
                break

        value_str = "".join(result)
        value = float(value_str) if has_dot else int(value_str)
        return self._make_token(TokenType.数值, value, start_line, start_col)

    # ========================
    # 标识符与关键字
    # ========================

    def _is_identifier_start(self, char: str) -> bool:
        """检查字符是否可以作为标识符的开头"""
        return char.isalpha() or char == "_" or ("\u4e00" <= char <= "\u9fff")

    def _is_identifier_char(self, char: str) -> bool:
        """检查字符是否可以作为标识符的一部分"""
        return (
            char.isalpha()
            or char.isdigit()
            or char == "_"
            or ("\u4e00" <= char <= "\u9fff")
        )

    def _read_identifier(self) -> Token:
        """读取标识符或关键字"""
        start_line = self.line
        start_col = self.column
        result = []

        while self.current_char is not None and self._is_identifier_char(
            self.current_char
        ):
            result.append(self.advance())

        word = "".join(result)

        # 特殊处理：异步函数（检查是否是异步函数声明）
        if word == "异步函数":
            return (
                self._make_token(TokenType.异步, "异步", start_line, start_col),
                self._make_token(TokenType.函数, "函数", start_line, start_col + 2),
            )
        elif word == "运行异步":
            # 运行异步是内置函数名，作为标识符处理
            return self._make_token(TokenType.标识符, word, start_line, start_col)
        elif word == "异步":
            # 向前看是否紧跟"函数"
            saved_pos = self.pos
            saved_line = self.line
            saved_col = self.column

            # 跳过空格
            while self.current_char == " ":
                self.advance()

            if self.current_char is not None and self._is_identifier_start(
                self.current_char
            ):
                next_chars = []
                while self.current_char is not None and self._is_identifier_char(
                    self.current_char
                ):
                    next_chars.append(self.advance())
                next_word = "".join(next_chars)
                if next_word == "函数":
                    return (
                        self._make_token(TokenType.异步, "异步", start_line, start_col),
                        self._make_token(
                            TokenType.函数, "函数", self.line, self.column
                        ),
                    )

            # 回退
            self.pos = saved_pos
            self.line = saved_line
            self.column = saved_col

        # 特殊处理：否则如果（两个词组合的关键字）
        if word == "否则":
            # 向前看是否紧跟"如果"
            saved_pos = self.pos
            saved_line = self.line
            saved_col = self.column

            # 跳过空格
            while self.current_char == " ":
                self.advance()

            if self.current_char is not None and self._is_identifier_start(
                self.current_char
            ):
                next_chars = []
                while self.current_char is not None and self._is_identifier_char(
                    self.current_char
                ):
                    next_chars.append(self.advance())
                next_word = "".join(next_chars)
                if next_word == "如果":
                    return self._make_token(
                        TokenType.否则如果, "否则如果", start_line, start_col
                    )

            # 回退
            self.pos = saved_pos
            self.line = saved_line
            self.column = saved_col

        # 检查是否是关键字
        token_type = KEYWORDS.get(word, TokenType.标识符)
        return self._make_token(token_type, word, start_line, start_col)

    # ========================
    # 运算符与标点
    # ========================

    def _read_operator_or_punctuation(self) -> Token:
        """读取运算符或标点符号"""
        char = self.current_char
        line, col = self.line, self.column

        if char is None:
            raise 词法错误("未预期的文件结束")

        # 双字符运算符（先检查）
        two_chars = char + (self.peek() or "")
        three_chars = two_chars + (self.peek(2) or "")

        if three_chars == "...":
            self.advance()
            self.advance()
            self.advance()
            return self._make_token(TokenType.展开, "...", line, col)

        if two_chars == "=>":
            self.advance()
            self.advance()
            return self._make_token(TokenType.箭头, "=>", line, col)
        if two_chars == "|>":
            self.advance()
            self.advance()
            return self._make_token(TokenType.管道, "|>", line, col)
        if two_chars == "==":
            self.advance()
            self.advance()
            return self._make_token(TokenType.等于, "==", line, col)
        if two_chars == "!=":
            self.advance()
            self.advance()
            return self._make_token(TokenType.不等于, "!=", line, col)
        if two_chars == ">=":
            self.advance()
            self.advance()
            return self._make_token(TokenType.大于等于, ">=", line, col)
        if two_chars == "<=":
            self.advance()
            self.advance()
            return self._make_token(TokenType.小于等于, "<=", line, col)
        if two_chars == "**":
            self.advance()
            self.advance()
            return self._make_token(TokenType.幂, "**", line, col)

        # 单字符运算符
        single_ops = {
            "+": TokenType.加,
            "-": TokenType.减,
            "*": TokenType.乘,
            "/": TokenType.除,
            "%": TokenType.取余,
            "=": TokenType.赋值,
            ">": TokenType.大于,
            "<": TokenType.小于,
            ".": TokenType.点,
            "!": TokenType.感叹号,
        }

        # 标点符号（兼容中/西文）
        punctuation = {
            "(": TokenType.左括号,
            "（": TokenType.左括号,
            ")": TokenType.右括号,
            "）": TokenType.右括号,
            "[": TokenType.左方括号,
            "]": TokenType.右方括号,
            "{": TokenType.左花括号,
            "}": TokenType.右花括号,
            ",": TokenType.逗号,
            "，": TokenType.逗号,
            ":": TokenType.冒号,
            "：": TokenType.冒号,
        }

        if char in single_ops:
            self.advance()
            return self._make_token(single_ops[char], char, line, col)

        if char in punctuation:
            token_type = punctuation[char]
            # 追踪括号嵌套深度（用于多行表达式支持）
            if token_type in (TokenType.左括号, TokenType.左方括号, TokenType.左花括号):
                self._bracket_depth += 1
            elif token_type in (
                TokenType.右括号,
                TokenType.右方括号,
                TokenType.右花括号,
            ):
                self._bracket_depth = max(0, self._bracket_depth - 1)
            self.advance()
            return self._make_token(token_type, char, line, col)

        return None

    def _read_logic_variable(self) -> Token:
        """读取逻辑变量 (?变量名)"""
        start_line = self.line
        start_col = self.column
        self.advance()  # 跳过 ?

        result = ["?"]

        # 读取变量名（标识符）
        while self.current_char is not None and self._is_identifier_char(
            self.current_char
        ):
            result.append(self.advance())

        word = "".join(result)
        return self._make_token(TokenType.标识符, word, start_line, start_col)

    def _read_macro_injection(self) -> Token:
        """读取宏注入表达式 ($变量名)"""
        start_line = self.line
        start_col = self.column
        self.advance()  # 跳过 $

        result = ["$"]

        # 读取变量名（标识符）
        while self.current_char is not None and self._is_identifier_char(
            self.current_char
        ):
            result.append(self.advance())

        word = "".join(result)
        return self._make_token(TokenType.标识符, word, start_line, start_col)
