"""
运算符重载测试
===============

测试 运算符 关键字的功能：
- 重载基本运算符（+, -, *, /, %, **）
- 重载比较运算符（==, !=, <, <=, >, >=）
- 运算符重载方法有返回值
- 运算符重载可以抛出错误
"""

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from dao.lexer import Lexer
from dao.parser import Parser
from dao.interpreter import Interpreter
from dao.errors import 运行时错误
from dao.ast_nodes import FunctionDecl


def parse(source: str):
    """辅助函数：解析源代码"""
    tokens = Lexer(source).tokenize()
    return Parser(tokens).parse()


def execute(source: str):
    """辅助函数：执行源代码"""
    ast = parse(source)
    interpreter = Interpreter()
    interpreter.execute(ast)
    return interpreter.global_env.values


def test_operator_plus_overload():
    """测试 + 运算符重载"""
    source = """
类型 向量
    初始化(x, y)
        本对象.x = x
        本对象.y = y

    运算符+(其他)
        返回 向量(本对象.x + 其他.x, 本对象.y + 其他.y)

定义 v1 = 向量(1, 2)
定义 v2 = 向量(3, 4)
定义 v3 = v1 + v2
"""
    result = execute(source)
    assert "v3" in result
    assert result["v3"].fields["x"] == 4
    assert result["v3"].fields["y"] == 6


def test_operator_minus_overload():
    """测试 - 运算符重载"""
    source = """
类型 复数
    初始化(实部, 虚部)
        本对象.实部 = 实部
        本对象.虚部 = 虚部

    运算符-(其他)
        返回 复数(本对象.实部 - 其他.实部, 本对象.虚部 - 其他.虚部)

定义 c1 = 复数(5, 3)
定义 c2 = 复数(2, 1)
定义 c3 = c1 - c2
"""
    result = execute(source)
    assert result["c3"].fields["实部"] == 3
    assert result["c3"].fields["虚部"] == 2


def test_operator_multiply_overload():
    """测试 * 运算符重载"""
    source = """
类型 向量
    初始化(x, y)
        本对象.x = x
        本对象.y = y

    运算符*(标量)
        返回 向量(本对象.x * 标量, 本对象.y * 标量)

定义 v = 向量(2, 3)
定义 v2 = v * 3
"""
    result = execute(source)
    assert result["v2"].fields["x"] == 6
    assert result["v2"].fields["y"] == 9


def test_operator_divide_overload():
    """测试 / 运算符重载"""
    source = """
类型 分数
    初始化(分子, 分母)
        本对象.分子 = 分子
        本对象.分母 = 分母

    运算符/(其他)
        返回 分数(本对象.分子 * 其他.分母, 本对象.分母 * 其他.分子)

定义 f1 = 分数(1, 2)
定义 f2 = 分数(1, 3)
定义 f3 = f1 / f2
"""
    result = execute(source)
    assert result["f3"].fields["分子"] == 3
    assert result["f3"].fields["分母"] == 2


def test_operator_modulo_overload():
    """测试 % 运算符重载"""
    source = """
类型 模数
    初始化(值, 模)
        本对象.值 = 值
        本对象.模 = 模

    运算符%(其他)
        返回 模数(本对象.值 % 其他.模, 本对象.模)

定义 m1 = 模数(10, 3)
定义 m2 = 模数(0, 5)
定义 m3 = m1 % m2
"""
    result = execute(source)
    assert result["m3"].fields["值"] == 0
    assert result["m3"].fields["模"] == 3


def test_operator_power_overload():
    """测试 ** 运算符重载"""
    source = """
类型 矩阵2x2
    初始化(a, b, c, d)
        本对象.a = a
        本对象.b = b
        本对象.c = c
        本对象.d = d

    运算符**(n)
        返回 矩阵2x2(本对象.a ** n, 本对象.b ** n, 本对象.c ** n, 本对象.d ** n)

定义 m = 矩阵2x2(1, 2, 3, 4)
定义 m2 = m ** 2
"""
    result = execute(source)
    assert result["m2"].fields["a"] == 1
    assert result["m2"].fields["b"] == 4
    assert result["m2"].fields["c"] == 9
    assert result["m2"].fields["d"] == 16


def test_operator_equals_overload():
    """测试 == 运算符重载"""
    source = """
类型 点
    初始化(x, y)
        本对象.x = x
        本对象.y = y

    运算符==(其他)
        返回 本对象.x == 其他.x 并且 本对象.y == 其他.y

定义 p1 = 点(1, 2)
定义 p2 = 点(1, 2)
定义 p3 = 点(3, 4)

定义 eq1 = p1 == p2
定义 eq2 = p1 == p3
"""
    result = execute(source)
    assert result["eq1"] == True
    assert result["eq2"] == False


def test_operator_not_equals_overload():
    """测试 != 运算符重载"""
    source = """
类型 点
    初始化(x, y)
        本对象.x = x
        本对象.y = y

    运算符!=(其他)
        返回 本对象.x != 其他.x 或者 本对象.y != 其他.y

定义 p1 = 点(1, 2)
定义 p2 = 点(1, 2)
定义 p3 = 点(3, 4)

定义 ne1 = p1 != p2
定义 ne2 = p1 != p3

"""
    result = execute(source)
    assert result["ne1"] == False
    assert result["ne2"] == True


