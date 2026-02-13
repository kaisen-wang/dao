#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
调试异步函数解析
"""

import os
import sys

sys.path.append(os.path.join(os.path.dirname(__file__), "源码"))

from dao.interpreter import Interpreter
from dao.lexer import Lexer
from dao.parser import Parser


def debug_simple_async():
    """调试简单异步函数解析"""
    print("=== 调试简单异步函数 ===")

    with open("简单异步测试.道", "r", encoding="utf-8") as f:
        source_code = f.read()

    print("\n源代码:")
    print("=" * 50)
    print(source_code)
    print("=" * 50)

    # 词法分析
    print("\n1. 词法分析:")
    lexer = Lexer(source_code, "简单异步测试.道")
    tokens = lexer.tokenize()
    print(f"词法分析完成，共 {len(tokens)} 个 Token")

    for i, token in enumerate(tokens):
        token_info = f"{i + 1:3d} {token.type.name:<20} {repr(token.value)}"
        token_info += f" (行:{token.line}, 列:{token.column})"
        print(token_info)

    # 语法分析
    print("\n2. 语法分析:")
    parser = Parser(tokens)
    try:
        ast = parser.parse()
        print("语法分析完成")

        # 打印解析结果
        print(f"\n程序结构: {type(ast).__name__}")
        for i, stmt in enumerate(ast.statements):
            print(f"  语句{i + 1}: {type(stmt).__name__}")
            if hasattr(stmt, "name"):
                print(f"    名称: {stmt.name}")
            if hasattr(stmt, "params"):
                print(f"    参数: {stmt.params}")

        return ast

    except Exception as e:
        print(f"解析错误: {e}")
        import traceback

        print("\n错误堆栈信息:")
        print(traceback.format_exc())
        return None


def debug_async_function_execution():
    """测试异步函数执行"""
    print("\n=== 测试异步函数执行 ===")

    ast = debug_simple_async()

    if ast is not None:
        try:
            print("\n3. 开始执行程序...")
            interpreter = Interpreter()
            interpreter.execute(ast)
            print("✅ 程序执行成功")
        except Exception as e:
            print(f"❌ 执行错误: {e}")
            import traceback

            print(traceback.format_exc())


if __name__ == "__main__":
    print("道语言异步函数解析调试工具")
    print("=" * 50)

    debug_async_function_execution()
