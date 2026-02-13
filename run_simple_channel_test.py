#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
运行简单通道测试程序
"""

import os
import sys

sys.path.append(os.path.join(os.path.dirname(__file__), "源码"))

from dao.interpreter import Interpreter
from dao.interpreter.concurrency import ConcurrencyEvaluator
from dao.lexer import Lexer
from dao.parser import Parser


def run_simple_channel_test():
    """运行简单通道测试程序"""
    test_file = "测试简单通道.道"

    print("=== 道语言简单通道测试 ===\n")

    try:
        with open(test_file, "r", encoding="utf-8") as f:
            source_code = f.read()

        # 词法分析
        lexer = Lexer(source_code, test_file)
        tokens = lexer.tokenize()
        print(f"✅ 词法分析完成，共 {len(tokens)} 个 Token")

        # 语法分析
        parser = Parser(tokens)
        ast = parser.parse()
        print(f"✅ 文件解析成功")

        # 创建解释器
        interpreter = Interpreter()

        # 执行程序
        print("\n2. 开始执行程序...\n")
        interpreter.execute(ast)

        print("\n✅ 测试完成!")
        return True

    except Exception as e:
        print(f"\n❌ 执行过程中发生错误: {e}")
        import traceback

        print("\n" + traceback.format_exc())
        return False


if __name__ == "__main__":
    run_simple_channel_test()
