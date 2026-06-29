"""
语法分析器测试
=============
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

import pytest
from dao.lexer import Lexer
from dao.parser import Parser
from dao.ast_nodes import *


def parse(source: str) -> Program:
    """辅助函数：源代码 → AST"""
    tokens = Lexer(source).tokenize()
    return Parser(tokens).parse()


class TestParserVariables:
    """变量声明解析测试"""

    def test_variable_decl(self):
        ast = parse("定义 x = 42\n")
        assert len(ast.statements) == 1
        stmt = ast.statements[0]
        assert isinstance(stmt, VariableDecl)
        assert stmt.name == "x"
        assert isinstance(stmt.value, NumberLiteral)
        assert stmt.value.value == 42

    def test_constant_decl(self):
        ast = parse("常量 PI = 3\n")
        stmt = ast.statements[0]
        assert isinstance(stmt, VariableDecl)
        assert stmt.is_constant is True

    def test_string_variable(self):
        ast = parse('定义 名字 = "张三"\n')
        stmt = ast.statements[0]
        assert isinstance(stmt.value, StringLiteral)
        assert stmt.value.value == "张三"


class TestParserExpressions:
    """表达式解析测试"""

    def test_binary_add(self):
        ast = parse("定义 x = 1 + 2\n")
        stmt = ast.statements[0]
        assert isinstance(stmt.value, BinaryOp)
        assert stmt.value.operator == '+'

    def test_operator_precedence(self):
        """运算符优先级：* 优先于 +"""
        ast = parse("定义 x = 1 + 2 * 3\n")
        stmt = ast.statements[0]
        expr = stmt.value
        assert isinstance(expr, BinaryOp)
        assert expr.operator == '+'
        assert isinstance(expr.right, BinaryOp)
        assert expr.right.operator == '*'

    def test_power_right_associative(self):
        """幂运算右结合"""
        ast = parse("定义 x = 2 ** 3 ** 2\n")
        stmt = ast.statements[0]
        expr = stmt.value
        assert isinstance(expr, BinaryOp)
        assert expr.operator == '**'
        assert isinstance(expr.right, BinaryOp)
        assert expr.right.operator == '**'

    def test_list_literal(self):
        ast = parse("定义 x = [1, 2, 3]\n")
        stmt = ast.statements[0]
        assert isinstance(stmt.value, ListLiteral)
        assert len(stmt.value.elements) == 3

    def test_dict_literal(self):
        ast = parse('定义 x = {"a": 1}\n')
        stmt = ast.statements[0]
        assert isinstance(stmt.value, DictLiteral)
        assert len(stmt.value.pairs) == 1

    def test_function_call(self):
        ast = parse("打印(42)\n")
        stmt = ast.statements[0]
        assert isinstance(stmt, ExpressionStmt)
        assert isinstance(stmt.expression, FunctionCall)


class TestParserControlFlow:
    """控制流解析测试"""

    def test_if_simple(self):
        ast = parse("如果 x > 0\n    打印(x)\n")
        stmt = ast.statements[0]
        assert isinstance(stmt, IfStmt)

    def test_if_else(self):
        source = "如果 x > 0\n    打印(1)\n否则\n    打印(0)\n"
        ast = parse(source)
        stmt = ast.statements[0]
        assert isinstance(stmt, IfStmt)
        assert len(stmt.else_body) > 0

    def test_while_loop(self):
        source = "当 x < 10\n    打印(x)\n"
        ast = parse(source)
        stmt = ast.statements[0]
        assert isinstance(stmt, WhileStmt)

    def test_for_in_loop(self):
        source = "遍历 x 在 列表\n    打印(x)\n"
        ast = parse(source)
        stmt = ast.statements[0]
        assert isinstance(stmt, ForInStmt)

    def test_for_range_loop(self):
        source = "遍历 i 从 1 到 10\n    打印(i)\n"
        ast = parse(source)
        stmt = ast.statements[0]
        assert isinstance(stmt, ForRangeStmt)


class TestParserFunctions:
    """函数解析测试"""

    def test_function_decl(self):
        source = "函数 加法(甲, 乙)\n    返回 甲 + 乙\n"
        ast = parse(source)
        stmt = ast.statements[0]
        assert isinstance(stmt, FunctionDecl)
        assert stmt.name == "加法"
        assert stmt.params == ["甲", "乙"]

    def test_lambda(self):
        source = "定义 f = 函数(x) => x * 2\n"
        ast = parse(source)
        stmt = ast.statements[0]
        assert isinstance(stmt.value, LambdaExpr)

    def test_lambda_block_body(self):
        source = "定义 f = 函数(x) =>\n    定义 y = x + 1\n    返回 y\n"
        ast = parse(source)
        stmt = ast.statements[0]
        assert isinstance(stmt.value, LambdaExpr)
        assert isinstance(stmt.value.body, list)
        assert len(stmt.value.body) == 2


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
