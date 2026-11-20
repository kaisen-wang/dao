"""特征默认方法测试：默认实现可被继承、同名方法覆盖、抽象方法仍强制实现。"""

import io
import os
import sys
from contextlib import redirect_stdout

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from dao.errors import 类型错误
from dao.interpreter import Interpreter
from dao.lexer import Lexer
from dao.parser import Parser


def run(source: str) -> str:
    """运行源代码并捕获输出"""
    tokens = Lexer(source).tokenize()
    ast = Parser(tokens).parse()
    interpreter = Interpreter()

    output = io.StringIO()
    with redirect_stdout(output):
        interpreter.execute(ast)

    return output.getvalue()


def test_default_method_inherited_when_not_defined():
    """实现特征但未定义方法时，调用特征的默认实现"""
    source = """特征 F
    函数 说()
        返回 "trait默认"

类型 B
    实现 F

定义 b = B()
打印(b.说())
"""
    result = run(source)
    assert "trait默认" in result


def test_override_default_method():
    """类型自定义同名方法时优先于特征默认实现"""
    source = """特征 F
    函数 说()
        返回 "trait默认"

类型 A
    实现 F
    函数 说()
        返回 "A自己的"

定义 a = A()
打印(a.说())
"""
    result = run(source)
    assert "A自己的" in result
    assert "trait默认" not in result


def test_multiple_traits_with_abstract_type_no_regression():
    """多特征默认方法与抽象类型（父类抽象方法由子类实现）混用不回归"""
    source = """特征 可绘制
    函数 绘制()
        返回 "默认绘制"

特征 可命名
    函数 名称()
        返回 "默认名称"

抽象 类型 形状
    抽象 面积()

类型 圆形 继承自 形状
    实现 可绘制, 可命名
    函数 面积()
        返回 100

定义 c = 圆形()
打印(`{c.绘制()}|{c.名称()}|{c.面积()}`)
"""
    result = run(source)
    assert "默认绘制|默认名称|100" in result


def test_abstract_trait_method_still_required():
    """特征中的抽象方法（无默认体）仍强制由实现类型覆盖"""
    source = """特征 可发声
    抽象 发声()

类型 狗
    实现 可发声
"""
    with pytest.raises(类型错误) as exc_info:
        run(source)
    message = str(exc_info.value)
    assert "狗" in message
    assert "可发声" in message
    assert "发声" in message
    assert "必须实现" in message


def test_default_and_abstract_trait_methods_coexist():
    """同一特征中默认方法与抽象方法共存时各自语义正确"""
    source = """特征 混合
    函数 默认方法()
        返回 "默认"
    抽象 必须实现()

类型 T
    实现 混合
    函数 必须实现()
        返回 "已实现"

定义 t = T()
打印(`{t.默认方法()}|{t.必须实现()}`)
"""
    result = run(source)
    assert "默认|已实现" in result
