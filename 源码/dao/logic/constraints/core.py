"""
约束求解核心模块
================

定义约束类、约束求解器和相关算法。
"""

from enum import Enum
from typing import Any

from ..core import LogicAtom, LogicVariable, Substitution
from ..exceptions import QueryError
from .ac3 import Domain, ac3


class ConstraintType(Enum):
    """约束类型枚举"""

    NUMERIC_RANGE = "numeric_range"
    EQUALITY = "equality"
    INEQUALITY = "inequality"
    TYPE = "type"
    LOGICAL = "logical"
    LESS_THAN = "less_than"


class Constraint:
    """约束基类"""

    def __init__(self, variables: list[LogicVariable], constraint_type: ConstraintType):
        self.variables = variables
        self.constraint_type = constraint_type

    def is_satisfied(self, substitution: "Substitution") -> bool:
        """检查约束是否满足"""
        raise NotImplementedError("子类必须实现此方法")

    def propagate(self, substitution: "Substitution") -> "Substitution":
        """约束传播"""
        return substitution

    def get_variables(self) -> list[LogicVariable]:
        """获取约束中涉及的变量"""
        return self.variables

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}({self.variables})"


class NumericRangeConstraint(Constraint):
    """数值范围约束"""

    def __init__(self, variable: LogicVariable, min_value: float, max_value: float):
        super().__init__([variable], ConstraintType.NUMERIC_RANGE)
        self.variable = variable
        self.min_value = min_value
        self.max_value = max_value

    def is_satisfied(self, substitution: "Substitution") -> bool:
        """检查变量值是否在范围内"""
        if not substitution.is_bound(self.variable):
            return True  # 未绑定的变量默认满足约束

        value = substitution.get_value(self.variable)
        if isinstance(value, LogicAtom):
            value = value.value

        try:
            numeric_value = float(value)
            # 确保值不是布尔值，因为 bool 继承自 int 会导致误匹配
            if isinstance(value, bool):
                return False
            return self.min_value <= numeric_value <= self.max_value
        except (TypeError, ValueError):
            return False

    def propagate(self, substitution: "Substitution") -> "Substitution":
        """约束传播"""
        return substitution

    def __repr__(self) -> str:
        return f"{self.variable} 在范围 [{self.min_value}, {self.max_value}]"


class EqualityConstraint(Constraint):
    """相等约束"""

    def __init__(self, variable1: LogicVariable, variable2: LogicVariable):
        super().__init__([variable1, variable2], ConstraintType.EQUALITY)
        self.variable1 = variable1
        self.variable2 = variable2

    def is_satisfied(self, substitution: "Substitution") -> bool:
        """检查两个变量是否相等"""
        if not substitution.is_bound(self.variable1) or not substitution.is_bound(
            self.variable2
        ):
            return True

        value1 = substitution.get_value(self.variable1)
        value2 = substitution.get_value(self.variable2)
        return value1 == value2

    def __repr__(self) -> str:
        return f"{self.variable1} = {self.variable2}"


class InequalityConstraint(Constraint):
    """不等约束"""

    def __init__(self, variable1: LogicVariable, variable2: LogicVariable):
        super().__init__([variable1, variable2], ConstraintType.INEQUALITY)
        self.variable1 = variable1
        self.variable2 = variable2

    def is_satisfied(self, substitution: "Substitution") -> bool:
        """检查两个变量是否不等"""
        if not substitution.is_bound(self.variable1) or not substitution.is_bound(
            self.variable2
        ):
            return True

        value1 = substitution.get_value(self.variable1)
        value2 = substitution.get_value(self.variable2)
        return value1 != value2

    def __repr__(self) -> str:
        return f"{self.variable1} != {self.variable2}"


class LessThanConstraint(Constraint):
    """小于约束：``variable1 < variable2``。

    用于描述变量间的顺序关系，是 AC-3 弧一致性传播中体现传递推理
    （如 A < B < C ⟹ A < C）的典型约束。既支持数值，也支持其它可比较
    的类型（例如字符串的字典序）。
    """

    def __init__(self, variable1: LogicVariable, variable2: LogicVariable):
        super().__init__([variable1, variable2], ConstraintType.LESS_THAN)
        self.variable1 = variable1
        self.variable2 = variable2

    def is_satisfied(self, substitution: "Substitution") -> bool:
        """检查左值是否小于右值；任一变量未绑定时视为满足。"""
        if not substitution.is_bound(self.variable1) or not substitution.is_bound(
            self.variable2
        ):
            return True

        value1 = substitution.get_value(self.variable1)
        value2 = substitution.get_value(self.variable2)
        if isinstance(value1, LogicAtom):
            value1 = value1.value
        if isinstance(value2, LogicAtom):
            value2 = value2.value

        try:
            return value1 < value2
        except TypeError:
            return False

    def __repr__(self) -> str:
        return f"{self.variable1} < {self.variable2}"


