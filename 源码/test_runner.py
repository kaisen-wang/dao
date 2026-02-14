#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from dao.builtins import get_builtins, get_interpreter_builtins
from dao.interpreter import Interpreter
from dao.lexer import Lexer
from dao.parser import Parser


def test_logic_program():
    # 读取道语言程序代码
    with open("test_logic_program.道", "r", encoding="utf-8") as f:
        source_code = f.read()

    print("==== 道语言逻辑编程测试 ====")
    print(f"程序源代码:\n{source_code}")
    print("-" * 60)

    try:
        # 词法分析
        lexer = Lexer(source_code, "test_logic_program.道")
        tokens = lexer.tokenize()
        print(f"词法分析完成，生成 {len(tokens)} 个词元")

        # 语法分析
        parser = Parser(tokens, source_code)
        ast = parser.parse()
        print(f"语法分析完成，生成抽象语法树")

        # 创建解释器并执行程序
        interpreter = Interpreter()
        result = interpreter.execute(ast)

        print("程序执行成功！")
        print("-" * 60)
        print(f"执行结果: {result}")

        print("\n==== 程序执行成功 ====")

    except Exception as e:
        print(f"\n==== 执行错误 ====")
        print(f"错误类型: {type(e).__name__}")
        print(f"错误信息: {e}")
        import traceback

        print(f"堆栈跟踪:\n{traceback.format_exc()}")


if __name__ == "__main__":
    test_logic_program()
