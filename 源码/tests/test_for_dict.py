"""
遍历字典双变量测试
==================
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


class TestForDictDualVar:
    def test_dict_dual_variable(self):
        output = capture_output(
            '定义 成绩 = {"数学": 95, "语文": 88}\n'
            '遍历 科目, 分数 在 成绩\n'
            '    打印(科目)\n'
        )
        assert "数学" in output
        assert "语文" in output

    def test_dict_dual_variable_values(self):
        output = capture_output(
            '定义 成绩 = {"数学": 95, "语文": 88}\n'
            '遍历 科目, 分数 在 成绩\n'
            '    打印(分数)\n'
        )
        assert "95" in output
        assert "88" in output

    def test_single_variable_still_works(self):
        output = capture_output(
            '遍历 x 在 [1, 2, 3]\n'
            '    打印(x)\n'
        )
        assert output == "1\n2\n3"