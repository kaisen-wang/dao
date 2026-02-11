"""
测试模式匹配中的列表和字典模式
"""

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from dao.lexer import Lexer
from dao.parser import Parser
from dao.interpreter import Interpreter


def test_list_pattern_match():
    """测试列表模式匹配"""
    source = """
定义 数据 = [1, 2, 3, 4, 5]

匹配 数据
    情况 [x, y, ...rest]
        打印("前两个:", x, y)
        打印("剩余:", rest)
    情况 [x]
        打印("单个:", x)
    情况 _
        打印("其他")
    """

    try:
        tokens = Lexer(source).tokenize()
        ast = Parser(tokens).parse()
        interpreter = Interpreter()
        interpreter.execute(ast)
        print("[OK] 列表模式匹配测试通过")
    except Exception as e:
        print(f"[FAIL] 列表模式匹配测试失败: {type(e).__name__}: {e}")
        import traceback

        traceback.print_exc()


def test_single_element_list_pattern():
    """测试单元素列表模式匹配"""
    source = """
定义 数据 = [42]

匹配 数据
    情况 [x, y, ...rest]
        打印("前两个:", x, y)
    情况 [x]
        打印("单个:", x)
    情况 _
        打印("其他")
    """

    try:
        tokens = Lexer(source).tokenize()
        ast = Parser(tokens).parse()
        interpreter = Interpreter()
        interpreter.execute(ast)
        print("[OK] 单元素列表模式匹配测试通过")
    except Exception as e:
        print(f"[FAIL] 单元素列表模式匹配测试失败: {type(e).__name__}: {e}")
        import traceback

        traceback.print_exc()


def test_dict_pattern_match():
    """测试字典模式匹配"""
    source = """
定义 人 = {"姓名": "张三", "年龄": 25, "城市": "北京"}

匹配 人
    情况 {"姓名": 名字, "年龄": age}
        打印("姓名:", 名字, "年龄:", age)
    情况 _
        打印("其他")
    """

    try:
        tokens = Lexer(source).tokenize()
        ast = Parser(tokens).parse()
        interpreter = Interpreter()
        interpreter.execute(ast)
        print("[OK] 字典模式匹配测试通过")
    except Exception as e:
        print(f"[FAIL] 字典模式匹配测试失败: {type(e).__name__}: {e}")
        import traceback

        traceback.print_exc()


def test_dict_pattern_multiple_keys():
    """测试多键字典模式匹配"""
    source = """
定义 人 = {"姓名": "李四", "年龄": 30, "城市": "上海"}

匹配 人
    情况 {"姓名": 名字, "年龄": age, "城市": city}
        打印("姓名:", 名字, "年龄:", age, "城市:", city)
    情况 _
        打印("其他")
    """

    try:
        tokens = Lexer(source).tokenize()
        ast = Parser(tokens).parse()
        interpreter = Interpreter()
        interpreter.execute(ast)
        print("[OK] 多键字典模式匹配测试通过")
    except Exception as e:
        print(f"[FAIL] 多键字典模式匹配测试失败: {type(e).__name__}: {e}")
        import traceback

        traceback.print_exc()


if __name__ == "__main__":
    print("测试列表模式匹配")
    test_list_pattern_match()
    print("\n测试单元素列表模式匹配")
    test_single_element_list_pattern()
    print("\n测试字典模式匹配")
    test_dict_pattern_match()
    print("\n测试多键字典模式匹配")
    test_dict_pattern_multiple_keys()
    print("\n所有测试完成！")
