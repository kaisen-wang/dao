#!/usr/bin/env python3
"""
道语言宏系统性能基准测试
======================

测试宏展开、参数替换、卫生处理等核心操作的性能。
目标：单次宏展开 < 1ms
"""

import time
import sys
import os
import statistics

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..'))

from dao.lexer import Lexer
from dao.parser import Parser
from dao.interpreter import Interpreter
from dao.macros.expander import MacroExpander
from dao.macros.registry import MacroRegistry
from dao.macros.builtins import register_builtin_macros
from dao.ast_nodes import (
    Identifier, NumberLiteral, StringLiteral, BinaryOp,
    QuoteBlock, MacroCall, VariableDecl, ExpressionStmt,
    IfStmt, UnaryOp, BooleanLiteral, NullLiteral,
)


def measure_time(func, iterations=1000):
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


def benchmark_macro_expansion():
    """基准测试：宏展开性能"""
    print("=== 宏展开性能基准测试 ===")
    print(f"目标：单次宏展开 < 1ms\n")

    # 测试1：简单宏展开
    expander = MacroExpander()
    expander.register_builtin_macros()

    macro_info = expander.registry.find_macro("除非")
    call = MacroCall(
        name="除非",
        arguments=[
            BinaryOp(left=Identifier(name="x"), operator=">", right=NumberLiteral(value=10)),
            Identifier(name="代码块"),
        ],
    )

    stats = measure_time(lambda: expander._expand_macro_call(call, 0), 1000)
    print(f"1. @除非 宏展开 (1000次)")
    print(f"   平均: {stats['avg_ms']:.3f}ms, 最小: {stats['min_ms']:.3f}ms, "
          f"最大: {stats['max_ms']:.3f}ms, P95: {stats['p95_ms']:.3f}ms")
    print(f"   {'通过' if stats['avg_ms'] < 1.0 else '未达标'} (目标 < 1ms)\n")

    # 测试2：@延迟 宏展开
    call_delay = MacroCall(
        name="延迟",
        arguments=[Identifier(name="代码块")],
    )
    stats = measure_time(lambda: expander._expand_macro_call(call_delay, 0), 1000)
    print(f"2. @延迟 宏展开 (1000次)")
    print(f"   平均: {stats['avg_ms']:.3f}ms, 最小: {stats['min_ms']:.3f}ms, "
          f"最大: {stats['max_ms']:.3f}ms, P95: {stats['p95_ms']:.3f}ms")
    print(f"   {'通过' if stats['avg_ms'] < 1.0 else '未达标'} (目标 < 1ms)\n")

    # 测试3：@缓存 宏展开
    call_cache = MacroCall(
        name="缓存",
        arguments=[Identifier(name="键"), Identifier(name="代码块")],
    )
    stats = measure_time(lambda: expander._expand_macro_call(call_cache, 0), 1000)
    print(f"3. @缓存 宏展开 (1000次)")
    print(f"   平均: {stats['avg_ms']:.3f}ms, 最小: {stats['min_ms']:.3f}ms, "
          f"最大: {stats['max_ms']:.3f}ms, P95: {stats['p95_ms']:.3f}ms")
    print(f"   {'通过' if stats['avg_ms'] < 1.0 else '未达标'} (目标 < 1ms)\n")


def benchmark_parameter_replacement():
    """基准测试：参数替换性能"""
    print("=== 参数替换性能基准测试 ===\n")

    expander = MacroExpander()

    # 构建一个包含多个参数引用的宏体
    body = QuoteBlock(body=[
        VariableDecl(
            name="结果",
            value=BinaryOp(
                left=BinaryOp(
                    left=Identifier(name="a"),
                    operator="+",
                    right=Identifier(name="b"),
                ),
                operator="*",
                right=Identifier(name="c"),
            ),
        ),
        ExpressionStmt(expression=Identifier(name="结果")),
    ])

    replacements = {
        "a": NumberLiteral(value=1),
        "b": NumberLiteral(value=2),
        "c": NumberLiteral(value=3),
    }

    stats = measure_time(
        lambda: expander._replace_in_node(body, replacements),
        1000,
    )
    print(f"1. 3参数替换 (1000次)")
    print(f"   平均: {stats['avg_ms']:.3f}ms, 最小: {stats['min_ms']:.3f}ms, "
          f"最大: {stats['max_ms']:.3f}ms, P95: {stats['p95_ms']:.3f}ms")
    print(f"   {'通过' if stats['avg_ms'] < 1.0 else '未达标'} (目标 < 1ms)\n")

    # 测试深层嵌套替换
    deep_body = QuoteBlock(body=[
        IfStmt(
            condition=BinaryOp(
                left=Identifier(name="x"),
                operator=">",
                right=NumberLiteral(value=0),
            ),
            body=[
                VariableDecl(
                    name="y",
                    value=BinaryOp(
                        left=Identifier(name="x"),
                        operator="*",
                        right=Identifier(name="x"),
                    ),
                ),
                ExpressionStmt(expression=Identifier(name="y")),
            ],
        ),
    ])

    deep_replacements = {
        "x": NumberLiteral(value=42),
    }

    stats = measure_time(
        lambda: expander._replace_in_node(deep_body, deep_replacements),
        1000,
    )
    print(f"2. 深层嵌套替换 (1000次)")
    print(f"   平均: {stats['avg_ms']:.3f}ms, 最小: {stats['min_ms']:.3f}ms, "
          f"最大: {stats['max_ms']:.3f}ms, P95: {stats['p95_ms']:.3f}ms")
    print(f"   {'通过' if stats['avg_ms'] < 1.0 else '未达标'} (目标 < 1ms)\n")


def benchmark_end_to_end():
    """基准测试：端到端宏执行性能"""
    print("=== 端到端宏执行基准测试 ===\n")

    # 测试1：@除非 宏端到端
    source_除非 = '设 结果 = !除非(1 > 2)\n    42'
    stats = measure_time(
        lambda: Interpreter().execute(Parser(Lexer(source_除非).tokenize()).parse()),
        100,
    )
    print(f"1. @除非 宏端到端 (100次)")
    print(f"   平均: {stats['avg_ms']:.3f}ms, P95: {stats['p95_ms']:.3f}ms\n")

    # 测试2：@延迟 宏端到端
    source_延迟 = '设 值 = !延迟()\n    1 + 2'
    stats = measure_time(
        lambda: Interpreter().execute(Parser(Lexer(source_延迟).tokenize()).parse()),
        100,
    )
    print(f"2. @延迟 宏端到端 (100次)")
    print(f"   平均: {stats['avg_ms']:.3f}ms, P95: {stats['p95_ms']:.3f}ms\n")

    # 测试3：用户自定义宏端到端
    source_自定义 = '''
定义宏 双倍(x)
    返回 引述 $x * 2
设 结果 = !双倍(21)
    '''
    stats = measure_time(
        lambda: Interpreter().execute(Parser(Lexer(source_自定义).tokenize()).parse()),
        100,
    )
    print(f"3. 用户自定义宏端到端 (100次)")
    print(f"   平均: {stats['avg_ms']:.3f}ms, P95: {stats['p95_ms']:.3f}ms\n")


def main():
    """主函数"""
    print("道语言宏系统性能基准测试")
    print("=" * 40)
    print()

    benchmark_macro_expansion()
    benchmark_parameter_replacement()
    benchmark_end_to_end()

    print("测试完成！")


if __name__ == "__main__":
    main()
