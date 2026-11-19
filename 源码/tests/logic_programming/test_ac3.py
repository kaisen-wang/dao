"""AC-3 弧一致性约束传播测试
============================

覆盖：
- 弧一致性与传递推理（A < B < C）
- AllDifferent 域传播
- 空域提前失败
- 非整数域兼容
- 一元约束（数值范围 / 类型）域缩减
- 回溯搜索与搜索空间对比
- 公共接口兼容性
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../"))

from dao.logic.constraints.ac3 import Domain, ac3
from dao.logic.constraints.core import (
    AllDifferentConstraint,
    ConstraintSolver,
    EqualityConstraint,
    InequalityConstraint,
    LessThanConstraint,
    NumericRangeConstraint,
    TypeConstraint,
)
from dao.logic.core import LogicAtom, LogicVariable, Substitution


class TestArcConsistency:
    """AC-3 弧一致性传播"""

    def test_transitive_less_than_narrows_domains(self):
        """A<B, B<C 通过弧一致性传递地缩小 A 的域（体现 A<C 推理）"""
        a, b, c = LogicVariable("?a"), LogicVariable("?b"), LogicVariable("?c")
        solver = ConstraintSolver([LessThanConstraint(a, b), LessThanConstraint(b, c)])
        for var in (a, b, c):
            solver.set_domain(var, range(1, 11))

        result = solver.propagate_domains()
        assert result is not None
        # A < B < C ⟹ A ≤ 8, 2 ≤ B ≤ 9, C ≥ 3
        assert max(result[a].values) == 8
        assert min(result[b].values) == 2 and max(result[b].values) == 9
        assert min(result[c].values) == 3
        # 链式不等式成立
        assert max(result[a].values) < max(result[b].values) < max(result[c].values)
        assert min(result[a].values) < min(result[b].values) < min(result[c].values)

        # 对照：仅有 A<B 时 A 的上界是 9；加入 B<C 后降到 8，
        # 证明传递约束确实传播到了 A（而非只做局部检查）
        solver2 = ConstraintSolver([LessThanConstraint(a, b)])
        solver2.set_domain(a, range(1, 11))
        solver2.set_domain(b, range(1, 11))
        result2 = solver2.propagate_domains()
        assert max(result2[a].values) == 9
        assert max(result[a].values) < max(result2[a].values)

    def test_all_different_prunes_domains(self):
        """AllDifferent 把单值变量的不确定性传播到其它变量"""
        x, y, z = LogicVariable("?x"), LogicVariable("?y"), LogicVariable("?z")
        solver = ConstraintSolver([AllDifferentConstraint([x, y, z])])
        solver.set_domain(x, [1, 2])
        solver.set_domain(y, [1])
        solver.set_domain(z, [1, 2, 3])

        result = solver.propagate_domains()
        assert result is not None
        assert result[x].values == frozenset({2})
        assert result[y].values == frozenset({1})
        # z 既不能等于 x=2，也不能等于 y=1
        assert result[z].values == frozenset({3})

    def test_equality_intersects_domains(self):
        """相等约束把两个变量的域裁剪为交集"""
        x, y = LogicVariable("?x"), LogicVariable("?y")
        solver = ConstraintSolver([EqualityConstraint(x, y)])
        solver.set_domain(x, [1, 2, 3, 4])
        solver.set_domain(y, [3, 4, 5])

        result = solver.propagate_domains()
        assert result[x].values == frozenset({3, 4})
        assert result[y].values == frozenset({3, 4})

    def test_unary_constraints_narrow_domain(self):
        """数值范围与类型约束对单变量域做过滤"""
        x = LogicVariable("?x")
        solver = ConstraintSolver(
            [NumericRangeConstraint(x, 1, 5), TypeConstraint(x, int)]
        )
        solver.set_domain(x, [0, 1, 3, 5, 6, "abc", True])

        result = solver.propagate_domains()
        assert result[x].values == frozenset({1, 3, 5})


class TestDomainFailureAndCompatibility:
    """空域失败、非整数域与接口兼容"""

    def test_empty_domain_early_failure(self):
        """域被裁为空时 AC-3 提前返回失败，回溯也剪掉整棵子树"""
        x, y = LogicVariable("?x"), LogicVariable("?y")
        solver = ConstraintSolver([EqualityConstraint(x, y)])
        solver.set_domain(x, [1, 2])
        solver.set_domain(y, [3, 4])

        counter = [0]
        assert solver.propagate_domains(counter=counter) is None
        assert counter[0] >= 1

        assert solver.solve_constraints(Substitution()) == []
        assert solver.last_search_stats["backtracks"] >= 1

    def test_non_integer_domains(self):
        """字符串与浮点等非整数域正常工作"""
        x, y = LogicVariable("?x"), LogicVariable("?y")
        solver = ConstraintSolver([InequalityConstraint(x, y)])
        solver.set_domain(x, ["红", "绿", "蓝"])
        solver.set_domain(y, ["红"])

        result = solver.propagate_domains()
        assert result[x].values == frozenset({"绿", "蓝"})
        assert result[y].values == frozenset({"红"})

        z = LogicVariable("?z")
        solver2 = ConstraintSolver([NumericRangeConstraint(z, 1.5, 3.5)])
        solver2.set_domain(z, [1, 2, 2.5, 3, 4, "x"])
        result2 = solver2.propagate_domains()
        assert result2[z].values == frozenset({2, 2.5, 3})

    def test_public_interface_compatibility(self):
        """未设置域时 check/propagate/solve 保持原有行为"""
        x = LogicVariable("?x")
        solver = ConstraintSolver([NumericRangeConstraint(x, 1, 10)])
        subst = Substitution()
        subst.bind(x, LogicAtom(5))

        assert solver.check_constraints(subst) is True
        assert solver.propagate_constraints(subst) is subst
        assert solver.solve_constraints(subst) == [subst]

    def test_ac3_does_not_mutate_input_domains(self):
        """ac3 返回新字典，不修改调用方传入的域"""
        x = LogicVariable("?x")
        original = {x: Domain([1, 2, 3])}
        result = ac3([NumericRangeConstraint(x, 1, 2)], original)
        assert result is not None
        assert result[x].values == frozenset({1, 2})
        assert original[x].values == frozenset({1, 2, 3})


class TestBacktrackingSearch:
    """AC-3 引导的回溯搜索"""

    @staticmethod
    def _chain_constraints(a, b, c, d):
        return [
            LessThanConstraint(a, b),
            LessThanConstraint(b, c),
            LessThanConstraint(c, d),
            AllDifferentConstraint([a, b, c, d]),
        ]

    def test_backtracking_enumerates_all_solutions(self):
        """从 1..6 中选 4 个严格递增值，应有 C(6,4)=15 个解"""
        a, b, c, d = (LogicVariable(n) for n in ("?a", "?b", "?c", "?d"))
        solver = ConstraintSolver(self._chain_constraints(a, b, c, d))
        for var in (a, b, c, d):
            solver.set_domain(var, range(1, 7))

        solutions = solver.solve_constraints(Substitution())
        assert len(solutions) == 15
        for solution in solutions:
            values = [solution.get_value(v).value for v in (a, b, c, d)]
            assert values == sorted(values)
            assert len(set(values)) == 4
        assert solver.last_search_stats["assignments"] > 0

    def test_ac3_reduces_search_space(self):
        """对比：AC-3 剪枝后的赋值次数显著少于朴素回溯"""
        a, b, c, d = (LogicVariable(n) for n in ("?a", "?b", "?c", "?d"))
        constraints = self._chain_constraints(a, b, c, d)

        solver = ConstraintSolver(constraints)
        for var in (a, b, c, d):
            solver.set_domain(var, range(1, 7))
        solutions = solver.solve_constraints(Substitution())
        assert len(solutions) == 15
        ac3_assignments = solver.last_search_stats["assignments"]

        # 朴素回溯：逐变量枚举所有赋值，最后统一检查，不使用域缩减
        naive_assignments = [0]
        naive_solutions = [0]
        current = Substitution()
        variables = [a, b, c, d]

        def naive_dfs(index):
            if index == len(variables):
                if all(constraint.is_satisfied(current) for constraint in constraints):
                    naive_solutions[0] += 1
                return
            mark = current.mark()
            for value in range(1, 7):
                naive_assignments[0] += 1
                current.bind(variables[index], LogicAtom(value))
                naive_dfs(index + 1)
                current.backtrack(mark)

        naive_dfs(0)

        # 两条路径解的数量一致，对比才公平
        assert naive_solutions[0] == 15
        # 朴素搜索累计赋值次数：6 + 6^2 + 6^3 + 6^4 = 1554
        assert naive_assignments[0] == sum(6 ** i for i in range(1, 5))
        assert ac3_assignments < naive_assignments[0] // 3, (
            f"AC-3 赋值次数 {ac3_assignments} 未显著低于朴素回溯 "
            f"{naive_assignments[0]}"
        )


if __name__ == "__main__":
    import pytest

    pytest.main([__file__, "-v"])
