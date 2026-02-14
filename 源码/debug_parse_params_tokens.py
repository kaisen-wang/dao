#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
调试宏参数解析过程，打印token信息
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from dao.lexer import Lexer
from dao.parser import Parser


def test_parse_params():
    code = """
定义宏 可选参数(x, y=10) {
    返回 引述 {
        $x + $y
    }
}
"""

    try:
        # 词法分析
        lexer = Lexer(code, "<调试>")
        tokens = lexer.tokenize()
        print("=== 词法分析结果 ===")
        for i, token in enumerate(tokens):
            print(f"  [{i:2d}] {token.type.name:10} : {repr(token.value)}")

        # 语法分析
        parser = Parser(tokens, code)
        ast = parser.parse()

        print("\n=== 语法分析结果 ===")
        print(ast)
        return True
    except Exception as e:
        print(f"\n=== 错误 ===")
        print(e)
        import traceback

        print(traceback.format_exc())
        return False


if __name__ == "__main__":
    test_parse_params()
