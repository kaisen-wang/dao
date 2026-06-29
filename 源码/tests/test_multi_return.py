"""
多返回值语法糖测试
==================
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


class TestMultiReturn:
    def test_multi_return_no_parens(self):
        env = eval_env(
            "函数 求商和余数(被除数, 除数)\n"
            "    返回 被除数 // 除数, 被除数 % 除数\n"
            "定义 (商, 余) = 求商和余数(17, 5)\n"
        )
        assert env.get("商") == 3
        assert env.get("余") == 2

    def test_multi_return_three_values(self):
        env = eval_env(
            "函数 三值()\n"
            "    返回 1, 2, 3\n"
            "定义 (甲, 乙, 丙) = 三值()\n"
        )
        assert env.get("甲") == 1
        assert env.get("乙") == 2
        assert env.get("丙") == 3

    def test_single_return_still_works(self):
        env = eval_env(
            "函数 单值()\n"
            "    返回 42\n"
            "定义 结果 = 单值()\n"
        )
        assert env.get("结果") == 42

    def test_multi_return_with_parens_still_works(self):
        env = eval_env(
            "函数 求商和余数(被除数, 除数)\n"
            "    返回 (被除数 // 除数, 被除数 % 除数)\n"
            "定义 (商, 余) = 求商和余数(17, 5)\n"
        )
        assert env.get("商") == 3
        assert env.get("余") == 2

    def test_multi_return_print(self):
        output = capture_output(
            "函数 f()\n"
            "    返回 1, 2\n"
            "打印(f())\n"
        )
        assert output == "(1, 2)"