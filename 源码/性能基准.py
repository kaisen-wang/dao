#!/usr/bin/env python3
"""
道语言性能基准测试
==================

用于测试道语言解释器在执行常见操作时的性能表现。
"""

import time
import sys
import os

# 添加源码目录到 Python 路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from dao.lexer import Lexer
from dao.parser import Parser
from dao.interpreter import Interpreter


def run_benchmark(name: str, source: str, iterations: int = 1000):
    """
    运行性能基准测试

    参数：
        name: 测试名称
        source: 道语言代码
        iterations: 执行次数
    """
    print(f"正在测试: {name} ({iterations} 次迭代)")
    
    # 编译阶段（只执行一次）
    lexer = Lexer(source)
    tokens = lexer.tokenize()
    parser = Parser(tokens)
    ast = parser.parse()
    
    # 执行阶段（多次迭代，每次使用新的解释器实例）
    start_time = time.perf_counter()
    for _ in range(iterations):
        interpreter = Interpreter()
        interpreter.execute(ast)
    end_time = time.perf_counter()
    
    total_time = end_time - start_time
    avg_time = total_time / iterations
    
    print(f"总时间: {total_time:.3f} 秒")
    print(f"平均每次: {avg_time:.6f} 秒")
    print()


def main():
    """主函数"""
    print("道语言性能基准测试")
    print("=" * 30)
    print()
    
    # 1. 斐波那契递归
    fib_source = """
函数 斐波那契(n)
    如果 n <= 1
        返回 n
    否则
        返回 斐波那契(n - 1) + 斐波那契(n - 2)
定义 结果 = 斐波那契(10)
    """.strip()
    
    # 2. 循环测试
    loop_source = """
定义 总和 = 0
遍历 i 从 1 到 1000
    总和 = 总和 + i
    """.strip()
    
    # 3. 列表操作
    list_source = """
定义 列表 = []
遍历 i 从 1 到 1000
    列表.追加(i)
定义 总和 = 0
遍历 元素 在 列表
    总和 = 总和 + 元素
    """.strip()
    
    # 4. 字符串拼接
    string_source = """
函数 字符串测试()
    定义 文本 = ""
    遍历 i 从 1 到 100
        文本 = 文本 + "字符"
字符串测试()
    """.strip()
    
    # 5. 函数调用
    function_source = """
函数 加法(a, b)
    返回 a + b
定义 总和 = 0
遍历 i 从 1 到 1000
    总和 = 总和 + 加法(i, i)
    """.strip()
    
    # 运行所有测试
    run_benchmark("斐波那契递归(10)", fib_source, 1000)
    run_benchmark("循环求和(1-1000)", loop_source, 1000)
    run_benchmark("列表操作(1000元素)", list_source, 1000)
    run_benchmark("字符串拼接(100次)", string_source, 1000)
    run_benchmark("函数调用(1000次)", function_source, 1000)
    
    print("测试完成！")


if __name__ == "__main__":
    main()