"""约束解析修复测试
====================

验证 ``?x 在范围 a..b`` 约束语法被正确解析为 ``LogicConstraint``，
其 ``variable`` / ``bounds`` 字段被真实填充（而非硬编码为空），
并验证解析出的约束能驱动约束求解器得到正确结果。
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest

from dao.ast_nodes import Identifier, LogicConstraint
from dao.environment import Environment
from dao.interpreter.core import Interpreter
from dao.lexer import Lexer
from dao.logic.constraints.core import NumericRangeConstraint
from dao.logic.core import KnowledgeBase, LogicAtom, LogicStruct, LogicVariable
from dao.logic.solver import Solver
from dao.parser import Parser


def parse(source: str):
    return Parser(Lexer(source).tokenize()).parse()


def first_constraint(source: str) -> LogicConstraint:
    """解析一个逻辑块，返回其首条规则体中的第一条约束"""
    program = parse(source)
    rules = program.statements[0].rules
    constraint = rules[0].body[0]
    assert isinstance(constraint, LogicConstraint)
    return constraint


def rule_source(body: str) -> str:
    return (
        "逻辑 测试\n"
        "    规则: 检查(?x) 如果\n"
        f"        {body}\n"
    )


class TestConstraintParsing:
    """测试约束语法解析为 LogicConstraint"""

    def test_integer_range(self):
        """整数区间：变量名与上下界被正确填充"""
        constraint = first_constraint(rule_source("?x 在范围 1..10"))
        assert constraint.variable == "?x"
        assert constraint.operator == "在范围"
        assert constraint.bounds == (1, 10)

    def test_variable_reference(self):
        """变量引用：传入的变量名被透传到 variable 字段"""
        tokens = Lexer("在范围 3..7").tokenize()
        parser = Parser(tokens)

        # 直接传入已解析的变量节点
        by_node = parser.parse_logic_constraint(Identifier(name="?y"))
        assert by_node.variable == "?y"
        assert by_node.bounds == (3, 7)

        # 直接传入变量名字符串
        tokens2 = Lexer("在范围 3..7").tokenize()
        by_name = Parser(tokens2).parse_logic_constraint("?年龄")
        assert by_name.variable == "?年龄"
        assert by_name.bounds == (3, 7)

        # 规则体中的变量引用同样保留真实变量名
        constraint = first_constraint(rule_source("?成绩 在范围 0..100"))
        assert constraint.variable == "?成绩"
        assert constraint.bounds == (0, 100)

    def test_boundary_values(self):
        """边界值：负数下界、零宽区间、负数上界均被正确解析"""
        negative = first_constraint(rule_source("?n 在范围 -5..5"))
        assert negative.variable == "?n"
        assert negative.bounds == (-5, 5)

        zero_width = first_constraint(rule_source("?z 在范围 0..0"))
        assert zero_width.bounds == (0, 0)

        negative_high = first_constraint(rule_source("?t 在范围 -10..-1"))
        assert negative_high.bounds == (-10, -1)

    def test_multiple_constraints_in_rule_body(self):
        """同一规则体中的多个约束互不干扰"""
        program = parse(
            "逻辑 测试\n"
            "    规则: 检查(?x, ?y) 如果\n"
            "        ?x 在范围 1..10 并且\n"
            "        ?y 在范围 20..30\n"
        )
        body = program.statements[0].rules[0].body
        assert len(body) == 2
        assert all(isinstance(c, LogicConstraint) for c in body)
        assert body[0].variable == "?x"
        assert body[0].bounds == (1, 10)
        assert body[1].variable == "?y"
        assert body[1].bounds == (20, 30)

    def test_invalid_bound_reports_chinese_error(self):
        """非整数边界应抛出中文语法错误"""
        tokens = Lexer("在范围 甲..10").tokenize()
        parser = Parser(tokens)
        with pytest.raises(Exception, match="约束下界必须是整数"):
            parser.parse_logic_constraint(Identifier(name="?x"))


class TestLogicBlockMultipleRules:
    """逻辑块含多条规则时不应被规则体层级的回退提前截断"""

    def test_two_rules_with_constraint_bodies(self):
        source = (
            "逻辑 测试\n"
            "    规则: 甲(?x) 如果\n"
            "        ?x 在范围 1..10\n"
            "\n"
            "    规则: 乙(?y) 如果\n"
            "        ?y 在范围 20..30\n"
        )
        program = parse(source)
        block = program.statements[0]
        assert len(block.rules) == 2

        first = block.rules[0].body[0]
        second = block.rules[1].body[0]
        assert isinstance(first, LogicConstraint)
        assert isinstance(second, LogicConstraint)
        assert (first.variable, first.bounds) == ("?x", (1, 10))
        assert (second.variable, second.bounds) == ("?y", (20, 30))

    def test_sudoku_example_keeps_both_rules(self):
        """数独求解示例的第一个逻辑块应含两条规则"""
        example = os.path.join(
            os.path.dirname(__file__),
            "..",
            "..",
            "examples",
            "logic_programming",
            "数独求解.道",
        )
        with open(example, encoding="utf-8") as f:
            program = parse(f.read())
        block = program.statements[0]
        assert hasattr(block, "rules")
        assert len(block.rules) == 2


class TestConstraintSolvingEndToEnd:
    """端到端验证：解析出的约束驱动求解器得到正确结果"""

    @staticmethod
    def build_solver(constraint: LogicConstraint) -> Solver:
        kb = KnowledgeBase("测试知识库")
        for value in (5, 15, 8, 0, 10):
            kb.add_fact(LogicStruct("数字", (LogicAtom(value),)))

        result = Interpreter().eval_logic_constraint(constraint, Environment())
        assert result[0] == "约束"
        runtime_constraint = result[1]
        assert isinstance(runtime_constraint, NumericRangeConstraint)
        return Solver(kb, [runtime_constraint])

    def test_range_filters_query_results(self):
        """解析出的 1..10 约束过滤掉范围外的事实"""
        constraint = first_constraint(rule_source("?x 在范围 1..10"))
        solver = self.build_solver(constraint)
        results = solver.solve(LogicStruct("数字", (LogicVariable("?x"),)))

        values = [r.to_dict()["?x"] for r in results]
        assert 5 in values
        assert 8 in values
        assert 15 not in values
        assert 0 not in values

    def test_boundary_values_are_inclusive(self):
        """边界值本身应满足约束（闭区间）"""
        constraint = first_constraint(rule_source("?x 在范围 0..10"))
        solver = self.build_solver(constraint)
        results = solver.solve(LogicStruct("数字", (LogicVariable("?x"),)))

        values = [r.to_dict()["?x"] for r in results]
        assert 0 in values
        assert 10 in values
        assert 15 not in values


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
