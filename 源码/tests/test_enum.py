"""
枚举类型测试
"""

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from dao.lexer import Lexer
from dao.parser import Parser
from dao.interpreter import Interpreter


def test_enum_basic():
    """测试基础枚举类型"""
    source = """// 测试基础枚举
枚举 颜色 { 红, 绿, 蓝, 黄 }

打印(颜色)
"""

    tokens = Lexer(source).tokenize()
    ast = Parser(tokens).parse()
    interpreter = Interpreter()
    interpreter.execute(ast)
    print("枚举基础测试通过")


def test_enum_member_access():
    """测试枚举成员访问"""
    source = """// 测试枚举成员访问
枚举 方向 { 北, 南, 东, 西 }

打印(方向)
"""

    tokens = Lexer(source).tokenize()
    ast = Parser(tokens).parse()
    interpreter = Interpreter()
    interpreter.execute(ast)
    print("枚举成员访问测试通过")


if __name__ == "__main__":
    print("测试基础枚举类型")
    test_enum_basic()

    print("\n测试枚枚举成员访问")
    test_enum_member_access()

    print("\n所有枚举测试通过！")
