#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
调试词法分析器
"""

import os
import sys

sys.path.append(os.path.join(os.path.dirname(__file__), "源码"))

from dao.lexer import Lexer
from dao.tokens import TokenType


def debug_lexer(filename):
    """调试词法分析器"""
    with open(filename, "r", encoding="utf-8") as f:
        source_code = f.read()

    lexer = Lexer(source_code, filename)
    tokens = lexer.tokenize()

    print(f"词法分析完成，共 {len(tokens)} 个 Token")
    print("=" * 60)

    # 打印Token信息
    for i, token in enumerate(tokens):
        token_info = f"{i + 1:3d} {token.type.name:<20} {repr(token.value)}"
        token_info += f" (行:{token.line}, 列:{token.column})"

        if token.line == 5:
            print(f"→ {token_info}")
        else:
            print(f"  {token_info}")

    # 查找可能的错误
    print("\n" + "=" * 60)
    print("可能有问题的第5行:")

    lines = source_code.split("\n")
    if len(lines) > 4:
        print(f"内容: '{lines[4]}'")

        # 检查第5行的Token
        line5_tokens = [t for t in tokens if t.line == 5]
        if line5_tokens:
            print(f"Token: {[(t.type.name, repr(t.value)) for t in line5_tokens]}")

    # 检查特殊标记
    print("\n" + "=" * 60)
    print("所有关键字标记:")
    for t in tokens:
        if t.type.name in ("异步", "函数", "通道", "发送", "接收"):
            print(f"{t.line:3d} {t.type.name:<20} '{t.value}'")


if __name__ == "__main__":
    if len(sys.argv) > 1:
        filename = sys.argv[1]
    else:
        filename = "简单并发测试.道"

    print(f"调试文件: {filename}")
    debug_lexer(filename)
