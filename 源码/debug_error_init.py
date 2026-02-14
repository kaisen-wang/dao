#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
直接使用道语言代码测试错误初始化过程的脚本
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from dao.interpreter.core import Interpreter
from dao.lexer.core import Lexer
from dao.parser.core import Parser


def main():
    source = """类型 详细错误 继承自 错误
    初始化(消息, 行号)
        父对象.初始化(消息)
        本对象.行号 = 行号
        本对象.时间 = "2024-01-01"

函数 获取错误实例()
    返 详细错误("测试消息", 10)

函数 测试()
    错误实例 = 获取错误实例()
    打印("错误实例类型:", type(错误实例))
    打印("是否是 DaoError 实例:", isinstance(错误实例, DaoError))
    打印("错误消息:", 错误实例)

    打印("\n错误实例属性:")
    打印("  hasattr(行号):", hasattr(错误实例, "行号"))
    if hasattr(错误实例, "行号"):
        打印("  行号:", 错误实例.行号)
    打印("  hasattr(时间):", hasattr(错误实例, "时间"))
    if hasattr(错误实例, "时间"):
        打印("  时间:", 错误实例.时间)
    打印("  hasattr(类型):", hasattr(错误实例, "类型"))
    if hasattr(错误实例, "类型"):
        打印("  类型:", 错误实例.类型)

    打印("\n所有属性:", dir(错误实例))

测试()
"""

    print("调试道语言错误初始化过程...")
    print("=" * 50)

    try:
        print("1. 词法分析...")
        lexer = Lexer(source)
        tokens = list(lexer.tokenize())
        print(f"   成功生成 {len(tokens)} 个 token")

        print("\n2. 语法分析...")
        parser = Parser(tokens)
        ast = parser.parse()
        print("   成功生成 AST")

        print("\n3. 解释执行...")
        interpreter = Interpreter()
        result = interpreter.execute(ast)
        print(f"   执行结果: {result}")

    except Exception as e:
        print("\n" + "=" * 50)
        print(f"执行过程中出现异常: {type(e).__name__}: {e}")
        import traceback

        print(f"堆栈跟踪: {traceback.format_exc()}")
        return False

    print("\n" + "=" * 50)
    print("调试完成")
    return True


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
