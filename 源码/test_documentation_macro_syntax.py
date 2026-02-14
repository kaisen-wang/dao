#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
测试文档中描述的`除非`宏是否正常工作
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from dao.interpreter import Interpreter
from dao.lexer import Lexer
from dao.parser import Parser


def run_code(source):
    """执行道语言代码"""
    try:
        print("=== 词法分析 ===")
        lexer = Lexer(source, "<测试代码>")
        tokens = lexer.tokenize()
        for i, token in enumerate(tokens):
            print(f"  [{i:2d}] {token.type.name:10} : {repr(token.value)}")

        print("\n=== 语法分析 ===")
        parser = Parser(tokens, source)
        ast = parser.parse()
        print(f"  成功解析 {len(ast.statements)} 个语句")

        print("\n=== 执行代码 ===")
        interpreter = Interpreter()
        result = interpreter.execute(ast, source=source)

        return result, interpreter

    except Exception as e:
        print(f"\n=== 错误 ===")
        print(f"  类型: {type(e).__name__}")
        print(f"  信息: {e}")
        import traceback

        print(f"  堆栈: {traceback.format_exc()}")
        return None, None


def test_unless_macro_syntax():
    """测试文档中描述的除非宏语法"""
    print("=" * 50)
    print("测试文档中描述的`除非`宏语法")
    print("=" * 50)

    code = """
// 设计一个 `除非` 宏，作为 `如果` 的反义词
定义宏 除非(条件, 代码块) {
    // 引述块将 `如果 ...` 这段代码转换成AST数据结构
    返回 引述
        如果 不是 (注入 条件) // `注入` 将宏参数 `条件` 的AST插入此处
            注入 代码块      // `注入` 将宏参数 `代码块` 的AST插入此处
}

// 使用宏
定义 温度 = 15
!除非(温度 > 20, {
    打印("天气有点冷，请加衣服。")
})

// 上述宏在编译期会被展开为：
如果 不是 (温度 > 20)
    打印("天气有点冷，请加衣服。")
"""

    print("\n执行不带括号的注入语法:")
    result, interpreter = run_code(code)

    if interpreter:
        print(f"\n=== 执行成功 ===")
        if interpreter.global_env.get("温度"):
            print(f"  温度变量: {interpreter.global_env.get('温度')}")
    else:
        print("\n=== 执行失败 ===")


def test_current_unquote_syntax():
    """测试当前实现的注入语法"""
    print("\n" + "=" * 50)
    print("测试当前实现的注入语法")
    print("=" * 50)

    code = """
// 设计一个 `除非` 宏，作为 `如果` 的反义词
定义宏 除非(条件, 代码块) {
    // 引述块将 `如果 ...` 这段代码转换成AST数据结构
    返回 引述 {
        如果 不是 (注入(条件)) // `注入` 将宏参数 `条件` 的AST插入此处
            注入(代码块)      // `注入` 将宏参数 `代码块` 的AST插入此处
    }
}

// 使用宏
定义 温度 = 15
!除非(温度 > 20, {
    打印("天气有点冷，请加衣服。")
})
"""

    print("\n执行带括号的注入语法:")
    result, interpreter = run_code(code)

    if interpreter:
        print(f"\n=== 执行成功 ===")
        if interpreter.global_env.get("温度"):
            print(f"  温度变量: {interpreter.global_env.get('温度')}")
    else:
        print("\n=== 执行失败 ===")


def test_dollar_unquote_syntax():
    """测试 $ 注入语法"""
    print("\n" + "=" * 50)
    print("测试 $ 注入语法")
    print("=" * 50)

    code = """
// 设计一个 `除非` 宏，使用 $ 注入语法
定义宏 除非(条件, 代码块) {
    // 引述块将 `如果 ...` 这段代码转换成AST数据结构
    返回 引用 {
        如果 不是 ($条件) // `$` 将宏参数 `条件` 的AST插入此处
            $代码块      // `$` 将宏参数 `代码块` 的AST插入此处
    }
}

// 使用宏
定义 温度 = 15
!除非(温度 > 20, {
    打印("天气有点冷，请加衣服。")
})
"""

    print("\n执行 $ 注入语法:")
    result, interpreter = run_code(code)

    if interpreter:
        print(f"\n=== 执行成功 ===")
        if interpreter.global_env.get("温度"):
            print(f"  温度变量: {interpreter.global_env.get('温度')}")
    else:
        print("\n=== 执行失败 ===")


def test_simple_macro_with_dollar_syntax():
    """测试简单宏使用 $ 语法"""
    print("\n" + "=" * 50)
    print("测试简单宏使用 $ 语法")
    print("=" * 50)

    code = """
// 定义一个简单的加一宏
定义宏 加一(x) {
    返回 引用 { $x + 1 }
}

// 使用宏
设 结果1 = 加一(5)
打印("加一(5):", 结果1)  // 输出: 6

// 定义一个循环宏
定义宏 循环(n, 块) {
    返回 引用 {
        设 i = 0
        当 i < $n {
            $块
            i = i + 1
        }
    }
}

// 使用块宏
设 总和 = 0
循环(5) {
    总和 = 总和 + i
}
打印("循环5次求和:", 总和)  // 输出: 10
"""

    print("\n执行简单宏使用 $ 语法:")
    result, interpreter = run_code(code)

    if interpreter:
        print(f"\n=== 执行成功 ===")
        if interpreter.global_env.get("结果1"):
            print(f"  结果1: {interpreter.global_env.get('结果1')}")
        if interpreter.global_env.get("总和"):
            print(f"  总和: {interpreter.global_env.get('总和')}")
    else:
        print("\n=== 执行失败 ===")


if __name__ == "__main__":
    test_unless_macro_syntax()
    test_current_unquote_syntax()
    test_dollar_unquote_syntax()
    test_simple_macro_with_dollar_syntax()
