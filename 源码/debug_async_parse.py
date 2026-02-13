#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
调试异步函数解析过程的脚本
"""

from dao.interpreter.core import Interpreter
from dao.lexer.core import Lexer
from dao.parser.core import Parser

test_program = """异步 函数 异步加法(x, y)
    睡眠(0.5)
    返回 x + y

异步 函数 异步乘法(x, y)
    睡眠(0.8)
    返回 x * y

异步 函数 主()
    a = 等待 异步加法(2, 3)
    打印("异步加法结果:", a)

    b = 等待 异步乘法(4, 5)
    打印("异步乘法结果:", b)

运行异步(主())
"""

print("=== 词法分析 ===")
lexer = Lexer(test_program)
tokens = lexer.tokenize()
for i, token in enumerate(tokens, 1):
    print(f"{i:2d} | {token}")

print("\n=== 语法解析 ===")
try:
    parser = Parser(tokens)
    ast = parser.parse()
    print("解析成功!")

    print(f"\n根节点类型: {type(ast).__name__}")
    if hasattr(ast, "body"):
        print(f"主体语句数量: {len(ast.body)}")
        for i, stmt in enumerate(ast.body, 1):
            stmt_type = type(stmt).__name__
            print(f"语句 {i}: {stmt_type}")

except Exception as e:
    print(f"解析失败: {type(e).__name__}: {e}")
    import traceback

    print("\n堆栈跟踪:")
    print(traceback.format_exc())
