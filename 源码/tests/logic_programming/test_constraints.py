"""
约束求解功能测试
==================

测试约束求解器的功能，包括：
- 数值范围约束
- 相等约束
- 不等约束
- 类型约束
- 约束传播
- 约束与逻辑编程的集成

这些测试验证约束求解器与逻辑编程引擎的正确交互。
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../"))

import pytest
from dao.logic.constraints.core import (
    Constraint,
    ConstraintSolver,
    ConstraintType,
    ConstraintViolationError,
    EqualityConstraint,
    InequalityConstraint,
    NumericRangeConstraint,
    TypeConstraint,
    apply_constraints,
    get_constraints,
    is_constrained,
)
from dao.logic.core import (
    KnowledgeBase,
    LogicAtom,
    LogicStruct,
    LogicVariable,
    Substitution,
)
from dao.logic.solver import Solver


class TestNumericRangeConstraint:
    """测试数值范围约束"""

    def test_range_constraint_satisfied(self):
        """测试范围约束满足"""
        x = LogicVariable("?x")
        constraint = NumericRangeConstraint(x, 1, 10)
        subst = Substitution()
        subst.bind(x, LogicAtom(5))
        assert constraint.is_satisfied(subst) is True

    def test_range_constraint_violated(self):
        """测试范围约束违反"""
        x = LogicVariable("?x")
        constraint = NumericRangeConstraint(x, 1, 10)
        subst = Substitution()
        subst.bind(x, LogicAtom(15))
        assert constraint.is_satisfied(subst) is False

    def test_range_constraint_unbound_variable(self):
        """测试未绑定变量的范围约束"""
        x = LogicVariable("?x")
        constraint = NumericRangeConstraint(x, 1, 10)
        subst = Substitution()
        assert constraint.is_satisfied(subst) is True

    def test_range_constraint_with_non_numeric_value(self):
        """测试非数值值的范围约束"""
        x = LogicVariable("?x")
        constraint = NumericRangeConstraint(x, 1, 10)
        subst = Substitution()
        subst.bind(x, LogicAtom("abc"))
        assert constraint.is_satisfied(subst) is False


class TestEqualityConstraint:
    """测试相等约束"""

    def test_equality_constraint_satisfied(self):
        """测试相等约束满足"""
        x = LogicVariable("?x")
        y = LogicVariable("?y")
        constraint = EqualityConstraint(x, y)
        subst = Substitution()
        subst.bind(x, LogicAtom(5))
        subst.bind(y, LogicAtom(5))
        assert constraint.is_satisfied(subst) is True

    def test_equality_constraint_violated(self):
        """测试相等约束违反"""
        x = LogicVariable("?x")
        y = LogicVariable("?y")
        constraint = EqualityConstraint(x, y)
        subst = Substitution()
        subst.bind(x, LogicAtom(5))
        subst.bind(y, LogicAtom(6))
        assert constraint.is_satisfied(subst) is False

    def test_equality_constraint_partially_bound(self):
        """测试部分绑定变量的相等约束"""
        x = LogicVariable("?x")
        y = LogicVariable("?y")
        constraint = EqualityConstraint(x, y)
        subst = Substitution()
        subst.bind(x, LogicAtom(5))
        assert constraint.is_satisfied(subst) is True


class TestInequalityConstraint:
    """测试不等约束"""

    def test_inequality_constraint_satisfied(self):
        """测试不等约束满足"""
        x = LogicVariable("?x")
        y = LogicVariable("?y")
        constraint = InequalityConstraint(x, y)
        subst = Substitution()
        subst.bind(x, LogicAtom(5))
        subst.bind(y, LogicAtom(6))
        assert constraint.is_satisfied(subst) is True

    def test_inequality_constraint_violated(self):
        """测试不等约束违反"""
        x = LogicVariable("?x")
        y = LogicVariable("?y")
        constraint = InequalityConstraint(x, y)
        subst = Substitution()
        subst.bind(x, LogicAtom(5))
        subst.bind(y, LogicAtom(5))
        assert constraint.is_satisfied(subst) is False


class TestTypeConstraint:
    """测试类型约束"""

    def test_type_constraint_satisfied(self):
        """测试类型约束满足"""
        x = LogicVariable("?x")
        constraint = TypeConstraint(x, int)
        subst = Substitution()
        subst.bind(x, LogicAtom(5))
        assert constraint.is_satisfied(subst) is True

    def test_type_constraint_violated(self):
        """测试类型约束违反"""
        x = LogicVariable("?x")
        constraint = TypeConstraint(x, int)
        subst = Substitution()
        subst.bind(x, LogicAtom("abc"))
        assert constraint.is_satisfied(subst) is False


class TestConstraintSolver:
    """测试约束求解器"""

    def test_solver_with_single_constraint(self):
        """测试单个约束的求解器"""
        x = LogicVariable("?x")
        constraint = NumericRangeConstraint(x, 1, 10)
        solver = ConstraintSolver([constraint])

        # 创建满足约束的替换
        subst = Substitution()
        subst.bind(x, LogicAtom(5))
        assert solver.check_constraints(subst) is True

    def test_solver_with_multiple_constraints(self):
        """测试多个约束的求解器"""
        x = LogicVariable("?x")
        y = LogicVariable("?y")
        constraints = [
            NumericRangeConstraint(x, 1, 10),
            NumericRangeConstraint(y, 5, 15),
            EqualityConstraint(x, y),
        ]
        solver = ConstraintSolver(constraints)

        # 创建满足所有约束的替换
        subst = Substitution()
        subst.bind(x, LogicAtom(5))
        subst.bind(y, LogicAtom(5))
        assert solver.check_constraints(subst) is True

    def test_solver_with_violating_constraints(self):
        """测试包含违反约束的求解器"""
        x = LogicVariable("?x")
        constraints = [NumericRangeConstraint(x, 1, 10), TypeConstraint(x, int)]
        solver = ConstraintSolver(constraints)

        # 创建违反约束的替换
        subst = Substitution()
        subst.bind(x, LogicAtom("abc"))
        assert solver.check_constraints(subst) is False

    def test_solver_clear_constraints(self):
        """测试清除约束"""
        x = LogicVariable("?x")
        constraint = NumericRangeConstraint(x, 1, 10)
        solver = ConstraintSolver([constraint])
        assert solver.has_constraints() is True

        solver.clear_constraints()
        assert solver.has_constraints() is False


class TestConstraintIntegration:
    """测试约束与逻辑编程的集成"""

    def test_query_with_range_constraint(self):
        """测试带范围约束的查询"""
        # 创建知识库
        kb = KnowledgeBase("测试知识库")
        kb.add_fact(LogicStruct("数字", (LogicAtom(5),)))
        kb.add_fact(LogicStruct("数字", (LogicAtom(15),)))
        kb.add_fact(LogicStruct("数字", (LogicAtom(8),)))

        # 创建约束
        x = LogicVariable("?x")
        constraints = [NumericRangeConstraint(x, 1, 10)]

        # 创建求解器并查询
        solver = Solver(kb, constraints)
        goal = LogicStruct("数字", (x,))
        results = solver.solve(goal)

        # 检查结果（只应该返回5和8）
        values = [list(result.to_dict().values())[0] for result in results]
        assert 5 in values
        assert 8 in values
        assert 15 not in values

    def test_query_with_equality_constraint(self):
        """测试带相等约束的查询"""
        # 创建知识库
        kb = KnowledgeBase("测试知识库")
        kb.add_fact(LogicStruct("配对", (LogicAtom(1), LogicAtom(1))))
        kb.add_fact(LogicStruct("配对", (LogicAtom(2), LogicAtom(3))))
        kb.add_fact(LogicStruct("配对", (LogicAtom(3), LogicAtom(3))))

        # 创建约束
        x = LogicVariable("?x")
        y = LogicVariable("?y")
        constraints = [EqualityConstraint(x, y)]

        # 创建求解器并查询
        solver = Solver(kb, constraints)
        goal = LogicStruct("配对", (x, y))
        results = solver.solve(goal)

        # 检查结果（只应该返回(1,1)和(3,3)）
        pairs = [tuple(result.to_dict().values()) for result in results]
        assert (1, 1) in pairs
        assert (3, 3) in pairs
        assert (2, 3) not in pairs

    def test_query_with_multiple_constraints(self):
        """测试多个约束的查询"""
        # 创建知识库
        kb = KnowledgeBase("测试知识库")
        kb.add_fact(LogicStruct("产品", (LogicAtom("苹果"), LogicAtom(5))))
        kb.add_fact(LogicStruct("产品", (LogicAtom("香蕉"), LogicAtom(3))))
        kb.add_fact(LogicStruct("产品", (LogicAtom("橙子"), LogicAtom(7))))
        kb.add_fact(LogicStruct("产品", (LogicAtom("西瓜"), LogicAtom(15))))

        # 创建约束
        name = LogicVariable("?name")
        price = LogicVariable("?price")
        constraints = [NumericRangeConstraint(price, 4, 10), TypeConstraint(price, int)]

        # 创建求解器并查询
        solver = Solver(kb, constraints)
        goal = LogicStruct("产品", (name, price))
        results = solver.solve(goal)

        # 检查结果（只应该返回苹果和橙子）
        products = [result.to_dict()["?name"] for result in results]
        assert "苹果" in products
        assert "橙子" in products
        assert "香蕉" not in products
        assert "西瓜" not in products


class TestConstraintUtils:
    """测试约束工具函数"""

    def test_is_constrained_function(self):
        """测试is_constrained函数"""
        x = LogicVariable("?x")
        y = LogicVariable("?y")
        constraints = [NumericRangeConstraint(x, 1, 10), EqualityConstraint(x, y)]

        assert is_constrained(x, constraints) is True
        assert is_constrained(y, constraints) is True

        z = LogicVariable("?z")
        assert is_constrained(z, constraints) is False

    def test_get_constraints_function(self):
        """测试get_constraints函数"""
        x = LogicVariable("?x")
        y = LogicVariable("?y")
        z = LogicVariable("?z")
        constraints = [
            NumericRangeConstraint(x, 1, 10),
            EqualityConstraint(x, y),
            TypeConstraint(z, int),
        ]

        x_constraints = get_constraints([x], constraints)
        assert len(x_constraints) == 2
        assert any(isinstance(c, NumericRangeConstraint) for c in x_constraints)
        assert any(isinstance(c, EqualityConstraint) for c in x_constraints)

        z_constraints = get_constraints([z], constraints)
        assert len(z_constraints) == 1
        assert isinstance(z_constraints[0], TypeConstraint)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
