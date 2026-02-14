#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
调试 parse_block 的实际 pos 值
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from dao.ast_nodes import *
from dao.lexer import Lexer
from dao.parser import Parser


def debug_positions():
    """调试 pos 位置"""
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

    lexer = Lexer(code)
    tokens = lexer.tokenize()

    # 打印所有 tokens 的详细信息
    print("=== Tokens ===")
    for i, token in enumerate(tokens):
        print(
            f"pos={i:2}: type={token.type.name}, value='{token.value}', line={token.line}, column={token.column}"
        )
        if token.value == "$块":
            print(f"  找到 $块 在 pos={i}")

    print("\n=== Parsing ===")
    try:
        parser = Parser(tokens)
        ast = parser.parse()

        print("=== AST ===")
        print(ast)

    except Exception as e:
        print(f"Error: {e}")
        import traceback

        print(traceback.format_exc())


if __name__ == "__main__":
    debug_positions()
