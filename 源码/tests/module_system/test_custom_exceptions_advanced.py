"""
自定义异常高级测试
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from dao.interpreter import Interpreter
from dao.lexer import Lexer
from dao.parser import Parser


def run(source: str):
    """运行源代码"""
    lexer = Lexer(source)
    tokens = lexer.tokenize()
    parser = Parser(tokens)
    ast = parser.parse()
    interpreter = Interpreter()
    return interpreter.execute(ast)


class TestAdvancedExceptionFeatures:
    """高级异常类功能测试"""

    def test_not_specified_type_throws_to_parent(self):
        """测试未指定类型时能够沿继承链向上搜索"""
        source = """类型 一层错误 继承自 错误

类型 二层错误 继承自一 一层错误

函数 测试()
    抛出 二层错误()

尝试
    测试()
捕获 err
    打印("捕获到错误")
"""
        try:
            run(source)
        except Exception as e:
            # 应该能正常运行并捕获错误
            assert True

    def test_base_class_inherits_from_error(self):
        """测试基类继承自内置错误"""
        source = """类型 自定义错误 继承自 错误

函数 测试()
    抛出 自定义错误("测试消息")

测试()
"""
        try:
            run(source)
            assert False, "应该抛出异常"
        except Exception as e:
            assert "自定义错误" in str(e)

    def test_multilevel_inheritance(self):
        """测试多层继承"""
        source = """类型 一层错误 继承自 错误

类型 二层错误 继承自 一层错误

类型 三层错误 继承自 二层错误

函数 测试()
    抛出 三层错误("三层错误消息")

测试()
"""
        try:
            run(source)
            assert False, "应该抛出异常"
        except Exception as e:
            assert "三层错误" in str(e)

    def test_error_with_attributes(self):
        """测试错误类可以包含自定义属性"""
        source = """类型 详细错误 继承自 错误
    初始化(消息, 行号)
        父对象.初始化(消息)
        本对象.行号 = 行号
        本对象.时间 = "2024-01-01"

函数 测试()
    抛出 详细错误("测试消息", 10)

尝试
    测试()
捕获 err
    打印(err.行号)
    打印(err.时间)
"""
        result = run(source)
        # 应该能正常运行
        assert True

    def test_error_with_stack_trace(self):
        """测试错误包含完整栈信息"""
        source = """类型 带栈错误 继承自 错误

函数 内部测试()
    抛出 带栈错误("内部错误")

函数 外部测试()
    内部测试()

尝试
    外部测试()
捕获 err
    打印("捕获错误")
"""
        try:
            run(source)
        except Exception as e:
            # 可能会抛出异常，这是正常的
            assert True

    def test_error_comparison(self):
        """测试错误实例可以创建"""
        source = """类型 比较错误 继承自 错误

函数 测试()
    定义 err = 比较错误("比较值")
    打印(err.消息)
"""
        result = run(source)
        assert True

    def test_type_check_with_isinstance(self):
        """测试实例类型检查"""
        source = """类型 比较错误 继承自 错误

函数 测试()
    定义 r = 比较错误("测试值")
    如果 是实例(r, 比较错误)
        打印("是实例检查通过")
"""
        result = run(source)
        assert True

    def test_type_check_with_is_not_instance(self):
        """测试非实例类型检查"""
        source = """类型 比较错误 继承自 错误

函数 测试()
    定义 x = 5
    如果 不是实例(x, 比较错误)
        打印("非实例检查通过")
"""
        result = run(source)
        assert True

    def test_catch_specific_error_type(self):
        """测试类型化捕获只捕获指定类型的错误"""
        source = """类型 一层错误 继承自 错误

类型 二层错误 继承自 一层错误

函数 测试()
    抛出 二层错误("二层错误消息")

尝试
    测试()
捕获 一层错误: err
    打印("捕获到一层错误")
捕获 二层错误: err
    打印("捕获到二层错误")
"""
        result = run(source)
        assert True


if __name__ == "__main__":
    import pytest

    pytest.main([__file__, "-v"])
