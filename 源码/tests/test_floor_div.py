"""
整除运算符测试
==============
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

import pytest
from dao.lexer import Lexer
from dao.tokens import TokenType
from dao.parser import Parser
from dao.interpreter import Interpreter


def eval_env(source: str):
    tokens = Lexer(source).tokenize()
    ast = Parser(tokens).parse()
    interpreter = Interpreter()
    interpreter.execute(ast)
    return interpreter.global_env


def capture_output(source: str) -> str:
    import io
    from contextlib import redirect_stdout
    tokens = Lexer(source).tokenize()
    ast = Parser(tokens).parse()
    interpreter = Interpreter()
    f = io.StringIO()
    with redirect_stdout(f):
        interpreter.execute(ast)
    return f.getvalue().strip()


class TestFloorDiv:
    def test_basic_floor_div(self):
        env = eval_env("定义 r = 10 // 3\n")
        assert env.get("r") == 3

    def test_floor_div_exact(self):
        env = eval_env("定义 r = 12 // 4\n")
        assert env.get("r") == 3

    def test_floor_div_negative(self):
        env = eval_env("定义 r = -10 // 3\n")
        assert env.get("r") == -4

    def test_comment_still_works(self):
        output = capture_output("// 这是注释\n打印(42)\n")
        assert output == "42"

    def test_floor_div_in_expression(self):
        env = eval_env("定义 r = (10 + 5) // 4\n")
        assert env.get("r") == 3

    def test_comment_after_code(self):
        output = capture_output("定义 x = 5\n// 行尾注释\n打印(x)\n")
        assert output == "5"


class TestFloorDivBoundaries:
    """// 歧义判别的边界用例：锁定「上一 token 可结束表达式 + 后继操作数」状态机语义"""

    @staticmethod
    def _types(source: str):
        return [
            t.type
            for t in Lexer(source).tokenize()
            if t.type not in (TokenType.换行, TokenType.文件结束)
        ]

    def test_negative_left_operand(self):
        """负号之后：-10 // 3 的 // 必须识别为整除"""
        assert TokenType.整除 in self._types("定义 r = -10 // 3\n")
        assert eval_env("定义 r = -10 // 3\n").get("r") == -4

    def test_negative_right_operand(self):
        """// 后紧跟负号：10 // -3 的 // 必须识别为整除"""
        assert TokenType.整除 in self._types("定义 r = 10 // -3\n")
        assert eval_env("定义 r = 10 // -3\n").get("r") == -4

    def test_after_function_call_is_comment(self):
        """函数调用之后：f() // 说明 视为注释，不产生整除 token"""
        assert TokenType.整除 not in self._types("f() // 说明文字\n")

    def test_after_right_bracket_with_digit_is_floor_div(self):
        """右括号之后接数字：(10 + 5) // 4 必须识别为整除"""
        assert TokenType.整除 in self._types("定义 r = (10 + 5) // 4\n")
        assert eval_env("定义 r = (10 + 5) // 4\n").get("r") == 3

    def test_after_right_bracket_with_identifier_is_comment(self):
        """右括号之后接标识符：[1, 2] // 说明 视为注释"""
        assert TokenType.整除 not in self._types("定义 x = [1, 2] // 说明\n")

    def test_after_string_literal_is_floor_div(self):
        """字符串之后："abc" // 2 必须识别为整除"""
        assert TokenType.整除 in self._types('定义 r = "abc" // 2\n')

    def test_trailing_slashes_without_operand_is_comment(self):
        """数字之后的 // 到行尾且无操作数：视为注释，不产生整除 token"""
        assert TokenType.整除 not in self._types("定义 x = 5 //\n")
        assert capture_output("定义 x = 5 //\n打印(x)\n") == "5"

    def test_all_comment_forms_still_work(self):
        """既有注释写法（独占行 //、注：、///、/* */）保持可用"""
        source = (
            "// 独占行注释\n"
            "注：中文注释\n"
            "/// 文档注释\n"
            "/* 块注释 */\n"
            "打印(42)\n"
        )
        types = self._types(source)
        assert TokenType.文档注释 in types
        assert capture_output(source) == "42"