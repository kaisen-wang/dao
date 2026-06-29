"""
私有字段访问控制测试
==================

覆盖：私有字段声明、读取控制、写入控制、类内部访问
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


class TestPrivateField:
    """测试私有字段访问控制"""

    def test_private_field_read_denied(self):
        """外部无法读取私有字段"""
        with pytest.raises(运行时错误):
            run(
                '类型 动物\n'
                '    初始化(名字)\n'
                '        本对象.名字 = 名字\n'
                '        私有 本对象.年龄 = 0\n'
                '定义 小猫 = 动物("咪咪")\n'
                '打印(小猫.年龄)\n'
            )

    def test_private_field_write_denied(self):
        """外部无法写入私有字段"""
        with pytest.raises(运行时错误):
            run(
                '类型 动物\n'
                '    初始化(名字)\n'
                '        本对象.名字 = 名字\n'
                '        私有 本对象.年龄 = 0\n'
                '定义 小猫 = 动物("咪咪")\n'
                '小猫.年龄 = 5\n'
            )

    def test_private_field_internal_read(self):
        """类内部可以读取私有字段"""
        output = capture_output(
            '类型 动物\n'
            '    初始化(名字)\n'
            '        本对象.名字 = 名字\n'
            '        私有 本对象.年龄 = 0\n'
            '    函数 获取年龄()\n'
            '        返回 本对象.年龄\n'
            '定义 小猫 = 动物("咪咪")\n'
            '打印(小猫.获取年龄())\n'
        )
        assert output.strip() == "0"

    def test_private_field_internal_write(self):
        """类内部可以写入私有字段"""
        output = capture_output(
            '类型 动物\n'
            '    初始化(名字)\n'
            '        本对象.名字 = 名字\n'
            '        私有 本对象.年龄 = 0\n'
            '    函数 设置年龄(年龄)\n'
            '        本对象.年龄 = 年龄\n'
            '    函数 获取年龄()\n'
            '        返回 本对象.年龄\n'
            '定义 小猫 = 动物("咪咪")\n'
            '小猫.设置年龄(3)\n'
            '打印(小猫.获取年龄())\n'
        )
        assert output.strip() == "3"

    def test_public_field_still_accessible(self):
        """公有字段不受影响"""
        output = capture_output(
            '类型 动物\n'
            '    初始化(名字)\n'
            '        本对象.名字 = 名字\n'
            '        私有 本对象.年龄 = 0\n'
            '定义 小猫 = 动物("咪咪")\n'
            '打印(小猫.名字)\n'
        )
        assert output.strip() == "咪咪"

    def test_private_field_with_getter(self):
        """私有字段配合 getter 使用"""
        output = capture_output(
            '类型 温度计\n'
            '    初始化(摄氏度)\n'
            '        私有 本对象._摄氏度 = 摄氏度\n'
            '    获取 摄氏度()\n'
            '        返回 本对象._摄氏度\n'
            '定义 温度 = 温度计(25)\n'
            '打印(温度.摄氏度)\n'
        )
        assert output.strip() == "25"

    def test_private_field_with_setter(self):
        """私有字段配合 setter 使用"""
        output = capture_output(
            '类型 温度计\n'
            '    初始化(摄氏度)\n'
            '        私有 本对象._摄氏度 = 摄氏度\n'
            '    获取 摄氏度()\n'
            '        返回 本对象._摄氏度\n'
            '    设置 摄氏度(值)\n'
            '        本对象._摄氏度 = 值\n'
            '定义 温度 = 温度计(25)\n'
            '温度.摄氏度 = 100\n'
            '打印(温度.摄氏度)\n'
        )
        assert output.strip() == "100"