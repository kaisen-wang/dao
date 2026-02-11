"""
特征 (Trait) 系统测试
"""

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from dao.lexer import Lexer
from dao.parser import Parser
from dao.interpreter import Interpreter
import io
from contextlib import redirect_stdout


def run(source: str) -> str:
    """运行源代码并捕获输出"""
    lexer = Lexer(source)
    tokens = lexer.tokenize()
    parser = Parser(tokens)
    ast = parser.parse()
    interpreter = Interpreter()

    output = io.StringIO()
    with redirect_stdout(output):
        interpreter.execute(ast)

    return output.getvalue()


class TestTraitBasics:
    def test_trait_decl(self):
        """测试特征声明"""
        source = """特征 可绘制
    函数 draw()
        打印("Drawing")
"""
        run(source)

    def test_class_implements_trait(self):
        """测试类实现特征"""
        source = """特征 可绘制
    函数 draw()
        打印("Default drawing")

类型 圆形
    实现 可绘制
    函数 draw()
        打印("Drawing a circle")

定义 c = 圆形()
c.draw()
"""
        result = run(source)
        assert "Drawing a circle" in result

    def test_trait_multiple_methods(self):
        """测试特征包含多个方法"""
        source = """特征 形状
    函数 area()
        返回 0
    函数 perimeter()
        返回 0

类型 矩形
    实现 形状
    函数 初始化(宽度, 高度)
        定义 width = 宽度
        定义 height = 高度
    函数 area()
        返回 本对象.width * 本对象.height
    函数 perimeter()
        返回 2 * (本对象.width + 本对象.height)

定义 r = = 矩形(5, 3)
打印(r.area())
打印(r.perimeter())
"""
        result = run(source)
        assert "15" in result
        assert "16" in result

    def test_class_implements_multiple_traits(self):
        """测试类实现多个特征"""
        source = """特征 可绘制
    函数 draw()
        打印("Default drawing")
特征 可缩放
    函数 scale(比例)
        打印("Default scaling")

类型 圆形
    实现 可绘制, 可缩放
    函数 draw()
        打印("Drawing a circle")
    函数 scale(比例)
        打印("Scaling")

定义 c = 圆形()
c.draw()
c.scale(2.0)
"""
        result = run(source)
        assert "Drawing a circle" in result
        assert "Scaling" in result

    def test_trait_with_inheritance(self):
        """测试特征与继承结合"""
        source = """特征 可绘制
    函数 draw()
        打印("Default drawing")

类型 图形
    实现 可绘制
    函数 draw()
        打印("Drawing generic shape")

类型 圆形 继承自 图形
    函数 draw()
        打印("Drawing a circle")

定义 s = 图形()
定义 c = 圆形()
s.draw()
c.draw()
"""
        result = run(source)
        assert "Drawing generic shape" in result
        assert "Drawing a circle" in result

    def test_trait_implementation_missing_method(self):
        """测试类未实现特征方法时的错误"""
        source = """特征 可绘制
    函数 draw()
        打印("Default drawing")

类型 圆形
    实现 可绘制
"""
        try:
            run(source)
            assert False, "应该抛出类型错误"
        except Exception as e:
            assert "draw" in str(e) or "可绘制" in str(e)

    def test_trait_not_found(self):
        """测试引用不存在的特征"""
        source = """类型 圆形
    实现 不存在的特征
    函数 draw()
        打印("Drawing")
"""
        try:
            run(source)
            assert False, "应该抛出类型错误"
        except Exception as e:
            assert "不存在的特征" in str(e) or "不是一个特征" in str(e)

    def test_trait_static_methods(self):
        """测试特征中的静态方法"""
        source = """特征 可序列化
    静态 函数 from_json(字符串)
        打印("Parsing: " + 字符串)

类型 用户
    实现 可序列化
    静态 函数 from_json(字符串)
        打印("User from: " + 字符串)

用户.from_json('{"name": "张三"}')
"""
        result = run(source)
        assert "User from:" in result


if __name__ == "__main__":
    import pytest

    pytest.main([__file__, "-v"])
