#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
运行综合并发测试
"""

import os
import sys

sys.path.append(os.path.join(os.path.dirname(__file__), "源码"))

import time

from dao.interpreter import Interpreter
from dao.lexer import Lexer
from dao.parser import Parser


def run_comprehensive_test():
    """运行综合并发测试"""
    test_file = "综合并发测试.道"

    print("=== 运行综合并发测试 ===")

    try:
        with open(test_file, "r", encoding="utf-8") as f:
            source_code = f.read()

        # 词法分析
        lexer = Lexer(source_code, test_file)
        tokens = lexer.tokenize()
        print(f"词法分析: {len(tokens)} 个 Token")

        # 语法分析
        parser = Parser(tokens)
        ast = parser.parse()
        print(f"解析成功，程序包含 {len(ast.statements)} 个语句")

        # 执行
        interpreter = Interpreter()
        start_time = time.time()
        interpreter.execute(ast)
        end_time = time.time()

        print(f"✅ 程序执行成功，耗时: {end_time - start_time:.2f} 秒")

    except Exception as e:
        print(f"❌ 错误: {e}")
        import traceback

        print("\n" + traceback.format_exc())
        return False

    return True


def test_function_parsing():
    """测试函数解析"""
    code = """异步 函数 延迟执行(毫秒)
    打印("延迟执行:", 毫秒)
    返回 毫秒 * 2

异步 函数 计算阶乘(数字)
    定义 结果 = 1
    对于 i 从 1 到 数字
        结果 = 结果 * i
    返回 结果
    """.strip()

    print("=== 测试函数解析 ===")
    lexer = Lexer(code, "函数测试.道")
    tokens = lexer.tokenize()
    print(f"词法分析: {len(tokens)} 个 Token")

    parser = Parser(tokens)
    try:
        ast = parser.parse()
        print(f"解析成功，{len(ast.statements)} 个语句")
        for stmt in ast.statements:
            if hasattr(stmt, "name"):
                print(
                    f"  函数: {stmt.name}, 参数: {len(stmt.params)}, 常量: {stmt.is_constant}"
                )
        return True
    except Exception as e:
        print(f"❌ 解析错误: {e}")
        return False


if __name__ == "__main__":
    print("道语言综合并发测试套件")
    print("=" * 50)

    all_passed = True

    print("\n" + "-" * 50 + "\n")
    if not test_function_parsing():
        all_passed = False

    print("\n" + "-" * 50 + "\n")
    if not run_comprehensive_test():
        all_passed = False

    print("\n" + "-" * 50 + "\n")
    if all_passed:
        print("🎉 所有并发编程功能测试通过!")
    else:
        print("⚠️  测试过程中发现问题")
