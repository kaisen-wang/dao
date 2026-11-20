"""多条件规则查询绑定测试

回归：规则体用「并且」连接多个条件时，查询必须返回包含全部查询变量
绑定的字典，而不是缺失键的空字典。

根因：parse_logic_rule_body_expr 原先调用 parse_pipe，其内部的 parse_and
会把所有「并且」相连的条件合并成一个 BinaryOp；规则体因此只剩单个节点，
解释器 exec_logic_block 只识别 FunctionCall/LogicFact，将该节点忽略，
最终规则体为空，查询只能得到空替换。
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../"))

from dao.ast_nodes import FunctionCall, LogicFact
from dao.interpreter.core import Interpreter
from dao.lexer import Lexer
from dao.logic.backtracking import Backtracker
from dao.logic.core import (
    KnowledgeBase,
    LogicAtom,
    LogicStruct,
    LogicVariable,
    normalize_term,
)
from dao.logic.solver import Solver
from dao.parser import Parser


def run_source(source: str):
    """解析并执行源码，返回解释器实例。"""
    interpreter = Interpreter()
    program = Parser(Lexer(source, "<test>").tokenize(), source).parse()
    interpreter.execute(program, source=source)
    return interpreter


def parse_block(source: str):
    program = Parser(Lexer(source, "<test>").tokenize(), source).parse()
    return program.statements[0]


class TestMultiConditionRuleParsing:
    """解析器必须把「并且」连接的条件拆成多个规则体节点"""

    def test_two_conditions_become_two_body_nodes(self):
        block = parse_block(
            "逻辑 家\n"
            "    事实: 父母(\"甲\", \"乙\")\n"
            "    事实: 父母(\"乙\", \"丙\")\n"
            "    规则: 祖孙(?祖, ?孙) 如果 "
            "父母(?祖, ?中) 并且 父母(?中, ?孙)\n"
        )
        assert len(block.rules) == 1
        body = block.rules[0].body
        assert len(body) == 2
        assert all(isinstance(node, (FunctionCall, LogicFact)) for node in body)

    def test_three_conditions_become_three_body_nodes(self):
        block = parse_block(
            "逻辑 家\n"
            "    规则: 曾祖孙(?曾祖, ?曾孙) 如果 "
            "父母(?曾祖, ?父) 并且 父母(?父, ?子) 并且 父母(?子, ?曾孙)\n"
        )
        body = block.rules[0].body
        assert len(body) == 3


class TestMultiConditionQueries:
    """端到端：多条件规则查询返回完整变量绑定"""

    def test_two_condition_chain(self):
        """用例①：祖孙二条件链，?祖=甲、?孙=丙"""
        interpreter = run_source(
            "逻辑 家\n"
            "    事实: 父母(\"甲\", \"乙\")\n"
            "    事实: 父母(\"乙\", \"丙\")\n"
            "    规则: 祖孙(?祖, ?孙) 如果 "
            "父母(?祖, ?中) 并且 父母(?中, ?孙)\n"
            "定义 r = 查询(家, 祖孙(?祖, ?孙))\n"
        )
        results = interpreter.global_env.get("r")
        assert len(results) == 1
        assert results[0]["?祖"] == "甲"
        assert results[0]["?中"] == "乙"
        assert results[0]["?孙"] == "丙"

    def test_three_condition_chain(self):
        """用例②：曾祖孙三条件链，?曾祖=甲、?曾孙=丁"""
        interpreter = run_source(
            "逻辑 家\n"
            '    事实: 父母("甲", "乙")\n'
            '    事实: 父母("乙", "丙")\n'
            '    事实: 父母("丙", "丁")\n'
            "    规则: 曾祖孙(?曾祖, ?曾孙) 如果 "
            "父母(?曾祖, ?父) 并且 父母(?父, ?子) 并且 父母(?子, ?曾孙)\n"
            "定义 r = 查询(家, 曾祖孙(?曾祖, ?曾孙))\n"
        )
        results = interpreter.global_env.get("r")
        assert len(results) == 1
        assert results[0]["?曾祖"] == "甲"
        assert results[0]["?曾孙"] == "丁"
        assert results[0]["?父"] == "乙"
        assert results[0]["?子"] == "丙"

    def test_partially_bound_query(self):
        """用例③①：查询只绑定 ?孙（首参为常量）时结果正确"""
        interpreter = run_source(
            "逻辑 家\n"
            '    事实: 父母("甲", "乙")\n'
            '    事实: 父母("乙", "丙")\n'
            "    规则: 祖孙(?祖, ?孙) 如果 "
            "父母(?祖, ?中) 并且 父母(?中, ?孙)\n"
            '定义 r = 查询(家, 祖孙("甲", ?孙))\n'
        )
        results = interpreter.global_env.get("r")
        assert len(results) == 1
        assert results[0]["?孙"] == "丙"

    def test_query_variable_names_differ_from_rule_head(self):
        """用例③②：查询变量名与规则头不同时，链式绑定需递归解引用"""
        interpreter = run_source(
            "逻辑 家\n"
            '    事实: 父母("甲", "乙")\n'
            '    事实: 父母("乙", "丙")\n'
            "    规则: 祖孙(?祖, ?孙) 如果 "
            "父母(?祖, ?中) 并且 父母(?中, ?孙)\n"
            "定义 r = 查询(家, 祖孙(?谁, ?后代))\n"
        )
        results = interpreter.global_env.get("r")
        assert len(results) == 1
        assert results[0]["?谁"] == "甲"
        assert results[0]["?后代"] == "丙"


class TestRegressions:
    """用例④：单条件规则、否定、剪枝回归"""

    def test_single_condition_rule(self):
        interpreter = run_source(
            "逻辑 家\n"
            '    事实: 父母("甲", "乙")\n'
            '    事实: 父母("乙", "丙")\n'
            '    规则: 孩子(?父) 如果 父母(?父, "乙")\n'
            "定义 r = 查询(家, 孩子(?父))\n"
        )
        results = interpreter.global_env.get("r")
        assert len(results) == 1
        assert results[0]["?父"] == "甲"

    def test_negation_solver(self):
        kb = KnowledgeBase("权限")
        kb.add_fact(LogicStruct("已封禁", (LogicAtom("王五"),)))
        solver = Solver(kb)
        assert solver.solve_negation(LogicStruct("已封禁", (LogicAtom("王五"),))) is False
        assert solver.solve_negation(LogicStruct("已封禁", (LogicAtom("张三"),))) is True

    def test_cut_in_solve_body(self):
        kb = KnowledgeBase("测试")
        kb.add_fact(LogicStruct("a", (LogicAtom(1),)))
        kb.add_fact(LogicStruct("a", (LogicAtom(2),)))
        backtracker = Backtracker(kb)
        goal = normalize_term(LogicStruct("a", (LogicVariable("?x"),)))
        results = list(backtracker._solve_body(["剪枝"], goal))
        assert len(results) == 1


if __name__ == "__main__":
    import pytest

    pytest.main([__file__, "-v"])
