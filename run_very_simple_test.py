#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
运行最简单的并发测试
"""

import os
import sys

sys.path.append(os.path.join(os.path.dirname(__file__), "源码"))

from dao.interpreter import Interpreter
from dao.lexer import Lexer
from dao.parser import Parser


def run_very_simple_test():
    """运行最简单的并发测试"""
    test_file = "最简单并发测试.道"

    print("=== 运行最简单的并发测试 ===")

    try:
        with open(test_file, "r", encoding="utf-8") as f:
            source_code = f.read()

        # 词法分析
        lexer = Lexer(source_code, test_file)
        tokens = lexer.tokenize()
        print(f"词法分析: {len(tokens)} 个 Token")

        # 语法分析
        parser = Parser(tokens)
        ast = parser.parse()
        print(f"解析成功，程序包含 {len(ast.statements)} 个语句")

        # 执行
        interpreter = Interpreter()
        interpreter.execute(ast)
        print("✅ 程序执行成功")

    except Exception as e:
        print(f"❌ 错误: {e}")
        import traceback

        print("\n" + traceback.format_exc())
        return False

    return True


if __name__ == "__main__":
    run_very_simple_test()
