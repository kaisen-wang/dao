"""
逻辑运算符 &&/||/! 测试
======================
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


class TestLogicOperators:
    def test_and_symbol(self):
        env = eval_env("定义 r = 真 && 假\n")
        assert env.get("r") == False

    def test_or_symbol(self):
        env = eval_env("定义 r = 真 || 假\n")
        assert env.get("r") == True

    def test_not_symbol(self):
        env = eval_env("定义 r = !假\n")
        assert env.get("r") == True

    def test_and_short_circuit(self):
        env = eval_env("定义 r = 假 && 1/0\n")
        assert env.get("r") == False

    def test_or_short_circuit(self):
        env = eval_env("定义 r = 真 || 1/0\n")
        assert env.get("r") == True

    def test_chinese_keywords_still_work(self):
        env = eval_env("定义 r = 真 并且 假\n")
        assert env.get("r") == False

    def test_mixed_operators(self):
        env = eval_env("定义 r = (真 || 假) && 真\n")
        assert env.get("r") == True