class TypeConstraint(Constraint):
    """类型约束"""

    def __init__(self, variable: LogicVariable, expected_type: type):
        super().__init__([variable], ConstraintType.TYPE)
        self.variable = variable
        self.expected_type = expected_type

    def is_satisfied(self, substitution: "Substitution") -> bool:
        """检查变量值是否符合类型"""
        if not substitution.is_bound(self.variable):
            return True

        value = substitution.get_value(self.variable)
        if isinstance(value, LogicAtom):
            value = value.value

        return isinstance(value, self.expected_type)

    def __repr__(self) -> str:
        return f"{self.variable} 是 {self.expected_type.__name__}"


class AllDifferentConstraint(Constraint):
    """全不同约束"""

    def __init__(self, variables: list[LogicVariable]):
        super().__init__(variables, ConstraintType.INEQUALITY)
        self.variables = variables

    def is_satisfied(self, substitution: "Substitution") -> bool:
        """检查所有变量值是否互不相同"""
        values = []
        for var in self.variables:
            if not substitution.is_bound(var):
                return True
            value = substitution.get_value(var)
            if isinstance(value, LogicAtom):
                value = value.value
            values.append(value)
        return len(values) == len(set(values))

    def __repr__(self) -> str:
        vars_str = ", ".join(v.name for v in self.variables)
        return f"all_different({vars_str})"


class ConstraintViolationError(QueryError):
    """约束违反错误"""

    def __init__(self, constraint: Constraint, substitution: "Substitution"):
        self.constraint = constraint
        self.substitution = substitution
        super().__init__(f"约束违反: {constraint}")


