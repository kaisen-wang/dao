"""逻辑编程新特性测试：否定、剪枝、约束、动态事实"""

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from dao.lexer import Lexer
from dao.parser import Parser
from dao.interpreter.core import Interpreter
from dao.tokens import TokenType, KEYWORDS
from dao.logic.core import KnowledgeBase, LogicStruct, LogicAtom, LogicVariable, normalize_term
from dao.logic.solver import Solver
from dao.logic.backtracking import Backtracker, CutSignal
from dao.logic.constraints.core import (
    NumericRangeConstraint,
    AllDifferentConstraint,
    ConstraintSolver,
)


def parse(source: str):
    tokens = Lexer(source).tokenize()
    return Parser(tokens).parse()


def interpret(source: str):
    interpreter = Interpreter()
    return interpreter.execute(source)


class TestNegationToken:
    """测试否定关键字Token"""

    def test_非_token_type_exists(self):
        assert TokenType.非 is not None

    def test_非_keyword_registered(self):
        assert "非" in KEYWORDS
        assert KEYWORDS["非"] == TokenType.非

    def test_在范围_token_type_exists(self):
        assert TokenType.在范围 is not None

    def test_在范围_keyword_registered(self):
        assert "在范围" in KEYWORDS
        assert KEYWORDS["在范围"] == TokenType.在范围

    def test_区间_token_type_exists(self):
        assert TokenType.区间 is not None


class TestNegationLexer:
    """测试否定关键字词法分析"""

    def test_非_lexer(self):
        tokens = Lexer("非").tokenize()
        assert tokens[0].type == TokenType.非

    def test_在范围_lexer(self):
        tokens = Lexer("在范围").tokenize()
        assert tokens[0].type == TokenType.在范围

    def test_区间_lexer(self):
        tokens = Lexer("1..10").tokenize()
        types = [t.type for t in tokens if t.type != TokenType.文件结束]
        assert TokenType.数值 in types
        assert TokenType.区间 in types


class TestNegationParser:
    """测试否定关键字语法分析"""

    def test_parse_negation_in_query(self):
        source = '查询(kb, 非 已封禁(?用户))\n'
        ast = parse(source)
        assert len(ast.statements) == 1

    def test_parse_cut(self):
        source = '剪枝\n'
        ast = parse(source)
        assert len(ast.statements) == 1


class TestNegationSolver:
    """测试否定求解"""

    def test_solve_negation_true(self):
        kb = KnowledgeBase("test")
        kb.add_fact(LogicStruct("已封禁", (LogicAtom("王五"),)))
        solver = Solver(kb)
        result = solver.solve_negation(LogicStruct("已封禁", (LogicAtom("王五"),)))
        assert result is False

    def test_solve_negation_false(self):
        kb = KnowledgeBase("test")
        kb.add_fact(LogicStruct("已封禁", (LogicAtom("王五"),)))
        solver = Solver(kb)
        result = solver.solve_negation(LogicStruct("已封禁", (LogicAtom("张三"),)))
        assert result is True

    def test_negation_in_rule(self):
        kb = KnowledgeBase("权限")
        kb.add_fact(LogicStruct("角色", (LogicAtom("张三"), LogicAtom("管理员"))))
        kb.add_fact(LogicStruct("角色", (LogicAtom("李四"), LogicAtom("普通用户"))))
        kb.add_fact(LogicStruct("已封禁", (LogicAtom("王五"),)))

        solver = Solver(kb)
        assert solver.solve_negation(LogicStruct("已封禁", (LogicAtom("张三"),))) is True
        assert solver.solve_negation(LogicStruct("已封禁", (LogicAtom("王五"),))) is False


class TestCutBacktracker:
    """测试剪枝机制"""

    def test_cut_signal(self):
        signal = CutSignal()
        assert isinstance(signal, Exception)

    def test_backtracker_cut_activation(self):
        kb = KnowledgeBase("test")
        kb.add_fact(LogicStruct("a", (LogicAtom(1),)))
        kb.add_fact(LogicStruct("a", (LogicAtom(2),)))
        backtracker = Backtracker(kb)
        backtracker.activate_cut()
        assert backtracker._cut_active is True

    def test_backtracker_cut_reset(self):
        kb = KnowledgeBase("test")
        backtracker = Backtracker(kb)
        backtracker.activate_cut()
        backtracker.reset_cut()
        assert backtracker._cut_active is False

    def test_cut_in_solve_body(self):
        kb = KnowledgeBase("test")
        kb.add_fact(LogicStruct("a", (LogicAtom(1),)))
        kb.add_fact(LogicStruct("a", (LogicAtom(2),)))
        backtracker = Backtracker(kb)

        results = list(backtracker._solve_body(["剪枝"], normalize_term(LogicStruct("a", (LogicVariable("?x"),)))))
        assert len(results) == 1


