"""
元组字面量测试
============
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

import pytest
from dao.lexer import Lexer
from dao.parser import Parser
from dao.interpreter import Interpreter
from dao.ast_nodes import TupleLiteral, VariableDecl


def run(source: str) -> object:
    tokens = Lexer(source).tokenize()
    ast = Parser(tokens).parse()
    interpreter = Interpreter()
    return interpreter.execute(ast)


def eval_env(source: str):
    tokens = Lexer(source).tokenize()
    ast = Parser(tokens).parse()
    interpreter = Interpreter()
    interpreter.execute(ast)
    return interpreter.global_env


def capture_output(source: str) -> str:
    import io
    from contextlib import redirect_stdout
    f = io.StringIO()
    with redirect_stdout(f):
        run(source)
    return f.getvalue().strip()


def parse_expr(source: str):
    tokens = Lexer(source).tokenize()
    return Parser(tokens).parse()


class TestTupleLiteral:
    def test_empty_tuple(self):
        env = eval_env("定义 t = ()\n")
        assert env.get("t") == ()

    def test_multi_element_tuple(self):
        env = eval_env("定义 t = (1, 2, 3)\n")
        assert env.get("t") == (1, 2, 3)

    def test_mixed_type_tuple(self):
        env = eval_env('定义 t = (1, "你好", 真)\n')
        assert env.get("t") == (1, "你好", True)

    def test_single_element_tuple(self):
        env = eval_env("定义 t = (1,)\n")
        assert env.get("t") == (1,)

    def test_paren_expr_not_tuple(self):
        env = eval_env("定义 x = (1 + 2)\n")
        assert env.get("x") == 3
        assert not isinstance(env.get("x"), tuple)

    def test_nested_tuple(self):
        env = eval_env("定义 t = (1, (2, 3))\n")
        assert env.get("t") == (1, (2, 3))

    def test_tuple_in_function_return(self):
        output = capture_output("函数 f()\n    返回 (1, 2)\n打印(f())\n")
        assert output == "(1, 2)"

    def test_tuple_destructure(self):
        env = eval_env("定义 [a, b] = (10, 20)\n")
        assert env.get("a") == 10
        assert env.get("b") == 20

    def test_parse_tuple_ast(self):
        ast = parse_expr("定义 t = (1, 2, 3)\n")
        stmt = ast.statements[0]
        assert isinstance(stmt, VariableDecl)
        assert isinstance(stmt.value, TupleLiteral)
        assert len(stmt.value.elements) == 3

    def test_tuple_print(self):
        output = capture_output("打印((1, 2, 3))\n")
        assert output == "(1, 2, 3)"
