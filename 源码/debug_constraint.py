#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import sys

sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

from dao.logic.backtracking import Backtracker
from dao.logic.constraints.core import NumericRangeConstraint
from dao.logic.core import KnowledgeBase, LogicAtom, LogicStruct, LogicVariable


def debug_constraint():
    """调试约束问题"""
    print("调试 NumericRangeConstraint 约束检查")
    print("=" * 50)

    # 创建知识库
    kb = KnowledgeBase("测试知识库")
    kb.add_fact(LogicStruct("数据", (LogicAtom("字符串"),)))
    kb.add_fact(LogicStruct("数据", (LogicAtom(123),)))
    kb.add_fact(LogicStruct("数据", (LogicAtom(True),)))

    # 创建变量和约束
    x = LogicVariable("?x")
    constraints = [NumericRangeConstraint(x, 0, 100)]

    # 创建约束求解器
    from dao.logic.constraints.core import ConstraintSolver

    solver = ConstraintSolver(constraints)

    print(f"约束求解器: {solver}")
    print(f"约束个数: {len(constraints)}")
    print()

    # 创建替换
    from dao.logic.core import Substitution

    subst1 = Substitution()
    subst1.bind(x, LogicAtom("字符串"))
    print(f"替换1 (字符串): {subst1}")
    print(f"约束满足: {solver.check_constraints(subst1)}")
    print()

    subst2 = Substitution()
    subst2.bind(x, LogicAtom(123))
    print(f"替换2 (123): {subst2}")
    print(f"约束满足: {solver.check_constraints(subst2)}")
    print()

    subst3 = Substitution()
    subst3.bind(x, LogicAtom(True))
    print(f"替换3 (True): {subst3}")
    print(f"约束满足: {solver.check_constraints(subst3)}")
    print()


if __name__ == "__main__":
    debug_constraint()
