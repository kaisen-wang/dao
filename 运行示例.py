#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
运行道语言程序
"""

import os
import sys

sys.path.append(os.path.join(os.path.dirname(__file__), "源码"))

from dao.interpreter import Interpreter
from dao.lexer import Lexer
from dao.parser import Parser


def run_file(filename):
    """运行道语言文件"""
    if not os.path.exists(filename):
        print(f"文件 '{filename}' 不存在")
        return False

    try:
        # 读取源代码
        with open(filename, "r", encoding="utf-8") as f:
            source = f.read()

        # 词法分析
        lexer = Lexer(source, filename)
        tokens = lexer.tokenize()

        # 语法分析
        parser = Parser(tokens)
        ast = parser.parse()

        # 执行
        interpreter = Interpreter()
        interpreter.execute(ast)

        return True

    except Exception as e:
        print(f"错误: {e}")
        import traceback

        traceback.print_exc()
        return False


if __name__ == "__main__":
    if len(sys.argv) > 1:
        filename = sys.argv[1]
    else:
        # 默认运行并发编程示例
        filename = "并发编程示例.道"

    print(f"运行文件: {filename}")
    success = run_file(filename)

    if success:
        print("\n程序执行成功")
    else:
        print("\n程序执行失败")
