"""
自定义异常简单测试
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
    print("定义错误类测试通过")


def test_throw_custom_error():
    """测试抛出自定义错误"""
    source = """类型 MyError 继承自 错误

函数 test()
    抛出 MyError("test message")
"""
    try:
        run(source)
        print("失败: 应该抛出异常")
    except Exception as e:
        if "test message" in str(e):
            print("抛出和捕获测试通过")
        else:
            print("失败:", str(e))


if __name__ == "__main__":
    test_define_error_class()
    test_throw_custom_error()
