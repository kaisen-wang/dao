"""
约束求解核心模块
================

定义约束类、约束求解器和相关算法。
"""

from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Set

from ..core import LogicAtom, LogicStruct, LogicVariable, normalize_term
from ..exceptions import QueryError


class ConstraintType(Enum):
    """约束类型枚举"""

    NUMERIC_RANGE = "numeric_range"
    EQUALITY = "equality"
    INEQUALITY = "inequality"
    TYPE = "type"
    LOGICAL = "logical"


class Constraint:
    """约束基类"""

    def __init__(self, variables: List[LogicVariable], constraint_type: ConstraintType):
        self.variables = variables
        self.constraint_type = constraint_type

    def is_satisfied(self, substitution: "Substitution") -> bool:
        """检查约束是否满足"""
        raise NotImplementedError("子类必须实现此方法")

    def propagate(self, substitution: "Substitution") -> "Substitution":
        """约束传播"""
        return substitution

    def get_variables(self) -> List[LogicVariable]:
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


class ConstraintViolationError(QueryError):
    """约束违反错误"""

    def __init__(self, constraint: Constraint, substitution: "Substitution"):
        self.constraint = constraint
        self.substitution = substitution
        super().__init__(f"约束违反: {constraint}")


class ConstraintSolver:
    """约束求解器"""

    def __init__(self, constraints: Optional[List[Constraint]] = None):
        self.constraints: List[Constraint] = constraints or []
        self.variable_constraints: Dict[LogicVariable, List[Constraint]] = {}
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

    def get_constraints_for_variable(self, variable: LogicVariable) -> List[Constraint]:
        """获取变量的所有约束"""
        return self.variable_constraints.get(variable, [])

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

    def solve_constraints(self, substitution: "Substitution") -> List["Substitution"]:
        """求解约束"""
        if not self.check_constraints(substitution):
            return []

        results = []
        # 简单的约束传播和检查
        propagated = self.propagate_constraints(substitution)
        if self.check_constraints(propagated):
            results.append(propagated)

        return results

    def has_constraints(self) -> bool:
        """检查是否有约束"""
        return len(self.constraints) > 0

    def clear_constraints(self):
        """清除所有约束"""
        self.constraints.clear()
        self.variable_constraints.clear()

    def __repr__(self) -> str:
        constraints_str = ", ".join(repr(c) for c in self.constraints)
        return f"ConstraintSolver({constraints_str})"


def is_constrained(variable: LogicVariable, constraints: List[Constraint]) -> bool:
    """检查变量是否有约束"""
    for constraint in constraints:
        if variable in constraint.get_variables():
            return True
    return False


def apply_constraints(
    substitution: "Substitution", constraints: List[Constraint]
) -> List["Substitution"]:
    """应用约束到替换上"""
    solver = ConstraintSolver(constraints)
    return solver.solve_constraints(substitution)


def get_constraints(
    variables: List[LogicVariable], constraints: List[Constraint]
) -> List[Constraint]:
    """获取变量相关的所有约束"""
    result = []
    for constraint in constraints:
        if any(var in variables for var in constraint.get_variables()):
            result.append(constraint)
    return result
