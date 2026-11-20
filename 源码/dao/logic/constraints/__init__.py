"""
约束求解模块
============

提供约束求解功能，包括：
- 数值约束（范围、相等、不等）
- 类型约束
- 逻辑约束
- 约束传播算法

约束求解器与逻辑编程引擎集成，支持在查询过程中应用约束条件。
"""

__all__ = [
    "AllDifferentConstraint",
    "Constraint",
    "ConstraintSolver",
    "ConstraintType",
    "ConstraintViolationError",
    "EqualityConstraint",
    "InequalityConstraint",
    "LessThanConstraint",
    "NumericRangeConstraint",
    "TypeConstraint",
    "all_different",
    "apply_constraints",
    "get_constraints",
    "in_range",
    "is_constrained",
]


def in_range(variable, low: int, high: int):
    """创建范围约束"""
    from .core import LogicVariable, NumericRangeConstraint

    if isinstance(variable, str):
        variable = LogicVariable(variable)
    return NumericRangeConstraint(variable, low, high)


def all_different(variables):
    """创建全不同约束"""
    from .core import AllDifferentConstraint, LogicVariable

    normalized = []
    for v in variables:
        if isinstance(v, str):
            normalized.append(LogicVariable(v))
        else:
            normalized.append(v)
    return AllDifferentConstraint(normalized)
