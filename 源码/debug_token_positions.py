#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
调试 tokens 位置
显示 test_macro_with_block 测试中 pos=19 到 pos=23 的 tokens 信息
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from dao.lexer import Lexer
from dao.parser import Parser
from dao.tokens import Token, TokenType


def debug_tokens():
    """调试 tokens 位置"""
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

    print(f"总 tokens 数: {len(tokens)}")
    print(f"")
    print(f"tokens 详情:")
    print(f"")

    # 打印所有 tokens 的详细信息
    for i, token in enumerate(tokens):
        print(
            f"pos={i}: type={token.type.name}, value='{token.value}', line={token.line}, column={token.column}"
        )

    print(f"")
    print(f"--- pos=18 到 pos=25 的 tokens ---")
    for i in range(18, min(26, len(tokens))):
        if i < len(tokens):
            token = tokens[i]
            print(
                f"pos={i}: type={token.type.name}, value='{token.value}', line={token.line}, column={token.column}"
            )


if __name__ == "__main__":
    debug_tokens()
