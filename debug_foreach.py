#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
调试遍历语句解析问题
"""

import os
import sys

sys.path.append(os.path.join(os.path.dirname(__file__), "源码"))

from dao.lexer import Lexer
from dao.parser import Parser
from dao.tokens import TokenType


def debug_foreach_parsing():
    """调试遍历语句解析问题"""
    source_code = """异步 函数 计算阶乘(数字)
    定义 结果 = 1
    遍历 i 从 1 到 数字
        结果 = 结果 * i
    返回 结果
""".strip()

    print("=== 调试遍历语句解析 ===")
    print(f"代码内容:\n{source_code}")
    print("-" * 50)

    # 词法分析
    lexer = Lexer(source_code, "测试遍历.道")
    tokens = lexer.tokenize()

    # 打印所有 Token
    print(f"词法分析: {len(tokens)} 个 Token")
    for i, token in enumerate(tokens):
        token_info = f"{i + 1:3d} {token.type.name:<20} '{token.value}'"
        token_info += f" (行:{token.line}, 列:{token.column})"
        print(token_info)

    # 尝试解析
    try:
        parser = Parser(tokens)
        ast = parser.parse()
        print("\n✅ 解析成功")
        print(f"程序结构: {type(ast).__name__}")
        if hasattr(ast, "statements"):
            print(f"语句数量: {len(ast.statements)}")
            for i, stmt in enumerate(ast.statements):
                print(f"  语句{i + 1}: {type(stmt).__name__}")
                if hasattr(stmt, "name"):
                    print(f"    名称: {stmt.name}")
                print(f"    内容: {stmt}")

    except Exception as e:
        print(f"\n❌ 解析错误: {e}")
        import traceback

        print("\n" + traceback.format_exc())

    print("\n" + "-" * 50)


if __name__ == "__main__":
    debug_foreach_parsing()
