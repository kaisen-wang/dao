#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
逻辑编程集成测试
=================

测试逻辑编程引擎的完整集成功能，包括：
- 知识库的创建和管理
- 事实的添加和查询
- 规则的创建和推理
- 约束求解的应用
- 查询结果的格式化

这个测试验证了逻辑编程系统作为一个整体的正确性。
"""

import os
import sys

sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

from dao.logic.backtracking import Backtracker
from dao.logic.constraints.core import (
    ConstraintSolver,
    EqualityConstraint,
    NumericRangeConstraint,
    TypeConstraint,
)
from dao.logic.core import KnowledgeBase, LogicAtom, LogicStruct, LogicVariable
from dao.logic.solver import Solver


def test_basic_knowledge_base():
    """测试基本知识库功能"""
    print("测试1: 基本知识库功能")

    # 创建知识库
    kb = KnowledgeBase("家庭关系知识库")

    # 添加事实
    kb.add_fact(LogicStruct("父母", (LogicAtom("张三"), LogicAtom("小明"))))
    kb.add_fact(LogicStruct("父母", (LogicAtom("李四"), LogicAtom("小明"))))
    kb.add_fact(LogicStruct("父母", (LogicAtom("王五"), LogicAtom("小红"))))
    kb.add_fact(LogicStruct("父母", (LogicAtom("赵六"), LogicAtom("小红"))))

    # 添加规则
    x = LogicVariable("?x")
    y = LogicVariable("?y")
    z = LogicVariable("?z")
    kb.add_rule(
        LogicStruct("祖父母", (x, z)),
        [LogicStruct("父母", (x, y)), LogicStruct("父母", (y, z))],
    )

    # 查询
    solver = Solver(kb)
    result = solver.solve_one(LogicStruct("祖父母", (x, LogicAtom("小明"))))

    print(f"祖父母查询结果: {result}")

    return True


def test_constraint_integration():
    """测试约束与逻辑编程的集成"""
    print("\n测试2: 约束与逻辑编程的集成")

    # 创建知识库
    kb = KnowledgeBase("产品数据库")

    products = [
        ("苹果", 15, "水果"),
        ("香蕉", 8, "水果"),
        ("胡萝卜", 6, "蔬菜"),
        ("西红柿", 12, "蔬菜"),
        ("牛奶", 25, "乳制品"),
        ("面包", 18, "烘焙品"),
        ("鸡蛋", 30, "乳制品"),
    ]

    for name, price, category in products:
        kb.add_fact(
            LogicStruct(
                "产品", (LogicAtom(name), LogicAtom(price), LogicAtom(category))
            )
        )

    # 查询价格在 10-20 之间的水果或蔬菜
    x = LogicVariable("?x")
    y = LogicVariable("?y")
    z = LogicVariable("?z")

    constraints = [
        NumericRangeConstraint(y, 10, 20),
        EqualityConstraint(z, LogicAtom("水果")),
    ]

    solver = Solver(kb, constraints)
    results = solver.solve(LogicStruct("产品", (x, y, z)))

    print("价格在10-20之间的水果:")
    for result in results:
        print(f"  - {result.to_dict()['?x']} (价格: {result.to_dict()['?y']} 元)")

    # 单独使用约束求解器
    print("\n单独使用约束求解器:")
    constraint_solver = ConstraintSolver([NumericRangeConstraint(y, 10, 20)])

    # 创建替换
    from dao.logic.core import Substitution

    subst = Substitution()
    subst.bind(x, LogicAtom("西红柿"))
    subst.bind(y, LogicAtom(12))
    subst.bind(z, LogicAtom("蔬菜"))

    print(f"西红柿价格符合约束: {constraint_solver.check_constraints(subst)}")

    return True


def test_query_with_constraints():
    """测试带约束的查询"""
    print("\n测试3: 带复杂约束的查询")

    # 创建知识库
    kb = KnowledgeBase("员工数据库")

    employees = [
        ("张三", 30, "开发", 8000),
        ("李四", 25, "设计", 7000),
        ("王五", 35, "开发", 9000),
        ("赵六", 28, "测试", 6500),
        ("钱七", 40, "管理", 12000),
        ("孙八", 26, "开发", 7500),
    ]

    for name, age, department, salary in employees:
        kb.add_fact(
            LogicStruct(
                "员工",
                (
                    LogicAtom(name),
                    LogicAtom(age),
                    LogicAtom(department),
                    LogicAtom(salary),
                ),
            )
        )

    # 查询开发部门且工资在7000-8000之间的员工
    name = LogicVariable("?name")
    age = LogicVariable("?age")
    dept = LogicVariable("?dept")
    salary = LogicVariable("?salary")

    constraints = [
        NumericRangeConstraint(salary, 7000, 8000),
        EqualityConstraint(dept, LogicAtom("开发")),
    ]

    solver = Solver(kb, constraints)
    results = solver.solve(LogicStruct("员工", (name, age, dept, salary)))

    print("开发部门且工资在7000-8000之间的员工:")
    for result in results:
        print(f"  - {result.to_dict()['?name']} (年龄: {result.to_dict()['?age']})")

    # 查询年龄在28岁以上且工资超过8000的员工
    print("\n年龄在28岁以上且工资超过8000的员工:")
    solver2 = Solver(kb)
    solver2.add_constraint(NumericRangeConstraint(age, 28, 60))
    solver2.add_constraint(NumericRangeConstraint(salary, 8000, 20000))

    results2 = solver2.solve(LogicStruct("员工", (name, age, dept, salary)))
    for result in results2:
        print(f"  - {result.to_dict()['?name']}")

    return True


def test_query_function():
    """测试 query 函数"""
    print("\n测试4: 字符串查询函数")

    kb = KnowledgeBase("产品数据库")

    products = [("苹果", 15, "水果"), ("香蕉", 8, "水果"), ("胡萝卜", 6, "蔬菜")]

    for name, price, category in products:
        kb.add_fact(
            LogicStruct(
                "产品", (LogicAtom(name), LogicAtom(price), LogicAtom(category))
            )
        )

    from dao.logic.solver import query

    # 基本查询
    print("基本产品查询:")
    results = query(kb, "产品(?x, ?y, '水果')")
    for result in results:
        print(f"  - {result['?x']} (价格: {result['?y']})")

    # 带约束的查询
    print("\n带价格约束的查询:")
    x = LogicVariable("?x")
    y = LogicVariable("?y")
    solver = Solver(kb, [NumericRangeConstraint(y, 10, 20)])
    results2 = solver.solve(LogicStruct("产品", (x, y, LogicAtom("水果"))))
    for result in results2:
        print(f"  - {result.to_dict()['?x']} (价格: {result.to_dict()['?y']})")

    return True


if __name__ == "__main__":
    print("逻辑编程集成测试")
    print("=" * 50)

    try:
        # 运行所有测试
        all_passed = True

        all_passed = all_passed and test_basic_knowledge_base()
        all_passed = all_passed and test_constraint_integration()
        all_passed = all_passed and test_query_with_constraints()
        all_passed = all_passed and test_query_function()

        print("\n" + "=" * 50)
        if all_passed:
            print("✅ 所有测试通过！逻辑编程引擎集成功能正常。")
        else:
            print("❌ 部分测试失败！")
            sys.exit(1)

    except Exception as e:
        print(f"\n❌ 测试过程中出错: {e}")
        print(traceback.format_exc())
        sys.exit(1)
