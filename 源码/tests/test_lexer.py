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


class TestMultilinePipe:
    """多行管道续行测试"""

    def _token_types(self, source: str) -> list[TokenType]:
        return [t.type for t in Lexer(source).tokenize()]

    def test_pipe_continuation_with_indent(self):
        """T1: 行首管道续行（有缩进）"""
        source = "数据\n    |> 映射(f)\n"
        types = self._token_types(source)
        idx_data = types.index(TokenType.标识符)
        idx_pipe = types.index(TokenType.管道)
        assert idx_pipe == idx_data + 1

    def test_pipe_continuation_no_indent(self):
        """T2: 行首管道续行（无缩进）"""
        source = "数据\n|> 映射(f)\n"
        types = self._token_types(source)
        idx_data = types.index(TokenType.标识符)
        idx_pipe = types.index(TokenType.管道)
        assert idx_pipe == idx_data + 1

    def test_pipe_chain_continuation(self):
        """T3: 多级管道链续行"""
        source = "数据\n    |> 映射(f)\n    |> 筛选(g)\n    |> 排序()\n"
        types = self._token_types(source)
        pipe_indices = [i for i, t in enumerate(types) if t == TokenType.管道]
        assert len(pipe_indices) == 3
        for i in range(len(pipe_indices) - 1):
            assert pipe_indices[i + 1] > pipe_indices[i]

    def test_indentation_consistency_after_pipe(self):
        """T4: 管道链结束后缩进正确恢复"""
        source = "定义 x = 数据\n    |> 映射(f)\n打印(x)\n"
        types = self._token_types(source)
        assert TokenType.缩进 not in types
        assert TokenType.回退 not in types

    def test_pipe_with_bracket_continuation(self):
        """T5: 管道续行与括号续行共存"""
        source = "打印(数据\n    |> 映射(f))\n"
        types = self._token_types(source)
        assert TokenType.管道 in types

    def test_single_line_pipe_unchanged(self):
        """T6: 单行管道兼容性"""
        source = "数据 |> 映射(f) |> 筛选(g)\n"
        types = self._token_types(source)
        pipe_indices = [i for i, t in enumerate(types) if t == TokenType.管道]
        assert len(pipe_indices) == 2

    def test_mixed_single_multiline_pipe(self):
        """T7: 混合单行和多行管道"""
        source = "数据 |> 映射(f)\n    |> 筛选(g)\n"
        types = self._token_types(source)
        pipe_indices = [i for i, t in enumerate(types) if t == TokenType.管道]
        assert len(pipe_indices) == 2

    def test_pipe_in_assignment(self):
        """T8: 赋值语句右侧多行管道"""
        source = "定义 结果 = 数据\n    |> 映射(f)\n"
        types = self._token_types(source)
        idx_pipe = types.index(TokenType.管道)
        idx_eq = types.index(TokenType.赋值)
        assert idx_pipe > idx_eq

    def test_pipe_without_predecessor(self):
        """T9: 管道运算符无前驱表达式"""
        from dao.parser import Parser
        from dao.errors import 语法错误
        source = "|> 映射(f)\n"
        tokens = Lexer(source).tokenize()
        with pytest.raises(语法错误):
            Parser(tokens).parse()

    def test_pipe_inside_indent_block(self):
        """T10: 管道续行在缩进块内"""
        source = "如果 真\n    定义 x = 数据\n        |> 映射(f)\n"
        types = self._token_types(source)
        assert TokenType.缩进 in types
        assert TokenType.管道 in types

    def test_indent_dedent_after_pipe(self):
        """T11: 管道续行后缩进回退"""
        source = "定义 x = 数据\n    |> 映射(f)\n打印(x)\n"
        types = self._token_types(source)
        assert types.count(TokenType.缩进) == 0
        assert types.count(TokenType.回退) == 0

    def test_empty_line_before_pipe(self):
        """T12: 空行和注释行不触发续行"""
        source = "数据\n\n    |> 映射(f)\n"
        types = self._token_types(source)
        idx_data = types.index(TokenType.标识符)
        idx_pipe = types.index(TokenType.管道)
        assert idx_pipe == idx_data + 1

    def test_pipe_bracket_cross(self):
        """T13: 管道续行与括号续行交叉"""
        source = "f(数据\n    |> 映射(g))\n"
        types = self._token_types(source)
        assert TokenType.管道 in types


class TestMultilinePipeExecution:
    """多行管道端到端执行测试"""

    def _run(self, source: str) -> object:
        from dao.interpreter import Interpreter
        from dao.parser import Parser
        tokens = Lexer(source).tokenize()
        ast = Parser(tokens).parse()
        return Interpreter().execute(ast)

    def _capture(self, source: str) -> str:
        import io
        from contextlib import redirect_stdout
        f = io.StringIO()
        with redirect_stdout(f):
            self._run(source)
        return f.getvalue().strip()

    def test_multiline_pipe_execution(self):
        """多行管道链执行"""
        source = (
            '定义 数列 = [3, 1, 4, 1, 5]\n'
            '定义 结果 = 数列\n'
            '    |> 排序()\n'
            '打印(结果)\n'
        )
        output = self._capture(source)
        assert output == "[1, 1, 3, 4, 5]"

    def test_multiline_pipe_chain_execution(self):
        """多级多行管道链执行"""
        source = (
            '定义 数列 = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10]\n'
            '定义 结果 = 数列\n'
            '    |> 筛选(函数(x) => x % 2 == 0)\n'
            '    |> 映射(函数(x) => x * x)\n'
            '打印(结果)\n'
        )
        output = self._capture(source)
        assert output == "[4, 16, 36, 64, 100]"

    def test_multiline_pipe_in_assignment(self):
        """赋值右侧多行管道执行"""
        source = (
            '定义 结果 = [1, 2, 3]\n'
            '    |> 映射(函数(x) => x * 2)\n'
            '打印(结果)\n'
        )
        output = self._capture(source)
        assert output == "[2, 4, 6]"

    def test_mixed_single_multiline_pipe_execution(self):
        """混合单行多行管道执行"""
        source = (
            '定义 结果 = [1, 2, 3] |> 映射(函数(x) => x * 2)\n'
            '    |> 筛选(函数(x) => x > 4)\n'
            '打印(结果)\n'
        )
        output = self._capture(source)
        assert output == "[6]"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
