"""
解构匹配测试
"""

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from dao.lexer import Lexer
from dao.parser import Parser
from dao.interpreter import Interpreter


def test_list_destructure():
    """测试列表解构赋值"""
    source = """
定义 [a, b, c] = [1, 2, 3]
打印(a)
打印(b)
打印(c)
    [a, b] = [b, a, c]
打印(a)
打印(b)
打印(c)
    """

    try:
        tokens = Lexer(source).tokenize()
        ast = Parser(tokens).parse()
        interpreter = Interpreter()
        interpreter.execute(ast)
        print("✅ 列表解构测试通过")
    except Exception as e:
        print(f"❌ 列表解构测试失败: {type(e).__name__}: {e}")


def test_dict_destructure():
    """测试字典解构赋值"""
    source = """
定义 {"姓名": 名字, "年龄": 年龄} = {"姓名": "张三", "年龄": "25"}
打印(姓名)
打印(年龄)
    {"姓名": 名字, "城市": 城市} = {"姓名": "李四", "城市": "北京"}
打印(姓名)
打印(城市)
    """

    try:
        tokens = Lexer(source).tokenize()
        ast = Parser(tokens).parse()
        interpreter = Interpreter()
        interpreter.execute(ast)
        print("✅ 字典解构测试通过")
    except Exception as e:
        print(f"❌ 字典解构测试失败: {type(e).__name__}: {e}")


if __name__ == "__main__":
    print("测试列表解构赋值")
    test_list_destructure()
    print("\n测试字典解构赋值")
    test_dict_destructure()
    print("\n所有测试通过！")
