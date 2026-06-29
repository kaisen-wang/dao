"""
整除运算符测试
==============
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

import pytest
from dao.lexer import Lexer
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