class ConstraintSolver:
    """约束求解器"""

    def __init__(self, constraints: list[Constraint] | None = None):
        self.constraints: list[Constraint] = constraints or []
        self.variable_constraints: dict[LogicVariable, list[Constraint]] = {}
        # 显式设置的变量候选域，供 AC-3 域缩减与回溯搜索使用
        self.domains: dict[LogicVariable, Domain] = {}
        # 最近一次 solve_constraints 的搜索统计（供性能对比/诊断）
        self.last_search_stats: dict[str, int] = {}
        for constraint in self.constraints:
            self._add_constraint(constraint)

    def add_constraint(self, constraint: Constraint):
        """添加约束"""
        self.constraints.append(constraint)
        self._add_constraint(constraint)

    def _add_constraint(self, constraint: Constraint):
        """内部添加约束方法"""
        for variable in constraint.get_variables():
            if variable not in self.variable_constraints:
                self.variable_constraints[variable] = []
            self.variable_constraints[variable].append(constraint)

    def remove_constraint(self, constraint: Constraint):
        """移除约束"""
        if constraint in self.constraints:
            self.constraints.remove(constraint)
            for variable in constraint.get_variables():
                if variable in self.variable_constraints:
                    if constraint in self.variable_constraints[variable]:
                        self.variable_constraints[variable].remove(constraint)

    def get_constraints_for_variable(self, variable: LogicVariable) -> list[Constraint]:
        """获取变量的所有约束"""
        return self.variable_constraints.get(variable, [])

    def set_domain(self, variable: LogicVariable, values: list[Any]):
        """为变量设置候选域。

        设置后，:meth:`propagate_domains` 与 :meth:`solve_constraints`
        会把该变量纳入 AC-3 域缩减。``variable`` 也可以直接传变量名字符串。
        """
        if isinstance(variable, str):
            variable = LogicVariable(variable)
        self.domains[variable] = Domain(values)

    def get_domain(self, variable: LogicVariable) -> Domain | None:
        """获取变量的候选域；未设置则返回 ``None``。"""
        return self.domains.get(variable)

    def propagate_domains(
        self,
        domains: dict[LogicVariable, Domain] | None = None,
        counter: list[int] | None = None,
    ) -> dict[LogicVariable, Domain] | None:
        """用 AC-3 裁剪候选域，直到达到弧一致。

        参数:
            domains: 待裁剪的域映射；省略时使用通过 :meth:`set_domain`
                设置的域。
            counter: 可选的单元素列表，累计 ``revise`` 调用次数。

        返回:
            裁剪后的域字典（新对象）；若出现空域（约束不可满足）则返回 ``None``。
        """
        source = self.domains if domains is None else domains
        return ac3(self.constraints, source, counter)

    def check_constraints(self, substitution: "Substitution") -> bool:
        """检查所有约束是否满足"""
        for constraint in self.constraints:
            if not constraint.is_satisfied(substitution):
                return False
        return True

    def propagate_constraints(self, substitution: "Substitution") -> "Substitution":
        """约束传播"""
        for constraint in self.constraints:
            substitution = constraint.propagate(substitution)
        return substitution

    def solve_constraints(self, substitution: "Substitution") -> list["Substitution"]:
        """求解约束，返回所有满足约束的替换。

        当所有未绑定变量都通过 :meth:`set_domain` 设置了候选域时，使用
        AC-3 域缩减配合回溯搜索进行剪枝；否则保持原有行为（传播 + 检查），
        以确保接口与既有调用方兼容。
        """
        if not self.check_constraints(substitution):
            return []

        unbound = [
            variable
            for variable in self.variable_constraints
            if not substitution.is_bound(variable)
        ]
        if unbound and all(variable in self.domains for variable in unbound):
            return self._solve_with_domains(substitution)

        # 原有行为：简单传播 + 检查
        propagated = self.propagate_constraints(substitution)
        if self.check_constraints(propagated):
            return [propagated]
        return []

    def _solve_with_domains(
        self, substitution: "Substitution"
    ) -> list["Substitution"]:
        """AC-3 引导的回溯搜索：每层先做域缩减，再按最小剩余值分支。"""
        stats = {
            "assignments": 0,
            "backtracks": 0,
            "ac3_calls": 0,
            "revise_calls": 0,
        }
        domains: dict[LogicVariable, Domain] = {}
        for variable in self.variable_constraints:
            if substitution.is_bound(variable):
                domains[variable] = Domain([substitution.get_value(variable)])
            else:
                domains[variable] = self.domains[variable].copy()

        solutions: list["Substitution"] = []

        def backtrack(current: dict[LogicVariable, Domain]) -> None:
            stats["ac3_calls"] += 1
            revise_counter = [0]
            pruned = ac3(self.constraints, current, counter=revise_counter)
            stats["revise_calls"] += revise_counter[0]
            if pruned is None:
                # AC-3 发现空域：整棵子树不可满足，提前剪枝
                stats["backtracks"] += 1
                return

            unfixed = [
                variable
                for variable in self.variable_constraints
                if len(pruned[variable].values) > 1
            ]
            if not unfixed:
                candidate = substitution.copy()
                for variable, domain in pruned.items():
                    if not candidate.is_bound(variable):
                        values = list(domain.values)
                        candidate.bind(variable, LogicAtom(values[0]))
                if self.check_constraints(candidate):
                    solutions.append(candidate)
                return

            # MRV：优先尝试候选值最少的变量
            variable = min(unfixed, key=lambda v: len(pruned[v].values))
            for value in sorted(pruned[variable].values, key=repr):
                stats["assignments"] += 1
                child = {v: d.copy() for v, d in pruned.items()}
                child[variable] = Domain([value])
                backtrack(child)

        backtrack(domains)
        self.last_search_stats = stats
        return solutions

    def has_constraints(self) -> bool:
        """检查是否有约束"""
        return len(self.constraints) > 0

    def clear_constraints(self):
        """清除所有约束（同时清除候选域与搜索统计）"""
        self.constraints.clear()
        self.variable_constraints.clear()
        self.domains.clear()
        self.last_search_stats.clear()

    def __repr__(self) -> str:
        constraints_str = ", ".join(repr(c) for c in self.constraints)
        return f"ConstraintSolver({constraints_str})"


def is_constrained(variable: LogicVariable, constraints: list[Constraint]) -> bool:
    """检查变量是否有约束"""
    for constraint in constraints:
        if variable in constraint.get_variables():
            return True
    return False


def apply_constraints(
    substitution: "Substitution", constraints: list[Constraint]
) -> list["Substitution"]:
    """应用约束到替换上"""
    solver = ConstraintSolver(constraints)
    return solver.solve_constraints(substitution)


def get_constraints(
    variables: list[LogicVariable], constraints: list[Constraint]
) -> list[Constraint]:
    """获取变量相关的所有约束"""
    result = []
    for constraint in constraints:
        if any(var in variables for var in constraint.get_variables()):
            result.append(constraint)
    return result
