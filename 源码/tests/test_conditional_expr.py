"""
条件表达式（三元）测试
====================
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


class TestConditionalExpr:
    def test_basic_conditional(self):
        env = eval_env('定义 结果 = "成年" 如果 真 否则 "未成年"\n')
        assert env.get("结果") == "成年"

    def test_conditional_false(self):
        env = eval_env('定义 结果 = "成年" 如果 假 否则 "未成年"\n')
        assert env.get("结果") == "未成年"

    def test_conditional_with_comparison(self):
        env = eval_env("定义 年龄 = 20\n定义 结果 = \"成年\" 如果 年龄 >= 18 否则 \"未成年\"\n")
        assert env.get("结果") == "成年"

    def test_conditional_with_expression(self):
        env = eval_env("定义 x = 5\n定义 结果 = x * 2 如果 x > 3 否则 x * 3\n")
        assert env.get("结果") == 10

    def test_conditional_in_print(self):
        output = capture_output('打印("大" 如果 10 > 5 否则 "小")\n')
        assert output == "大"

    def test_if_statement_still_works(self):
        output = capture_output("如果 真\n    打印(\"是\")\n")
        assert output == "是"