"""表达式层面逻辑约束与"并且"续行的解析测试
============================================

覆盖三类场景：

1. ``?x 在范围 a..b`` 作为【表达式】（而非仅规则体）解析时，
   ``LogicConstraint.variable`` / ``bounds`` 被真实填充；
2. 行尾 ``并且`` 后紧跟换行时，右侧表达式能继续解析；
3. 三个逻辑编程示例能被 ``Parser`` 完整解析（不要求执行成功）。

所有测试只覆盖 `dao/parser/expressions.py`（本代理所有权）的行为。
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest

from dao.ast_nodes import BinaryOp, LogicConstraint
from dao.lexer import Lexer
from dao.parser import Parser


def parse_expr(source: str):
    """把源码作为单个表达式解析，返回 (Parser, 表达式)。"""
    parser = Parser(Lexer(source).tokenize(), source)
    return parser, parser.parse_expression()


def parse_file(rel_path: str):
    """完整解析一个 .道 示例文件。"""
    path = os.path.join(os.path.dirname(__file__), "..", rel_path)
    with open(path, encoding="utf-8") as f:
        source = f.read()
    return Parser(Lexer(source).tokenize(), source).parse()


class TestConstraintAsExpression:
    """约束范围作为表达式解析"""

    def test_variable_and_bounds_are_filled(self):
        """?x 在范围 1..10 → variable='?x', bounds=(1,10)"""
        _, expr = parse_expr("?x 在范围 1..10")
        assert isinstance(expr, LogicConstraint)
        assert expr.variable == "?x"
        assert expr.operator == "在范围"
        assert expr.bounds == (1, 10)

    def test_negative_bounds(self):
        """负数上下界作为表达式解析"""
        _, expr = parse_expr("?n 在范围 -5..5")
        assert isinstance(expr, LogicConstraint)
        assert expr.variable == "?n"
        assert expr.bounds == (-5, 5)

    def test_chinese_bound_error(self):
        """非整数边界抛出中文语法错误（复用规则体的统一校验）"""
        with pytest.raises(Exception, match="约束下界必须是整数"):
            parse_expr("在范围 甲..10")

    def test_primary_compat_entry_delegates(self):
        """parse_primary 的 在范围 兼容入口不再硬编码 (空变量, 0, 0)"""
        _, expr = parse_expr("在范围 3..7")
        assert isinstance(expr, LogicConstraint)
        # 变量名虽无法从左侧取得，但边界必须被真实填充
        assert expr.bounds == (3, 7)


class TestAndNewlineContinuation:
    """行尾"并且"后的换行续写"""

    def test_newline_after_and_continues_right_operand(self):
        """真 并且\\n假 并且\\n真 解析为嵌套 BinaryOp"""
        _, expr = parse_expr("真 并且\n假 并且\n真")
        assert isinstance(expr, BinaryOp)
        assert expr.operator == "并且"

    def test_inequality_chain_across_lines(self):
        """数独/调度风格：?a != ?b 并且\\n?b != ?c"""
        _, expr = parse_expr("?a != ?b 并且\n?b != ?c")
        assert isinstance(expr, BinaryOp)
        assert expr.operator == "并且"

    def test_single_line_and_unchanged(self):
        """单行 并且 场景不受影响"""
        _, expr = parse_expr("真 并且 假")
        assert isinstance(expr, BinaryOp)
        assert expr.operator == "并且"


class TestLogicExamplesParse:
    """三个逻辑编程示例可完整解析"""

    def test_scheduling_example_parses(self):
        program = parse_file("examples/logic_programming/调度问题.道")
        assert program.statements

    def test_sudoku_example_parses(self):
        program = parse_file("examples/logic_programming/数独求解.道")
        assert program.statements

    def test_permissions_example_parses(self):
        program = parse_file("examples/logic_programming/权限系统.道")
        assert program.statements


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
