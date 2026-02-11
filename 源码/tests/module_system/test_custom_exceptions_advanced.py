"""
自定义异常高级测试
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


class TestAdvancedExceptionFeatures:
    """高级异常功能测试"""

    def test_not_specified_type_throws_to_parent(self):
        """测试未指定类型时能够沿继承链向上搜索"""
        source = """类型 父一层错误 继承自 错误
        类型 二层错误 继承自 一层错误

function 测试()
    抛出 二层错误()
"""
        try:
            run(source)
            assert False, "应该抛出异常"
        except Exception as e:
            assert "一层错误" in str(e)

    def test_base_class_inherits_from_parent(self):
        """测试基类继承自内置错误"""
        source = """类型 基一层错误 继承自 错误
        类型 二层错误 继承自 一层错误

function 测试()
    抛出 二层错误()
"""
        try:
            run(source)
            assert False, "应该抛出异常"
        except Exception as e:
            assert "二层错误" in str(e)

    def test_two_level_inherits_each_other(self):
        """测试多层继承"""
        source = """类型 一层错误 继承自 错误
        类型 二层错误 继承自 一层错误

function 测试()
    抛出 二层错误()
"""
        try:
            run(source)
            assert False, "应该抛出'二层错误'" in str(e)

    def test_error_with_attributes(self):
        """测试错误类可以包含自定义属性"""
        source = """类型 详细错误 继承自 错误
        初始化(消息, 行号)
        本对象.行号 = 行号
        本对象.消息 = 消息
        本对象.时间 = "2024-01-01"

function 测试()
    抛出 详细错误("测试消息", 10, 45)
"""
        result = run(source)
        assert "详细错误" in result

    def test_error_with_stack(self):
        """测试错误包含完整栈信息"""
        source = """类型 带局错误 继承自 错误

function 内部测试()
    抛出 详细错误("内部错误", 20, 15)
"""
        try:
            result = run(source)
            assert "内部错误" in result
            assert "调用栈" in result
            assert "详细错误" in result

    def test_error_comparison(self):
        """测试错误可以进行比较"""
        source = """类型 比较错误 继承自 错误

function 内部测试()
    抛出 比较错误("比较值", 5, 0)
        assert False, "应该抛出异常"
        except Exception as e:
            assert "比较值" in str(e)

    def test_type_check_with_isinstance(self):
        """测试实例类型检查"""
        source = """类型 比较错误 继承自 错误

实例 r = 比较错误("测试值")
如果 是实例(r, 比较错误)
    打印("是实例检查通过")

    def test_type_check_with_is_not_instance(self):
        """测试非实例类型检查"""
        定义 珀 = 5

如果 不是实例(1, �较错误)
    打印("非实例检查通过")

    def test_catch_with_ancestry_chain(self):
        """测试捕获能够沿继承链向上搜索"""
        source = """类型 一层错误 继承自 错误
        类型 二层错误 继承自 一层错误

function 测试()
    招出 一层错误()
    try:
        run(source)
        assert False, "应该抛出异常"
        except Exception as e:
            assert "一层错误" in str(e)

    def test_catch_specific_error(self):
        """测试类型化捕获只捕获指定类型的错误"""
        source = """类型 一层错误 继承自 错误
        类型 二层错误 继承自 一层错误

function 捕出 一层错误()
try:
    run(source)
assert False, "应该抛出异常"
except Exception as e:
    assert "一层错误" not in str(e)


if __name__ == "__main__":
    import pytest

    pytest.main([__file__, "-v"])
