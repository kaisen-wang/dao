#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
跟踪 _apply_macro_parameters 函数的执行
"""

import os
import sys

# 添加项目根目录到 Python 路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from dao.interpreter import Interpreter
from dao.lexer import Lexer

# 导入需要调试的类
from dao.macros.expander import MacroExpander
from dao.parser import Parser

# 猴子补丁：重写 _apply_macro_parameters 函数以添加跟踪
original_apply = MacroExpander._apply_macro_parameters


def traced_apply(self, body, parameters, arguments):
    print("=== _apply_macro_parameters 被调用 ===")
    print(f"  body 类型: {type(body)}")
    print(f"  body: {body}")
    print(f"  parameters: {parameters}")
    print(f"  arguments: {arguments}")
    print(f"  arguments 类型: {[type(arg) for arg in arguments]}")

    result = original_apply(self, body, parameters, arguments)

    print("=== 函数返回 ===")
    print(f"  返回值类型: {type(result)}")
    print(f"  返回值: {result}")

    return result


# 应用补丁
MacroExpander._apply_macro_parameters = traced_apply


def debug_code(code):
    try:
        print("=== 词法分析 ===")
        lexer = Lexer(code, "<测试>")
        tokens = lexer.tokenize()

        print("=== 语法分析 ===")
        parser = Parser(tokens, code)
        ast = parser.parse()

        print("=== 执行代码 ===")
        interpreter = Interpreter()
        result = interpreter.execute(ast, source=code)
        print(f"执行结果: {result}")

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
断言 结果1 == 15
"""
    print("调试可选参数宏")
    print("-" * 40)
    print()
    debug_code(code)


if __name__ == "__main__":
    main()