def test_operator_less_than_overload():
    """测试 < 运算符重载"""
    source = """
类型 版本号
    初始化(主, 次, 修)
        本对象.主 = 主
        本对象.次 = 次
        本对象.修 = 修

    运算符<(其他)
        如果 本对象.主 != 其他.主
            返回 本对象.主 < 其他.主
        如果 本对象.次 != 其他.次
            返回 本对象.次 < 其他.次
        返回 本对象.修 < 其他.修

定义 v1 = 版本号(1, 2, 3)
定义 v2 = 版本号(1, 4, 0)
定义 v3 = 版本号(2, 0, 0)

定义 lt1 = v1 < v2
定义 lt2 = v1 < v3
定义 lt3 = v2 < v1
"""
    result = execute(source)
    assert result["lt1"] == True
    assert result["lt2"] == True
    assert result["lt3"] == False


def test_operator_less_equal_overload():
    """测试 <= 运算符重载"""
    source = """
类型 分数
    初始化(分子, 分母)
        本对象.分子 = 分子
        本对象.分母 = 分母

    运算符<=(其他)
        返回 本对象.分子 * 其他.分母 <= 其他.分子 * 本对象.分母

定义 f1 = 分数(1, 2)
定义 f2 = 分数(1, 2)
定义 f3 = 分数(3, 4)

定义 le1 = f1 <= f2
定义 le2 = f1 <= f3
"""
    result = execute(source)
    assert result["le1"] == True
    assert result["le2"] == True


def test_operator_greater_than_overload():
    """测试 > 运算符重载"""
    source = """
类型 温度
    初始化(摄氏)
        本对象.摄氏 = 摄氏

    运算符>(其他)
        返回 本对象.摄氏 > 其他.摄氏

定义 t1 = 温度(25)
定义 t2 = 温度(20)
定义 t3 = 温度(30)

定义 gt1 = t1 > t2
定义 gt2 = t1 > t3
"""
    result = execute(source)
    assert result["gt1"] == True
    assert result["gt2"] == False


def test_operator_greater_equal_overload():
    """测试 >= 运算符重载"""
    source = """
类型 时间
    初始化(秒)
        本对象.秒 = 秒

    运算符>=(其他)
        返回 本对象.秒 >= 其他.秒

定义 time1 = 时间(60)
定义 time2 = 时间(60)
定义 time3 = 时间(30)

定义 ge1 = time1 >= time2
定义 ge2 = time1 >= time3
"""
    result = execute(source)
    assert result["ge1"] == True
    assert result["ge2"] == True


def test_multiple_operators_on_same_class():
    """测试同一类上的多个运算符重载"""
    source = """
类型 向量
    初始化(x, y)
        本对象.x = x
        本对象.y = y

    运算符+(其他)
        返回 向量(本对象.x + 其他.x, 本对象.y + 其他.y)

    运算符*(标量)
        返回 向量(本对象.x * 标量, 本对象.y * 标量)

    运算符==(其他)
        返回 本对象.x == 其他.x 并且 本对象.y == 其他.y

定义 v1 = 向量(2, 3)
定义 v2 = 向量(1, 2)
定义 v3 = v1 + v2
定义 v4 = v3 * 2
定义 eq = v4 == 向量(6, 10)
"""
    result = execute(source)
    assert result["eq"] == True


def test_operator_chaining():
    """测试运算符链式调用"""
    source = """
类型 计数器
    初始化(值)
        本对象.值 = 值

    运算符+(增量)
        返回 计数器(本对象.值 + 增量.值)

定义 c = 计数器(10)
定义 c2 = c + 计数器(5)
定义 c3 = c2 + 计数器(3)
"""
    result = execute(source)
    assert result["c3"].fields["值"] == 18


def test_operator_with_complex_logic():
    """测试运算符重载中的复杂逻辑"""
    source = """
类型 区间
    初始化(最小, 最大)
        本对象.最小 = 最小
        本对象.最大 = 最大

    运算符*(倍数)
        返回 区间(本对象.最小 * 倍数, 本对象.最大 * 倍数)

    运算符==(其他)
        返回 本对象.最小 == 其他.最小 并且 本对象.最大 == 其他.最大

定义 range1 = 区间(1, 10)
定义 range2 = range1 * 2
定义 range3 = 区间(2, 20)

定义 equals = range2 == range3
"""
    result = execute(source)
    assert result["equals"] == True


if __name__ == "__main__":
    test_operator_plus_overload()
    test_operator_minus_overload()
    test_operator_multiply_overload()
    test_operator_divide_overload()
    test_operator_modulo_overload()
    test_operator_power_overload()
    test_operator_equals_overload()
    test_operator_not_equals_overload()
    test_operator_less_than_overload()
    test_operator_less_equal_overload()
    test_operator_greater_than_overload()
    test_operator_greater_equal_overload()
    test_multiple_operators_on_same_class()
    test_operator_chaining()
    test_operator_with_complex_logic()
    print("所有测试通过！")
