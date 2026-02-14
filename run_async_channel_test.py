#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
测试异步通道通信
"""

import os
import sys

sys.path.append(os.path.join(os.path.dirname(__file__), "源码"))

from dao.interpreter import Interpreter
from dao.lexer import Lexer
from dao.parser import Parser


def run_async_channel_test():
    """测试异步通道通信"""
    test_file = "测试异步通道.道"

    print("=== 运行异步通道通信测试 ===")

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
        print("\n✅ 程序执行成功")

    except Exception as e:
        print(f"❌ 错误: {e}")
        import traceback

        print("\n" + traceback.format_exc())
        return False

    return True


if __name__ == "__main__":
    if run_async_channel_test():
        print("\n✅ 异步通道通信测试通过!")
    else:
        print("\n❌ 异步通道通信测试失败")
