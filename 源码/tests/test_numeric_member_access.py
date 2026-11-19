"""数字下标成员访问 ``变量.0`` 的解析与执行测试
================================================

根因：parse_call() 的成员访问分支只接受标识符/关键字作为成员名，
遇到 ``数值`` token 直接报错"成员访问需要属性名"。

修复：把 ``a.0`` / ``a.12`` / ``a.-1`` 解析为 ``IndexAccess``，
复用 ``a[0]`` 的 AST 节点与求值逻辑；字符串成员访问保持不变。
"""

import io
import os
import sys
from contextlib import redirect_stdout

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest

from dao.ast_nodes import Identifier, IndexAccess, MemberAccess, NumberLiteral
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


class TestNumericMemberAccessAst:
    """AST 结构：数字下标解析为 IndexAccess"""

    def test_single_and_multi_digit_index(self):
        for src, value in (("a.0", 0), ("a.12", 12)):
            expr = parse_expr(src)
            assert isinstance(expr, IndexAccess)
            assert isinstance(expr.object, Identifier)
            assert expr.object.name == "a"
            assert isinstance(expr.index, NumberLiteral)
            assert expr.index.value == value

    def test_negative_index(self):
        expr = parse_expr("a.-1")
        assert isinstance(expr, IndexAccess)
        assert isinstance(expr.index, NumberLiteral)
        assert expr.index.value == -1

    def test_string_member_unchanged(self):
        """对象.属性 仍解析为 MemberAccess，不受影响"""
        expr = parse_expr("a.姓名")
        assert isinstance(expr, MemberAccess)
        assert expr.member == "姓名"

    def test_chinese_variable_numeric_index(self):
        """文档中的 文章库.0 形式"""
        expr = parse_expr("文章库.0")
        assert isinstance(expr, IndexAccess)
        assert isinstance(expr.object, Identifier)
        assert expr.object.name == "文章库"
        assert expr.index.value == 0


class TestNumericMemberAccessRuntime:
    """执行结果：复用现有 IndexAccess 求值逻辑"""

    def test_positive_and_negative_index_execution(self):
        src = "定义 a = [10, 20, 30]\n打印(a.0)\n打印(a.-1)\n"
        assert run(src) == "10\n30"

    def test_multi_digit_index_execution(self):
        src = "定义 a = [0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12]\n打印(a.12)\n"
        assert run(src) == "12"

    def test_non_integer_index_chinese_error(self):
        """词法把 a.0.1 合并成浮点 0.1，应报中文错误而非静默截断"""
        with pytest.raises(Exception, match="成员下标必须是整数"):
            parse_expr("a.0.1")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
