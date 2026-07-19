#!/usr/bin/env python3
"""
道语言逻辑编程性能基准测试
========================

测试逻辑编程核心操作的性能。
目标：小规模逻辑查询 < 10ms
"""

import time
import sys
import os
import statistics

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..'))

from dao.logic.core import KnowledgeBase, LogicStruct, LogicVariable, LogicAtom
from dao.logic.solver import Solver


def measure_time(func, iterations=100):
    """测量函数执行时间，返回统计信息"""
    times = []
    for _ in range(iterations):
        start = time.perf_counter()
        func()
        end = time.perf_counter()
        times.append(end - start)

    avg_ms = statistics.mean(times) * 1000
    min_ms = min(times) * 1000
    max_ms = max(times) * 1000
    p95_ms = sorted(times)[int(len(times) * 0.95)] * 1000
    return {
        "avg_ms": avg_ms,
        "min_ms": min_ms,
        "max_ms": max_ms,
        "p95_ms": p95_ms,
    }


def benchmark_simple_query():
    """基准测试：简单事实查询"""
    print("=== 简单事实查询性能基准测试 ===")
    print(f"目标：小规模逻辑查询 < 10ms\n")

    # 构建知识库：10个事实
    kb = KnowledgeBase("简单查询")
    for i in range(10):
        kb.add_fact(LogicStruct("事实", (LogicAtom(f"值{i}"),)))

    solver = Solver(kb)

    # 测试1：单事实查询
    goal = LogicStruct("事实", (LogicVariable("?x"),))
    stats = measure_time(lambda: solver.solve(goal), 100)
    print(f"1. 单事实查询 (100次)")
    print(f"   平均: {stats['avg_ms']:.3f}ms, 最小: {stats['min_ms']:.3f}ms, "
          f"最大: {stats['max_ms']:.3f}ms, P95: {stats['p95_ms']:.3f}ms")
    print(f"   {'通过' if stats['avg_ms'] < 10.0 else '未达标'} (目标 < 10ms)\n")

    # 测试2：精确匹配查询
    goal = LogicStruct("事实", (LogicAtom("值5"),))
    stats = measure_time(lambda: solver.solve(goal), 100)
    print(f"2. 精确匹配查询 (100次)")
    print(f"   平均: {stats['avg_ms']:.3f}ms, 最小: {stats['min_ms']:.3f}ms, "
          f"最大: {stats['max_ms']:.3f}ms, P95: {stats['p95_ms']:.3f}ms")
    print(f"   {'通过' if stats['avg_ms'] < 10.0 else '未达标'} (目标 < 10ms)\n")


def benchmark_rule_query():
    """基准测试：规则推理查询"""
    print("=== 规则推理查询性能基准测试 ===\n")

    # 构建知识库：家庭关系
    kb = KnowledgeBase("家庭关系")
    # 添加事实
    parents = [
        ("张三", "小明"), ("李四", "小明"),
        ("张三", "小红"), ("小明", "乐乐"),
        ("王五", "小刚"), ("王五", "小丽"),
    ]
    for parent, child in parents:
        kb.add_fact(LogicStruct("父母", (LogicAtom(parent), LogicAtom(child))))

    # 添加规则：祖父母
    kb.add_rule(
        LogicStruct("祖父母", (LogicVariable("?祖"), LogicVariable("?孙"))),
        [
            LogicStruct("父母", (LogicVariable("?祖"), LogicVariable("?父"))),
            LogicStruct("父母", (LogicVariable("?父"), LogicVariable("?孙"))),
        ]
    )

    solver = Solver(kb)

    # 测试1：单层规则推理
    goal = LogicStruct("祖父母", (LogicVariable("?祖"), LogicVariable("?孙")))
    stats = measure_time(lambda: solver.solve(goal), 100)
    print(f"1. 单层规则推理 (100次)")
    print(f"   平均: {stats['avg_ms']:.3f}ms, 最小: {stats['min_ms']:.3f}ms, "
          f"最大: {stats['max_ms']:.3f}ms, P95: {stats['p95_ms']:.3f}ms")
    print(f"   {'通过' if stats['avg_ms'] < 10.0 else '未达标'} (目标 < 10ms)\n")

    # 测试2：事实直接查询
    goal = LogicStruct("父母", (LogicVariable("?x"), LogicVariable("?y")))
    stats = measure_time(lambda: solver.solve(goal), 100)
    print(f"2. 事实直接查询 (100次)")
    print(f"   平均: {stats['avg_ms']:.3f}ms, 最小: {stats['min_ms']:.3f}ms, "
          f"最大: {stats['max_ms']:.3f}ms, P95: {stats['p95_ms']:.3f}ms")
    print(f"   {'通过' if stats['avg_ms'] < 10.0 else '未达标'} (目标 < 10ms)\n")


def benchmark_negation_query():
    """基准测试：否定查询"""
    print("=== 否定查询性能基准测试 ===\n")

    kb = KnowledgeBase("否定测试")
    for i in range(5):
        kb.add_fact(LogicStruct("存在", (LogicAtom(f"项{i}"),)))

    solver = Solver(kb)

    # 测试否定查询
    goal = LogicStruct("存在", (LogicAtom("不存在项"),))
    stats = measure_time(lambda: solver.solve_negation(goal), 100)
    print(f"1. 否定查询（不存在的事实） (100次)")
    print(f"   平均: {stats['avg_ms']:.3f}ms, 最小: {stats['min_ms']:.3f}ms, "
          f"最大: {stats['max_ms']:.3f}ms, P95: {stats['p95_ms']:.3f}ms")
    print(f"   {'通过' if stats['avg_ms'] < 10.0 else '未达标'} (目标 < 10ms)\n")


def benchmark_knowledge_base_operations():
    """基准测试：知识库操作性能"""
    print("=== 知识库操作性能基准测试 ===\n")

    # 测试1：添加事实
    stats = measure_time(lambda: _create_kb_with_facts(100), 100)
    print(f"1. 添加100个事实 (100次)")
    print(f"   平均: {stats['avg_ms']:.3f}ms, P95: {stats['p95_ms']:.3f}ms\n")

    # 测试2：添加规则
    stats = measure_time(lambda: _create_kb_with_rules(50), 100)
    print(f"2. 添加50条规则 (100次)")
    print(f"   平均: {stats['avg_ms']:.3f}ms, P95: {stats['p95_ms']:.3f}ms\n")


def _create_kb_with_facts(n: int) -> KnowledgeBase:
    """创建包含n个事实的知识库"""
    kb = KnowledgeBase("测试")
    for i in range(n):
        kb.add_fact(LogicStruct("事实", (LogicAtom(f"值{i}"),)))
    return kb


def _create_kb_with_rules(n: int) -> KnowledgeBase:
    """创建包含n条规则的知识库"""
    kb = KnowledgeBase("测试")
    kb.add_fact(LogicStruct("基础", (LogicAtom("真"),)))
    for i in range(n):
        kb.add_rule(
            LogicStruct(f"规则{i}", (LogicVariable("?x"),)),
            [LogicStruct("基础", (LogicVariable("?x"),))]
        )
    return kb


def main():
    """主函数"""
    print("道语言逻辑编程性能基准测试")
    print("=" * 40)
    print()

    benchmark_simple_query()
    benchmark_rule_query()
    benchmark_negation_query()
    benchmark_knowledge_base_operations()

    print("测试完成！")


if __name__ == "__main__":
    main()
