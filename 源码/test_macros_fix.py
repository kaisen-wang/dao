#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
测试我们修复的宏系统问题
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from dao.interpreter import Interpreter
from dao.lexer import Lexer
from dao.parser import Parser


def run_code(source):
    lexer = Lexer(source, "<test>")
    tokens = lexer.tokenize()

    parser = Parser(tokens, source)
    ast = parser.parse()

    interpreter = Interpreter()
    result = interpreter.execute(ast, source=source)

    return result, interpreter


def test_optional_parameters():
    """测试可选参数宏"""
    print("=== 测试可选参数宏 ===")
    code = """
定义宏 可选参数(x, y=10) {
    返回 引述 {
        $x + $y
    }
}

设 结果1 = !可选参数(5)
设 结果2 = !可选参数(5, 20)

断言 结果1 == 15
断言 结果2 == 25
"""
    result, interpreter = run_code(code)
    print(f"结果1: {interpreter.global_env.get('结果1')}")
    print(f"结果2: {interpreter.global_env.get('结果2')}")

    if (
        interpreter.global_env.get("结果1") == 15
        and interpreter.global_env.get("结果2") == 25
    ):
        print("✅ 可选参数宏修复成功")
    else:
        print("❌ 可选参数宏修复失败")
    print()


def test_block_parameters():
    """测试块参数宏"""
    print("=== 测试块参数宏 ===")
    code = """
定义宏 循环(n, 块) {
    返回 引述 {
        设 i = 0
        当 i < $n {
            $块
            i = i + 1
        }
    }
}

设 总和 = 0
!循环(5) {
    总和 = 总和 + i
}
"""
    result, interpreter = run_code(code)
    print(f"总和: {interpreter.global_env.get('总和')}")

    if interpreter.global_env.get("总和") == 10:
        print("✅ 块参数宏修复成功")
    else:
        print("❌ 块参数宏修复失败")
    print()


def test_macro_injection():
    """测试注入表达式"""
    print("=== 测试注入表达式 ===")
    code = """
定义宏 注入宏() {
    设 a = 1
    设 b = 2
    返回 引述 { $a + $b }
}

设 结果 = !注入宏()
断言 结果 == 3
"""
    result, interpreter = run_code(code)
    print(f"结果: {interpreter.global_env.get('结果')}")

    if interpreter.global_env.get("结果") == 3:
        print("✅ 注入表达式修复成功")
    else:
        print("❌ 注入表达式修复失败")
    print()


def main():
    print("测试我们修复的宏系统问题")
    print("-" * 40)
    print()

    test_optional_parameters()
    test_block_parameters()
    test_macro_injection()

    print("-" * 40)
    print("所有测试完成")


if __name__ == "__main__":
    main()
