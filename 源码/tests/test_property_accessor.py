"""
属性访问器测试
"""

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from dao.lexer import Lexer
from dao.parser import Parser
from dao.interpreter import Interpreter


def run(source: str):
    """运行源代码"""
    import sys

    # 捕获输出
    from io import StringIO
    old_stdout = sys.stdout
    sys.stdout = StringIO()

    try:
        lexer = Lexer(source)
        tokens = lexer.tokenize()
        parser = Parser(tokens)
        ast = parser.parse()
        interpreter = Interpreter()
        interpreter.execute(ast)
        return sys.stdout.getvalue()
    finally:
        sys.stdout = old_stdout


class TestPropertyGetter:
    """属性 Getter 测试"""

    def test_simple_getter(self):
        """测试简单的 getter"""
        source = """
类型 Person
    初始化(姓名)
        本对象._姓名 = 姓名

    获取 姓名()
        返回 本对象._姓名

定义 p = Person("张三")
打印(p.姓名)
"""
        result = run(source)
        assert "张三" in result

    def test_getter_with_transformation(self):
        """测试带转换的 getter"""
        source = """
类型 温度
    初始化(摄氏度)
        本对象._摄氏度 = 摄氏度

    获取 华氏度()
        返回 本对象._摄氏度 * 9 / 5 + 32

定义 t = 温度(0)
打印(t.华氏度)
"""
        result = run(source)
        assert "32" in result

    def test_readonly_property(self):
        """测试只读属性"""
        source = """
类型 只读
    初始化(值)
        本对象._值 = 值

    获取 数据()
        返回 本对象._值

定义 obj = 只读(42)
打印(obj.数据)
"""
        result = run(source)
        assert "42" in result


class TestPropertySetter:
    """属性 Setter 测试"""

    def test_simple_setter(self):
        """测试简单的 setter"""
        source = """
类型 计数器
    初始化()
        本对象._值 = 0

    获取 值()
        返回 本对象._值

    设置 值(v)
        本对象._值 = v

定义 c = 计数器()
c.值 = 10
打印(c.值)
"""
        result = run(source)
        assert "10" in result

    def test_setter_with_validation(self):
        """测试带验证的 setter"""
        source = """
类型 年龄
    初始化()
        本对象._值 = 0

    获取 值()
        返回 本对象._值

    设置 值(v)
        本对象._值 = v

定义 a = 年龄()
a.值 = 25
打印(a.值)
"""
        result = run(source)
        assert "25" in result

    def test_setter_side_effect(self):
        """测试带副作用的 setter"""
        source = """
类型 状态
    初始化()
        本对象._值 = 假
        本对象.改变次数 = 0

    获取 激活()
        返回 本对象._值

    设置 激活(v)
        本对象._值 = v
        本对象.改变次数 = 本对象.改变次数 + 1

定义 s = 状态()
s.激活 = 真
s.激活 = 假
s.激活 = 真
打印(s.改变次数)
"""
        result = run(source)
        assert "3" in result


class TestPropertyGetSetBoth:
    """Getter 和 Setter 组合测试"""

    def test_getter_setter_pair(self):
        """测试 getter/setter 对"""
        source = """
类型 分数
    初始化()
        本对象._值 = 0

    获取 值()
        返回 本对象._值

    设置 值(v)
        如果 v < 0
            本对象._值 = 0
        否则 如果 v > 100
            本对象._值 = 100
        否则
            本对象._值 = v

定义 s = 分数()
s.值 = 150
打印(s.值)
s.值 = -10
打印(s.值)
s.值 = 75
打印(s.值)
"""
        result = run(source)
        assert "100" in result
        assert "0" in result
        assert "75" in result

    def test_computed_property(self):
        """测试计算属性（getter 动态计算，setter 解析）"""
        source = """
类型 矩形
    初始化(宽, 高)
        本对象.宽 = 宽
        本对象.高 = 高

    获取 面积()
        返回 本对象.宽 * 本对象.高

    获取 周长()
        返回 2 * (本对象.宽 + 本对象.高)

定义 r = 矩形(5, 3)
打印(r.面积)
打印(r.周长)
"""
        result = run(source)
        assert "15" in result
        assert "16" in result


class TestPropertyInheritance:
    """属性访问器继承测试"""

    def test_inherit_getter(self):
        """测试继承 getter"""
        source = """
类型 基类
    初始化()
        本对象._值 = 10

    获取 值()
        返回 本对象._值 * 2

类型 子类 继承自 基类
    初始化()
        父对象.初始化()

定义 obj = 子类()
打印(obj.值)
"""
        result = run(source)
        assert "20" in result

    def test_override_getter(self):
        """测试重写 getter"""
        source = """
类型 基类
    初始化()
        本对象._值 = 10

    获取 值()
        返回 本对象._值 * 2

类型 子类 继承自 基类
    初始化()
        父对象.初始化()

    获取 值()
        返回 本对象._值 * 3

定义 obj = 子类()
打印(obj.值)
"""
        result = run(source)
        assert "30" in result


if __name__ == "__main__":
    import pytest

    pytest.main([__file__, "-v"])
