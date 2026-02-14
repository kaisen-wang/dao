#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
调试脚本来查看错误对象的属性访问问题
"""

import os
import sys

# 添加项目根目录到 Python 路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from dao.ast_nodes import *
from dao.interpreter.core import Interpreter
from dao.lexer.core import Lexer
from dao.parser.core import Parser


def main():
    # 使用正确的道语言语法
    code = """
测试错误属性访问
    尝试
        抛出 运行时错误("测试消息")

    捕获 异常 为 e
        打印("错误对象:", e)
        打印("错误类型:", type(e))
        打印("错误字符串表示:", str(e))
        打印("错误消息:", e.message)
        打印("错误行号:", e.行)
        打印("错误列号:", e.列)
        打印("错误信息:", e.信息)
        打印("所有属性:", dir(e))

测试错误属性访问()
"""

    print("调试脚本开始运行...")
    print("=" * 50)

    try:
        # 词法分析
        lexer = Lexer(code)
        tokens = lexer.tokenize()
        print(f"词法分析完成，共生成 {len(tokens)} 个 Token")

        # 语法分析
        parser = Parser(tokens)
        ast = parser.parse()
        print("语法分析完成，生成了有效的 AST")

        # 解释执行
        interpreter = Interpreter(code)
        print("解释器执行结果:")
        interpreter.execute(ast)

    except Exception as e:
        print("=" * 50)
        print(f"执行过程中出现异常: {type(e).__name__}: {e}")
        import traceback

        print(f"堆栈跟踪: {traceback.format_exc()}")
        return False

    print("=" * 50)
    print("调试脚本执行完成")
    return True


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
