"""
可变参数测试
============
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

import pytest
from dao.lexer import Lexer
from dao.parser import Parser
from dao.interpreter import Interpreter


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


def eval_env(source: str):
    tokens = Lexer(source).tokenize()
    ast = Parser(tokens).parse()
    interpreter = Interpreter()
    interpreter.execute(ast)
    return interpreter.global_env


class TestRestParams:
    def test_basic_rest_param(self):
        output = capture_output(
            "函数 求和(...数字们)\n"
            "    定义 结果 = 0\n"
            "    遍历 数字 在 数字们\n"
            "        结果 = 结果 + 数字\n"
            "    返回 结果\n"
            "打印(求和(1, 2, 3, 4, 5))\n"
        )
        assert output == "15"

    def test_rest_param_with_regular(self):
        output = capture_output(
            "函数 问候(名字, ...其他)\n"
            "    打印(名字)\n"
            "    打印(其他)\n"
            "问候(\"张三\", \"李四\", \"王五\")\n"
        )
        lines = output.split("\n")
        assert "张三" in lines[0]

    def test_rest_param_empty(self):
        env = eval_env(
            "函数 f(...args)\n"
            "    返回 args\n"
            "定义 r = f()\n"
        )
        assert env.get("r") == []

    def test_rest_param_no_extra(self):
        env = eval_env(
            "函数 f(甲, ...尾)\n"
            "    返回 尾\n"
            "定义 r = f(1)\n"
        )
        assert env.get("r") == []