#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
调试第7行导入语句解析错误
"""

import os
import sys

sys.path.append(os.path.join(os.path.dirname(__file__), "源码"))

from dao.lexer import Lexer
from dao.tokens import TokenType


def debug_line7():
    """调试第7行内容"""
    with open("综合并发测试.道", "r", encoding="utf-8") as f:
        code = f.read()

    print(f"文件内容: {len(code)} 字节")
    print("第7行内容:")
    lines = code.split("\n")
    print("第7行内容:")
    lines = code.split('\n')
    for i, line in enumerate(lines, 1):
        print(f"{i:2d}: '{line}'")
        if i == 7:
            print("-" * 30)

    print("\n--- 词法分析结果 ---")
    lexer = Lexer(code, "综合并发测试.道")
    tokens = lexer.tokenize()

    print(f"总 Token 数: {len(tokens)}")
    line7_tokens = []
    for i, token in enumerate(tokens):
        if token.line == 7:
            line7_tokens.append((i, token))

    if line7_tokens:
        print(f"第7行 Token ({len(line7_tokens)} 个):")
        for token_pos, token in line7_tokens:
            token_info = f"{token_pos:4d}: {token.type.name:<20} '{token.value}'"
            token_info += f" (行:{token.line}, 列:{token.column})"
            print(f"  {token_info}")

    # 检查周围的 Token
    print("\n--- 上下文 Token ---")
    for i, token in enumerate(tokens):
        if 7 - 3 <= token.line <= 7 + 3:
            token_info = f"{i:4d}: {token.type.name:<20} '{token.value}'"
            token_info += f" (行:{token.line}, 列:{token.column})"
            if token.line == 7:
                print(f"→ {token_info}")
            else:
                print(f"  {token_info}")


if __name__ == "__main__":
    debug_line7()
