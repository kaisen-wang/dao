#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from dao.lexer import Lexer
from dao.parser import Parser
from dao.tokens import TokenType

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

lexer = Lexer(code, "<调试>")
tokens = lexer.tokenize()

# 显示token序列
print(f"Token序列 ({len(tokens)}个):")
for i, token in enumerate(tokens):
    type_name = token.type.name
    if token.type == TokenType.标识符:
        value = repr(token.value)
    else:
        value = repr(token.value)
    print(f"  [{i:2d}] {type_name:12} : {value}")

print("\n=== 解析代码 ===")
try:
    parser = Parser(tokens, code)
    ast = parser.parse()

    print(f"\n解析结果: {type(ast).__name__}")
    if ast and hasattr(ast, "statements"):
        print(f"语句数量: {len(ast.statements)}")
        for i, stmt in enumerate(ast.statements):
            print(f"  语句 {i}: {type(stmt).__name__}")
            if hasattr(stmt, "body"):
                print(f"    内部语句数量: {len(stmt.body)}")
            if hasattr(stmt, "arguments"):
                print(f"    参数数量: {len(stmt.arguments)}")
except Exception as e:
    print(f"\n解析错误: {type(e).__name__}: {e}")
    import traceback

    print(f"堆栈信息: {traceback.format_exc()}")
