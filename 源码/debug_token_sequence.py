#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import sys


sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from dao.lexer import Lexer
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

print(f"Token序列 ({len(tokens)}个):")
for i, token in enumerate(tokens):
    type_name = token.type.name
    if token.type == TokenType.标识符:
        value = repr(token.value)
    else:
        value = repr(token.value)
    print(f"  [{i:2d}] {type_name:12} : {value}")