class TestConstraintIntegration:
    """测试约束集成"""

    def test_numeric_range_constraint(self):
        var = LogicVariable("?x")
        constraint = NumericRangeConstraint(var, 1, 10)
        from dao.logic.core import Substitution

        subst = Substitution()
        subst.bind(var, LogicAtom(5))
        assert constraint.is_satisfied(subst) is True

        subst2 = Substitution()
        subst2.bind(var, LogicAtom(15))
        assert constraint.is_satisfied(subst2) is False

    def test_all_different_constraint(self):
        var1 = LogicVariable("?x")
        var2 = LogicVariable("?y")
        constraint = AllDifferentConstraint([var1, var2])
        from dao.logic.core import Substitution

        subst = Substitution()
        subst.bind(var1, LogicAtom(1))
        subst.bind(var2, LogicAtom(2))
        assert constraint.is_satisfied(subst) is True

        subst2 = Substitution()
        subst2.bind(var1, LogicAtom(1))
        subst2.bind(var2, LogicAtom(1))
        assert constraint.is_satisfied(subst2) is False

    def test_in_range_helper(self):
        from dao.logic.constraints import in_range

        constraint = in_range("?x", 1, 10)
        assert isinstance(constraint, NumericRangeConstraint)
        assert constraint.min_value == 1
        assert constraint.max_value == 10

    def test_all_different_helper(self):
        from dao.logic.constraints import all_different

        constraint = all_different(["?x", "?y"])
        assert isinstance(constraint, AllDifferentConstraint)


class TestDynamicFacts:
    """测试动态事实"""

    def test_add_fact_builtin(self):
        kb = KnowledgeBase("test")
        kb.add_fact(LogicStruct("用户", (LogicAtom("张三"), LogicAtom("管理员"))))
        assert len(kb.get_facts("用户")) == 1

        new_fact = LogicStruct("用户", (LogicAtom("王五"), LogicAtom("读者")))
        kb.add_fact(new_fact)
        assert len(kb.get_facts("用户")) == 2

    def test_remove_fact_builtin(self):
        kb = KnowledgeBase("test")
        kb.add_fact(LogicStruct("用户", (LogicAtom("张三"), LogicAtom("管理员"))))
        kb.add_fact(LogicStruct("用户", (LogicAtom("李四"), LogicAtom("编辑"))))

        assert len(kb.get_facts("用户")) == 2
        kb.remove_fact(LogicStruct("用户", (LogicAtom("李四"), LogicAtom("编辑"))))
        assert len(kb.get_facts("用户")) == 1

    def test_dynamic_facts_with_solver(self):
        kb = KnowledgeBase("test")
        kb.add_fact(LogicStruct("角色", (LogicAtom("张三"), LogicAtom("管理员"))))
        solver = Solver(kb)

        result = solver.solve(LogicStruct("角色", (LogicVariable("?x"), LogicVariable("?r"))))
        assert len(result) == 1

        kb.add_fact(LogicStruct("角色", (LogicAtom("李四"), LogicAtom("编辑"))))
        solver2 = Solver(kb)
        result2 = solver2.solve(LogicStruct("角色", (LogicVariable("?x"), LogicVariable("?r"))))
        assert len(result2) == 2


class TestLogicBlockInterpreter:
    """测试逻辑块解释器集成"""

    def _run(self, source: str):
        tokens = Lexer(source).tokenize()
        ast = Parser(tokens).parse()
        interpreter = Interpreter()
        result = interpreter.execute(ast, source=source)
        return interpreter, result

    def test_logic_block_with_facts_and_rules(self):
        source = '''逻辑 家庭关系
    事实: 父母("张三", "小明")
    事实: 父母("李四", "小明")
    规则: 双亲(?孩子) 如果 父母("张三", ?孩子) 并且 父母("李四", ?孩子)
'''
        interp, _ = self._run(source)
        kb = interp.global_env.get("家庭关系")
        assert isinstance(kb, KnowledgeBase)
        assert len(kb.get_facts("父母")) == 2
        assert len(kb.get_rules("双亲")) == 1

    def test_logic_query_execution(self):
        source = '''逻辑 测试库
    事实: 颜色("红")
    事实: 颜色("蓝")

定义 结果 = 查询(测试库, 颜色(?c))
打印(结果)
'''
        interp, result = self._run(source)
        result_val = interp.global_env.get("结果")
        assert result_val is not None
        assert isinstance(result_val, list)
        assert len(result_val) >= 1