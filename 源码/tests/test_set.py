"""
集合字面量测试
============
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

import pytest
from dao.lexer import Lexer
from dao.parser import Parser
from dao.interpreter import Interpreter
from dao.ast_nodes import SetLiteral, VariableDecl


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


def parse_expr(source: str):
    tokens = Lexer(source).tokenize()
    return Parser(tokens).parse()


class TestSetLiteral:
    def test_set_literal(self):
        env = eval_env("定义 s = {1, 2, 3}\n")
        assert env.get("s") == {1, 2, 3}

    def test_set_literal_mixed_types(self):
        env = eval_env('定义 s = {1, "你好", 真}\n')
        assert env.get("s") == {1, "你好", True}

    def test_set_literal_duplicates(self):
        env = eval_env("定义 s = {1, 2, 2, 3}\n")
        assert env.get("s") == {1, 2, 3}

    def test_empty_dict_not_set(self):
        env = eval_env("定义 d = {}\n")
        assert env.get("d") == {}

    def test_dict_still_works(self):
        env = eval_env('定义 d = {"姓名": "张三", "年龄": 30}\n')
        assert env.get("d") == {"姓名": "张三", "年龄": 30}

    def test_set_with_expressions(self):
        env = eval_env("定义 s = {1 + 1, 2 + 2}\n")
        assert env.get("s") == {2, 4}

    def test_parse_set_ast(self):
        ast = parse_expr("定义 s = {1, 2, 3}\n")
        stmt = ast.statements[0]
        assert isinstance(stmt, VariableDecl)
        assert isinstance(stmt.value, SetLiteral)
        assert len(stmt.value.elements) == 3