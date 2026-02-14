#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
测试引述块和注入表达式的语法
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from dao.interpreter import Interpreter
from dao.lexer import Lexer
from dao.parser import Parser


def run_code(source):
    try:
        # 词法分析
        lexer = Lexer(source, "<测试代码>")
        tokens = lexer.tokenize()

        # 语法分析
        parser = Parser(tokens, source)
        ast = parser.parse()

        # 执行代码
        interpreter = Interpreter()
        result = interpreter.execute(ast, source=source)

        return result, interpreter

    except Exception as e:
        print(f"错误: {type(e).__name__}: {e}")
        import traceback

        print(f"堆栈: {traceback.format_exc()}")
        return None, None


def test_quote_block_without_braces():
    """测试不带花括号的引述块语法"""
    code = """
定义宏 测试() {
    返回 引述
        打印("测试引述块")
}

!测试()
"""

    print("=" * 50)
    print("测试不带花括号的引述块语法")
    print("=" * 50)
    result, interpreter = run_code(code)

    if interpreter:
        print("✅ 语法解析成功")
    else:
        print("❌ 语法解析失败")


def test_unquote_without_parentheses():
    """测试不带括号的注入表达式语法"""
    code = """
定义宏 测试(x) {
    返回 引述
        打印(注入 x)
}

!测试("注入表达式")
"""

    print("\n" + "=" * 50)
    print("测试不带括号的注入表达式语法")
    print("=" * 50)
    result, interpreter = run_code(code)

    if interpreter:
        print("✅ 语法解析成功")
    else:
        print("❌ 语法解析失败")


def test_simple_quote_unquote():
    """测试简单的引述和注入语法"""
    code = """
定义宏 加法(a, b) {
    返回 引述
        打印(注入 a + 注入 b)
}

!加法(5, 3)
"""

    print("\n" + "=" * 50)
    print("测试简单的引述和注入语法")
    print("=" * 50)
    result, interpreter = run_code(code)

    if interpreter:
        print("✅ 语法解析成功")
    else:
        print("❌ 语法解析失败")


def test_doc_example():
    """测试文档中的例子"""
    code = """
定义宏 除非(条件, 代码块) {
    返回 引述
        如果 不是 (注入 条件)
            注入 代码块
}

定义 温度 = 15

!除非(温度 > 20,
    打印("天气有点冷，请加衣服。")
)
"""

    print("\n" + "=" * 50)
    print("测试文档中的除非宏例子")
    print("=" * 50)
    result, interpreter = run_code(code)

    if interpreter:
        print("✅ 语法解析成功")
    else:
        print("❌ 语法解析失败")


if __name__ == "__main__":
    test_quote_block_without_braces()
    test_unquote_without_parentheses()
    test_simple_quote_unquote()
    test_doc_example()
