"""
自定义异常和类型化捕获测试
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


class TestCustomExceptions:
    """测试自定义异常类型"""

    def test_define_error_class(self):
        """测试定义错误类"""
        source = """类型 业务错误 继承自 错误"""
        result = run(source)
        # 不应该抛出异常
        assert result is None

    def test_throw_custom_error(self):
        """测试抛出自定义错误"""
        source = """类型 业务错误 继承自 错误

函数 检查权限(用户)
    如果 用户 != "admin"
        抛出 业务错误("没有权限")

定义 用户 = "guest"
检查权限(用户)
"""
        try:
            run(source)
            assert False, "应该抛出异常"
        except Exception as e:
            assert "没有权限" in str(e)

    def test_catch_custom_error(self):
        """测试捕获自定义错误"""
        source = """类型 业务错误 继承自 错误

函数 可能出错()
    抛出 业务错误("发生错误")

尝试
    可能出错()
捕获 异常: err
    打印(err.信息)
"""
        result = run(source)
        # 应该打印错误信息
        assert result is None  # 实际输出在 stdout

    def test_typed_catch(self):
        """测试类型化捕获"""
        source = """类型 业务错误 继承自 错误
类型 系统错误 继承自 错误

函数 抛出业务()
    抛出 业务错误("业务错误")

函数 抛出系统()
    抛出 系统错误("系统错误")

尝试
    抛出业务()
捕获 异常: err
    打印("捕获了所有异常")

尝试
    抛出系统()
捕获 异常: 业务错误
    打印("捕获了业务错误")
"""
        try:
            run(source)
            assert False, "应该抛出异常"
        except Exception as e:
            # 系统错误不应该被业务错误捕获
            assert "系统错误" in str(e)

    def test_catch_specific_error_type(self):
        """测试只捕获特定类型的错误"""
        source = """类型 业务错误 继承自 错误
类型 系统错误 继承自 错误

函数 测试(类型)
    如果 类型 == "业务"
        抛出 业务错误("业务错误")
    否则
        抛出 系统错误("系统错误")

尝试
    测试("系统")
捕获 异常: 业务错误
    打印("捕获了业务错误")
捕获 异常: 系统错误
    打印("捕获了系统错误")
"""
        result = run(source)
        # 不应该抛出异常，因为系统错误被捕获了
        assert result is None

    def test_error_with_message(self):
        """测试带消息。自定义错误"""
        source = """类型 自定义错误 继承自 错误

函数 函数()
    抛出 自定义错误("这是一个错误")

尝试
    函数()
捕获 异常: err
    打印(err.信息)
"""
        result = run(source)
        assert result is None

    def test_multiple_error_types(self):
        """测试多个错误类型层次"""
        source = """类型 基础错误 继承自 错误
类型 验证错误 继承自 基础错误
类型 网络错误 继承自 基础错误

函数 验证数据()
    抛出 验证错误("数据验证失败")

尝试
    验证数据()
捕获 异常: 网络错误
    打印("网络错误")
捕获 异常: 验证错误
    打印("验证错误")
捕获 异常: 基础错误
    打印("基础错误")
"""
        result = run(source)
        assert result is None


if __name__ == "__main__":
    import pytest
    pytest.main([__file__, "-v"])
