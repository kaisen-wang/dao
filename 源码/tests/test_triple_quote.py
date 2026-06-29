"""
三引号字符串测试
================
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


class TestTripleQuotedString:
    def test_basic_triple_quoted(self):
        env = eval_env('定义 s = """你好世界"""\n')
        assert env.get("s") == "你好世界"

    def test_multiline_triple_quoted(self):
        env = eval_env('定义 s = """第一行\n第二行\n第三行"""\n')
        assert "第一行" in env.get("s")
        assert "第二行" in env.get("s")

    def test_single_quoted_still_works(self):
        env = eval_env('定义 s = "你好"\n')
        assert env.get("s") == "你好"

    def test_triple_single_quotes(self):
        env = eval_env("定义 s = '''你好世界'''\n")
        assert env.get("s") == "你好世界"