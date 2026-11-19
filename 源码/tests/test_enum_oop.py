"""
枚举与 OOP 深度集成测试
======================

覆盖：枚举实现特征、枚举方法定义、枚举值相等比较。
"""

import io
import os
import sys
from contextlib import redirect_stdout

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest

from dao.interpreter import Interpreter
from dao.lexer import Lexer
from dao.parser import Parser


def eval_env(source: str):
    tokens = Lexer(source).tokenize()
    ast = Parser(tokens).parse()
    interpreter = Interpreter()
    interpreter.execute(ast)
    return interpreter.global_env


def run(source: str) -> str:
    """执行源码并返回标准输出"""
    tokens = Lexer(source).tokenize()
    ast = Parser(tokens).parse()
    interpreter = Interpreter()
    f = io.StringIO()
    with redirect_stdout(f):
        interpreter.execute(ast)
    return f.getvalue()


class TestEnumImplementsTrait:
    """枚举实现特征"""

    def test_inline_implements_trait_default_method(self):
        """同行写法：枚举 颜色 实现 可序列化，特征方法作为默认实现"""
        source = """特征 可序列化
    函数 序列化()
        返回 "trait-default"

枚举 颜色 实现 可序列化
    红
    绿

打印(颜色.红.序列化())
"""
        assert "trait-default" in run(source)

    def test_body_implements_multiple_traits(self):
        """缩进块写法：枚举体内首行实现多个特征"""
        source = """特征 可序列化
    函数 序列化()
        返回 "json"
特征 可比较
    函数 说明()
        返回 "可比较"

枚举 方向
    实现 可序列化, 可比较
    东
    西

打印(方向.东.序列化())
打印(方向.西.说明())
"""
        output = run(source)
        assert "json" in output
        assert "可比较" in output

    def test_enum_method_overrides_trait_default(self):
        """枚举自定义方法覆盖特征默认方法"""
        source = """特征 可序列化
    函数 序列化()
        返回 "trait-default"

枚举 形状 实现 可序列化
    圆形
    函数 序列化()
        返回 "enum-json"

打印(形状.圆形.序列化())
"""
        output = run(source)
        assert "enum-json" in output
        assert "trait-default" not in output

    def test_trait_static_method_on_enum_type(self):
        """特征静态方法可通过枚举类型访问"""
        source = """特征 工具
    静态 函数 创建()
        返回 "static-ok"

枚举 颜色 实现 工具
    红

打印(颜色.创建())
"""
        assert "static-ok" in run(source)

    def test_unknown_trait_error_is_chinese(self):
        """实现不存在的特征时抛出中文错误"""
        source = """枚举 颜色 实现 不存在
    红
打印(颜色.红)
"""
        with pytest.raises(Exception) as exc:
            run(source)
        assert "不是一个特征" in str(exc.value) or "不存在" in str(exc.value)


class TestEnumMethods:
    """枚举方法定义"""

    def test_instance_method_calls_self(self):
        """实例方法可通过 本对象 访问变体名"""
        source = """枚举 颜色
    红
    绿
    函数 描述()
        返回 "颜色-" + 本对象.变体名

打印(颜色.红.描述())
"""
        assert "颜色-红" in run(source)

    def test_method_accesses_associated_data_by_param_name(self):
        """方法可按变体参数名访问关联值"""
        source = """枚举 形状
    圆形(半径)
    矩形(宽, 高)
    函数 面积()
        如果 本对象.变体名 == "圆形"
            返回 3 * 本对象.半径 * 本对象.半径
        返回 本对象.宽 * 本对象.高

定义 c = 形状.圆形(2)
定义 r = 形状.矩形(3, 5)
打印(c.面积())
打印(r.面积())
"""
        output = run(source)
        assert "12" in output
        assert "15" in output

    def test_method_with_arguments(self):
        """枚举方法可带参数"""
        source = """枚举 颜色
    红
    绿
    函数 拼接(后缀)
        返回 本对象.变体名 + 后缀

打印(颜色.绿.拼接("色"))
"""
        assert "绿色" in run(source)

    def test_static_method_on_enum_type(self):
        """枚举体内可定义静态方法"""
        source = """枚举 颜色
    红
    绿
    静态 函数 数量()
        返回 2

打印(颜色.数量())
"""
        assert "2" in run(source)

    def test_unknown_member_error_is_chinese(self):
        """访问不存在的成员时抛出中文错误"""
        source = """枚举 颜色
    红
打印(颜色.红.不存在)
"""
        with pytest.raises(Exception) as exc:
            run(source)
        assert "没有属性或方法" in str(exc.value) or "不存在" in str(exc.value)


class TestEnumEquality:
    """枚举值相等比较"""

    def test_same_variant_same_data_is_equal(self):
        """同一枚举同变体且关联值相等则为真"""
        source = """枚举 形状
    圆形(半径)
定义 a = 形状.圆形(5)
定义 b = 形状.圆形(5)
打印(a == b)
"""
        assert "真" in run(source)

    def test_different_data_is_not_equal(self):
        """关联值不同则不相等"""
        source = """枚举 形状
    圆形(半径)
打印(形状.圆形(5) != 形状.圆形(6))
"""
        assert "真" in run(source)

    def test_different_variant_is_not_equal(self):
        """同枚举不同变体不相等"""
        source = """枚举 形状
    圆形(半径)
    矩形(半径)
打印(形状.圆形(5) == 形状.矩形(5))
"""
        assert "假" in run(source)

    def test_different_enum_same_variant_name_is_not_equal(self):
        """不同枚举即使变体名相同也不相等"""
        source = """枚举 甲
    红
枚举 乙
    红
打印(甲.红 == 乙.红)
"""
        assert "假" in run(source)

    def test_simple_variant_equality(self):
        """无关联值的简单枚举比较"""
        source = """枚举 方向
    东
    西
打印(方向.东 == 方向.东)
打印(方向.东 != 方向.西)
"""
        assert "真" in run(source)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
