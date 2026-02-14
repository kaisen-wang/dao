#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
调试可选参数宏测试
"""

import os
import sys

# 添加项目根目录到 Python 路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from dao.environment import Environment
from dao.interpreter.core import Interpreter
from dao.lexer.core import Lexer
from dao.parser.core import Parser


def debug_code(code):
    print("=== 源代码 ===")
    print(code)
    print()

    try:
        print("=== 词法分析 ===")
        lexer = Lexer(code)
        tokens = []
        while True:
            token = lexer.next_token()
            if token.type == "EOF":
                break
            tokens.append(repr(token))

        print(f"共 {len(tokens)} 个 token")
        print()

        print("=== 语法分析 ===")
        parser = Parser(code)
        ast = parser.parse()
        print(f"AST 类型: {type(ast)}")
        print()

        print("=== 执行代码 ===")
        interpreter = Interpreter()
        result = interpreter.execute(ast, source=code)
        print(f"执行结果: {result}")
        print()

        print("=== 执行成功 ===")
        return True

    except Exception as e:
        print(f"=== 错误: {type(e).__name__} ===")
        print(f"{e}")
        import traceback

        print(f"堆栈跟踪: {traceback.format_exc()}")
        return False


def main():
    code = """
定义宏 可选参数(x, y=10) {
    返回 引述 {
        $x + $y
    }
}

设 结果1 = !可选参数(5)
设 结果2 = !可选参数(5, 20)
断言 结果1 == 15
断言 结果2 == 25
"""
    print("调试可选参数宏测试")
    print("-" * 40)
    print()
    debug_code(code)


if __name__ == "__main__":
    main()
