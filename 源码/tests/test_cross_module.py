"""
跨模块集成测试
============

测试多范式协同工作：OOP + 逻辑 + 宏 + 并发 + FP。
"""

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

import pytest
from dao.lexer import Lexer
from dao.parser import Parser
from dao.interpreter import Interpreter


def run(source: str) -> object:
    tokens = Lexer(source).tokenize()
    ast = Parser(tokens).parse()
    interpreter = Interpreter()
    return interpreter.execute(ast)


def capture_output(source: str) -> str:
    import io
    from contextlib import redirect_stdout
    f = io.StringIO()
    with redirect_stdout(f):
        run(source)
    return f.getvalue()


class TestOOPAndLogic:
    """OOP + 逻辑编程集成"""

    def test_class_method_uses_logic_query(self):
        source = """
逻辑 家族
    事实: 父母("张三", "小明")
    事实: 父母("李四", "小明")

类型 查询工具
    初始化()
        本对象.知识库 = 家族

    函数 找父母(孩子)
        定义 结果 = 查询(本对象.知识库, 父母(?p, 孩子))
        返回 结果

定义 工具 = 查询工具()
定义 父母 = 工具.找父母("小明")
"""
        run(source)


class TestLogicAndMacro:
    """逻辑编程 + 宏系统集成"""

    def test_macro_before_logic_block(self):
        """宏定义在逻辑块之前，宏不直接展开在逻辑块内"""
        source = """
定义宏 双倍(x)
    返回 引述 $x * 2

逻辑 数学
    事实: 数值(1)
    事实: 数值(2)

定义 结果 = 查询(数学, 数值(?x))
"""
        run(source)


class TestOOPAndMacro:
    """OOP + 宏系统集成"""

    def test_macro_expands_with_oop_value(self):
        """宏展开生成 OOP 相关代码"""
        source = """
定义宏 创建实例(类型名, 参数)
    返回 引述 $类型名($参数)

类型 用户
    初始化(姓名)
        本对象.姓名 = 姓名
    函数 问好()
        返回 "你好，" + 本对象.姓名

定义 人 = !创建实例(用户, "张三")
定义 问候 = 人.问好()
"""
        run(source)


class TestFPAndLogic:
    """函数式 + 逻辑编程集成"""

    def test_hof_with_logic(self):
        source = """
逻辑 数字
    事实: 值(1)
    事实: 值(2)
    事实: 值(3)

定义 结果列表 = 查询(数字, 值(?x))
打印(结果列表)
"""
        capture_output(source)


class TestOOPAndFP:
    """OOP + 函数式集成"""

    def test_class_with_hof_method(self):
        source = """
定义 双倍 = 映射([1, 2, 3], 函数(x) => x * 2)

类型 容器
    初始化(元素列表)
        本对象.元素 = 元素列表
    函数 获取元素()
        返回 本对象.元素

定义 容器实例 = 容器([1, 2, 3, 4, 5])
定义 元素 = 容器实例.获取元素()
"""
        run(source)


class TestMacroWithControlFlow:
    """宏 + 控制流集成"""

    def test_macro_generates_conditional(self):
        source = """
定义宏 如果非空(值, 操作)
    返回 引述
        如果 $值 != 空
            $操作

设 数据 = [1, 2, 3]
!如果非空(数据)
    打印("数据非空")
"""
        capture_output(source)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
