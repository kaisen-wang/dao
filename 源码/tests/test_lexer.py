"""
词法分析器测试
=============
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

import pytest
from dao.lexer import Lexer
from dao.tokens import TokenType
from dao.errors import 词法错误


class TestLexerBasics:
    """基础词法分析测试"""

    def test_empty_source(self):
        """空源代码应只产生EOF"""
        lexer = Lexer("")
        tokens = lexer.tokenize()
        assert tokens[-1].type == TokenType.文件结束

    def test_number_integer(self):
        """整数字面量"""
        lexer = Lexer("42\n")
        tokens = lexer.tokenize()
        assert tokens[0].type == TokenType.数值
        assert tokens[0].value == 42

    def test_number_float(self):
        """浮点数字面量"""
        lexer = Lexer("3.14\n")
        tokens = lexer.tokenize()
        assert tokens[0].type == TokenType.数值
        assert tokens[0].value == 3.14

    def test_number_with_underscore(self):
        """带下划线的数值"""
        lexer = Lexer("1_000_000\n")
        tokens = lexer.tokenize()
        assert tokens[0].type == TokenType.数值
        assert tokens[0].value == 1000000

    def test_string_double_quote(self):
        """双引号字符串"""
        lexer = Lexer('"你好"\n')
        tokens = lexer.tokenize()
        assert tokens[0].type == TokenType.文本
        assert tokens[0].value == "你好"

    def test_string_single_quote(self):
        """单引号字符串"""
        lexer = Lexer("'世界'\n")
        tokens = lexer.tokenize()
        assert tokens[0].type == TokenType.文本
        assert tokens[0].value == "世界"

    def test_string_escape(self):
        """字符串转义"""
        lexer = Lexer('"你好\\n世界"\n')
        tokens = lexer.tokenize()
        assert tokens[0].value == "你好\n世界"


class TestLexerKeywords:
    """关键字识别测试"""

    def test_keyword_定义(self):
        lexer = Lexer("定义 x = 10\n")
        tokens = lexer.tokenize()
        assert tokens[0].type == TokenType.定义

    def test_keyword_常量(self):
        lexer = Lexer("常量 PI = 3\n")
        tokens = lexer.tokenize()
        assert tokens[0].type == TokenType.常量

    def test_keyword_函数(self):
        lexer = Lexer("函数 加(甲, 乙)\n")
        tokens = lexer.tokenize()
        assert tokens[0].type == TokenType.函数

    def test_keyword_如果(self):
        lexer = Lexer("如果 x > 0\n")
        tokens = lexer.tokenize()
        assert tokens[0].type == TokenType.如果

    def test_keyword_否则如果(self):
        lexer = Lexer("否则如果 x == 0\n")
        tokens = lexer.tokenize()
        assert tokens[0].type == TokenType.否则如果

    def test_keyword_真假(self):
        lexer = Lexer("真\n")
        tokens = lexer.tokenize()
        assert tokens[0].type == TokenType.真

    def test_keyword_空(self):
        lexer = Lexer("空\n")
        tokens = lexer.tokenize()
        assert tokens[0].type == TokenType.空


class TestLexerOperators:
    """运算符识别测试"""

    def test_arithmetic_operators(self):
        lexer = Lexer("1 + 2 - 3 * 4 / 5\n")
        tokens = lexer.tokenize()
        types = [t.type for t in tokens if t.type not in (TokenType.换行, TokenType.文件结束, TokenType.数值)]
        assert TokenType.加 in types
        assert TokenType.减 in types
        assert TokenType.乘 in types
        assert TokenType.除 in types

    def test_comparison_operators(self):
        lexer = Lexer("x == 1\n")
        tokens = lexer.tokenize()
        assert any(t.type == TokenType.等于 for t in tokens)

    def test_power_operator(self):
        lexer = Lexer("2 ** 10\n")
        tokens = lexer.tokenize()
        assert any(t.type == TokenType.幂 for t in tokens)

    def test_arrow_operator(self):
        lexer = Lexer("函数(x) => x\n")
        tokens = lexer.tokenize()
        assert any(t.type == TokenType.箭头 for t in tokens)

    def test_pipe_operator(self):
        lexer = Lexer("x |> f\n")
        tokens = lexer.tokenize()
        assert any(t.type == TokenType.管道 for t in tokens)


class TestLexerIndentation:
    """缩进处理测试"""

    def test_simple_indent(self):
        source = "如果 真\n    打印(1)\n"
        lexer = Lexer(source)
        tokens = lexer.tokenize()
        types = [t.type for t in tokens]
        assert TokenType.缩进 in types
        assert TokenType.回退 in types

    def test_nested_indent(self):
        source = "如果 真\n    如果 真\n        打印(1)\n"
        lexer = Lexer(source)
        tokens = lexer.tokenize()
        types = [t.type for t in tokens]
        assert types.count(TokenType.缩进) == 2
        assert types.count(TokenType.回退) == 2


class TestLexerComments:
    """注释处理测试"""

    def test_line_comment(self):
        lexer = Lexer("// 这是注释\n42\n")
        tokens = lexer.tokenize()
        assert tokens[0].type == TokenType.数值

    def test_chinese_comment(self):
        lexer = Lexer("注：这也是注释\n42\n")
        tokens = lexer.tokenize()
        assert tokens[0].type == TokenType.数值

    def test_inline_comment(self):
        lexer = Lexer("42 // 行尾注释\n")
        tokens = lexer.tokenize()
        assert tokens[0].type == TokenType.数值


class TestLexerPunctuation:
    """中西文标点兼容测试"""

    def test_chinese_parentheses(self):
        lexer = Lexer("加（1, 2）\n")
        tokens = lexer.tokenize()
        assert any(t.type == TokenType.左括号 for t in tokens)
        assert any(t.type == TokenType.右括号 for t in tokens)

    def test_chinese_comma(self):
        lexer = Lexer("加(1，2)\n")
        tokens = lexer.tokenize()
        assert any(t.type == TokenType.逗号 for t in tokens)


class TestLexerErrors:
    """错误处理测试"""

    def test_unclosed_string(self):
        lexer = Lexer('"未闭合的字符串\n')
        with pytest.raises(词法错误):
            lexer.tokenize()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
