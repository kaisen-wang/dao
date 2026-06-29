"""
受保护访问控制测试
================

覆盖：受保护方法、受保护字段、子类访问、外部拒绝
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

import pytest
from dao.lexer import Lexer
from dao.parser import Parser
from dao.interpreter import Interpreter
from dao.errors import 运行时错误


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


class TestProtectedMethod:
    """测试受保护方法访问控制"""

    def test_protected_method_external_denied(self):
        """外部无法访问受保护方法"""
        with pytest.raises(运行时错误):
            run(
                '类型 动物\n'
                '    初始化(名字)\n'
                '        本对象.名字 = 名字\n'
                '    受保护 函数 休息()\n'
                '        返回 "休息中"\n'
                '定义 小猫 = 动物("咪咪")\n'
                '小猫.休息()\n'
            )

    def test_protected_method_internal_access(self):
        """类内部可以访问受保护方法"""
        output = capture_output(
            '类型 动物\n'
            '    初始化(名字)\n'
            '        本对象.名字 = 名字\n'
                '    受保护 函数 休息()\n'
                '        返回 "休息中"\n'
            '    函数 放松()\n'
            '        返回 本对象.休息()\n'
            '定义 小猫 = 动物("咪咪")\n'
            '打印(小猫.放松())\n'
        )
        assert output.strip() == "休息中"

    def test_protected_method_subclass_access(self):
        """子类可以访问受保护方法"""
        output = capture_output(
            '类型 动物\n'
            '    初始化(名字)\n'
            '        本对象.名字 = 名字\n'
            '    受保护 函数 休息()\n'
            '        返回 "休息中"\n'
            '类型 猫 继承自 动物\n'
            '    初始化(名字)\n'
            '        父对象.初始化(名字)\n'
            '    函数 打盹()\n'
            '        返回 本对象.休息()\n'
            '定义 小猫 = 猫("咪咪")\n'
            '打印(小猫.打盹())\n'
        )
        assert output.strip() == "休息中"


class TestProtectedField:
    """测试受保护字段访问控制"""

    def test_protected_field_read_denied(self):
        """外部无法读取受保护字段"""
        with pytest.raises(运行时错误):
            run(
                '类型 动物\n'
                '    初始化(名字)\n'
                '        本对象.名字 = 名字\n'
                '        受保护 本对象.年龄 = 0\n'
                '定义 小猫 = 动物("咪咪")\n'
                '打印(小猫.年龄)\n'
            )

    def test_protected_field_write_denied(self):
        """外部无法写入受保护字段"""
        with pytest.raises(运行时错误):
            run(
                '类型 动物\n'
                '    初始化(名字)\n'
                '        本对象.名字 = 名字\n'
                '        受保护 本对象.年龄 = 0\n'
                '定义 小猫 = 动物("咪咪")\n'
                '小猫.年龄 = 5\n'
            )

    def test_protected_field_subclass_read(self):
        """子类可以读取受保护字段"""
        output = capture_output(
            '类型 动物\n'
            '    初始化(名字)\n'
            '        本对象.名字 = 名字\n'
            '        受保护 本对象.年龄 = 0\n'
            '类型 猫 继承自 动物\n'
            '    初始化(名字)\n'
            '        父对象.初始化(名字)\n'
            '    函数 获取年龄()\n'
            '        返回 本对象.年龄\n'
            '定义 小猫 = 猫("咪咪")\n'
            '打印(小猫.获取年龄())\n'
        )
        assert output.strip() == "0"

    def test_protected_field_subclass_write(self):
        """子类可以写入受保护字段"""
        output = capture_output(
            '类型 动物\n'
            '    初始化(名字)\n'
            '        本对象.名字 = 名字\n'
            '        受保护 本对象.年龄 = 0\n'
            '类型 猫 继承自 动物\n'
            '    初始化(名字)\n'
            '        父对象.初始化(名字)\n'
            '    函数 设置年龄(年龄)\n'
            '        本对象.年龄 = 年龄\n'
            '    函数 获取年龄()\n'
            '        返回 本对象.年龄\n'
            '定义 小猫 = 猫("咪咪")\n'
            '小猫.设置年龄(3)\n'
            '打印(小猫.获取年龄())\n'
        )
        assert output.strip() == "3"