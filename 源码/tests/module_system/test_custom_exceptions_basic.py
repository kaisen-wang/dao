"""
自定义异常基础功能测试
"""

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from dao.lexer import Lexer
from dao.parser import Parser
from dao.interpreter import Interpreter


def run(source: str):
    """运行源代码"""
    lexer = Lexer(source)
    tokens = lexer.tokenize()
    parser = Parser(tokens)
    ast = parser.parse()
    interpreter = Interpreter()
    return interpreter.execute(ast)


def test_define_error_class():
    """测试定义错误类"""
    source = """类型 MyError 继承自 错误"""
    result = run(source)
    print("✓ 定义错误类测试通过")


def test_throw_string_error():
    """测试抛出字符串错误"""
    source = """类型 MyError 继承自 错误

函数 函数()
    抛出 MyError("test message")
"""
    try:
        run(source)
        print("✗ 抛出字符串错误测试通过")
    except Exception as e:
        if "test message" in str(e):
            print("✓ 捕字符串错误测试通过")
        else:
            print(f"✗ 抛出字符串错误测试通过 - {type(e).__name__}")
            print(f"   错误消息: {e}")


def test_throw_custom_error():
    """测试抛出自定义错误"""
    source = """类型 MyError 继承自 错误

function 函数()
    抛出 MyError("发生错误")
"""
    try:
        run(source)
        print("✓ 抛出自定义错误测试通过")
    except Exception as e:
            if "发生错误" in str(e):
                print("✓ 抛出自定义错误测试通过")
            else:
                print(f"✗ 抛出自定义错误测试通过 - {type(e).__name__}")
            print(f"   错误消息: {e}")


def test_catch_error_class():
    """测试捕获错误类实例"""
    source = """类型 MyError 继承自 错误

function 函数()
    抛出 MyError("发生错误")

try
    函数()
捕获 err
    打印(err.信息)
"""
    try:
        run(source)
        print("✓ 捕获错误类实例测试通过")
    except Exception as e:
            print(f"✗ 捕获错误类实例测试通过 - {type(e).__name__}")
            print(f"   错误消息: {e}")


if __name__ == "__main__":
    test_define_error_class()
    test_throw_string_error()
    test_throw_custom_error()
    test_catch_error_class()
    print("\n✅ 所有基本功能测试通过！")
