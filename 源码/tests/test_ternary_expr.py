"""C 风格三元条件表达式 ``条件 ? 真值 : 假值`` 测试
====================================================

词法器把 ``?`` 识别为值恰为 '?' 的标识符；parse_conditional() 识别该形式，
复用既有 ConditionalExpr 节点与求值逻辑（``值 如果 条件 否则 值`` 仍可用）。
"""

import io
import os
import sys
from contextlib import redirect_stdout

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest

from dao.ast_nodes import ConditionalExpr
from dao.interpreter import Interpreter
from dao.lexer import Lexer
from dao.parser import Parser


def parse_expr(source: str):
    parser = Parser(Lexer(source).tokenize(), source)
    return parser.parse_expression()


def run(source: str) -> str:
    ast = Parser(Lexer(source).tokenize(), source).parse()
    f = io.StringIO()
    with redirect_stdout(f):
        Interpreter().execute(ast)
    return f.getvalue().strip()


class TestTernaryExpression:
    def test_ast_structure(self):
        expr = parse_expr('1 > 0 ? "是" : "否"')
        assert isinstance(expr, ConditionalExpr)
        assert expr.false_value.value == "否"

    def test_true_branch_execution(self):
        assert run('定义 a = 真 ? "是" : "否"\n打印(a)\n') == "是"

    def test_false_branch_execution(self):
        assert run('定义 a = 假 ? "是" : "否"\n打印(a)\n') == "否"

    def test_condition_comparison(self):
        assert run('定义 a = 1 > 0 ? "大" : "小"\n打印(a)\n') == "大"

    def test_nested_ternary_right_associative(self):
        src = '定义 a = 假 ? "一" : 真 ? "二" : "三"\n打印(a)\n'
        assert run(src) == "二"

    def test_chinese_conditional_still_works(self):
        assert run('定义 a = 真 如果 假 否则 真\n打印(a)\n') == "真"

    def test_missing_colon_chinese_error(self):
        with pytest.raises(Exception, match="三元条件表达式需要 ':'"):
            parse_expr('真 ? "是" "否"')


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
