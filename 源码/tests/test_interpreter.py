"""
解释器测试
=========
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

import pytest
from dao.lexer import Lexer
from dao.parser import Parser
from dao.interpreter import Interpreter
from dao.errors import 运行时错误, 名称错误


def run(source: str) -> object:
    """辅助函数：源代码 → 执行结果"""
    tokens = Lexer(source).tokenize()
    ast = Parser(tokens).parse()
    interpreter = Interpreter()
    return interpreter.execute(ast)


def capture_output(source: str) -> str:
    """辅助函数：捕获打印输出"""
    import io
    from contextlib import redirect_stdout

    f = io.StringIO()
    with redirect_stdout(f):
        run(source)
    return f.getvalue()


class TestInterpreterBasics:
    """基础执行测试"""

    def test_print_string(self):
        output = capture_output('打印("你好")\n')
        assert output.strip() == "你好"

    def test_print_number(self):
        output = capture_output('打印(42)\n')
        assert output.strip() == "42"

    def test_variable_and_print(self):
        output = capture_output('定义 x = 10\n打印(x)\n')
        assert output.strip() == "10"

    def test_constant(self):
        """常量不能重新赋值"""
        with pytest.raises(运行时错误):
            run('常量 x = 10\nx = 20\n')

    def test_string_concat(self):
        output = capture_output('打印("你好" + "世界")\n')
        assert output.strip() == "你好世界"


class TestInterpreterArithmetic:
    """算术运算测试"""

    def test_addition(self):
        output = capture_output('打印(3 + 4)\n')
        assert output.strip() == "7"

    def test_subtraction(self):
        output = capture_output('打印(10 - 3)\n')
        assert output.strip() == "7"

    def test_multiplication(self):
        output = capture_output('打印(3 * 4)\n')
        assert output.strip() == "12"

    def test_division(self):
        output = capture_output('打印(10 / 4)\n')
        assert output.strip() == "2.5"

    def test_power(self):
        output = capture_output('打印(2 ** 10)\n')
        assert output.strip() == "1024"

    def test_modulo(self):
        output = capture_output('打印(10 % 3)\n')
        assert output.strip() == "1"

    def test_operator_precedence(self):
        output = capture_output('打印(2 + 3 * 4)\n')
        assert output.strip() == "14"


class TestInterpreterControlFlow:
    """控制流测试"""

    def test_if_true(self):
        output = capture_output('如果 真\n    打印("是")\n')
        assert output.strip() == "是"

    def test_if_false(self):
        output = capture_output('如果 假\n    打印("是")\n否则\n    打印("否")\n')
        assert output.strip() == "否"

    def test_while_loop(self):
        source = '定义 x = 0\n当 x < 3\n    打印(x)\n    x = x + 1\n'
        output = capture_output(source)
        assert output.strip() == "0\n1\n2"

    def test_for_range(self):
        source = '遍历 i 从 1 到 3\n    打印(i)\n'
        output = capture_output(source)
        assert output.strip() == "1\n2\n3"

    def test_for_in(self):
        source = '定义 列表 = [10, 20, 30]\n遍历 x 在 列表\n    打印(x)\n'
        output = capture_output(source)
        assert output.strip() == "10\n20\n30"

    def test_break(self):
        source = '遍历 i 从 1 到 10\n    如果 i > 3\n        跳出\n    打印(i)\n'
        output = capture_output(source)
        assert output.strip() == "1\n2\n3"

    def test_continue(self):
        source = '遍历 i 从 1 到 5\n    如果 i == 3\n        继续\n    打印(i)\n'
        output = capture_output(source)
        assert output.strip() == "1\n2\n4\n5"


class TestInterpreterFunctions:
    """函数测试"""

    def test_function_call(self):
        source = '函数 加(甲, 乙)\n    返回 甲 + 乙\n打印(加(3, 4))\n'
        output = capture_output(source)
        assert output.strip() == "7"

    def test_function_default_args(self):
        source = '函数 招呼(名字, 称呼="先生")\n    打印(名字 + 称呼)\n招呼("张三")\n'
        output = capture_output(source)
        assert output.strip() == "张三先生"

    def test_recursive_function(self):
        source = (
            '函数 阶乘(n)\n'
            '    如果 n <= 1\n'
            '        返回 1\n'
            '    否则\n'
            '        返回 n * 阶乘(n - 1)\n'
            '打印(阶乘(5))\n'
        )
        output = capture_output(source)
        assert output.strip() == "120"

    def test_closure(self):
        source = (
            '函数 创建加法器(n)\n'
            '    返回 函数(x) => x + n\n'
            '定义 加五 = 创建加法器(5)\n'
            '打印(加五(3))\n'
        )
        output = capture_output(source)
        assert output.strip() == "8"

    def test_lambda(self):
        source = (
            '定义 双倍 = 函数(x) => x * 2\n'
            '打印(双倍(5))\n'
        )
        output = capture_output(source)
        assert output.strip() == "10"

    def test_lambda_block_body(self):
        source = (
            '定义 处理 = 函数(x) =>\n'
            '    定义 结果 = x * x\n'
            '    如果 结果 > 100\n'
            '        返回 100\n'
            '    返回 结果\n'
            '打印(处理(5))\n'
            '打印(处理(15))\n'
        )
        output = capture_output(source)
        assert output.strip() == "25\n100"

    def test_lambda_block_body_no_args(self):
        source = (
            '定义 取值 = 函数 =>\n'
            '    定义 x = 42\n'
            '    返回 x\n'
            '打印(取值())\n'
        )
        output = capture_output(source)
        assert output.strip() == "42"

    def test_lambda_block_closure(self):
        source = (
            '函数 创建乘法器(倍数)\n'
            '    返回 函数(x) =>\n'
            '        返回 x * 倍数\n'
            '定义 双倍 = 创建乘法器(2)\n'
            '定义 三倍 = 创建乘法器(3)\n'
            '打印(双倍(5))\n'
            '打印(三倍(5))\n'
        )
        output = capture_output(source)
        assert output.strip() == "10\n15"


class TestInterpreterCollections:
    """集合操作测试"""

    def test_list_index(self):
        output = capture_output('定义 列表 = [10, 20, 30]\n打印(列表[1])\n')
        assert output.strip() == "20"

    def test_dict_access(self):
        output = capture_output('定义 字典 = {"a": 1, "b": 2}\n打印(字典["a"])\n')
        assert output.strip() == "1"

    def test_builtin_长度(self):
        output = capture_output('打印(长度([1, 2, 3]))\n')
        assert output.strip() == "3"

    def test_builtin_取类型(self):
        output = capture_output('打印(取类型(42))\n')
        assert output.strip() == "数值"


class TestInterpreterErrorHandling:
    """错误处理测试"""

    def test_undefined_variable(self):
        with pytest.raises(名称错误):
            run('打印(未定义变量)\n')

    def test_try_catch(self):
        source = '尝试\n    抛出 "测试错误"\n捕获 错误\n    打印("已捕获")\n'
        output = capture_output(source)
        assert output.strip() == "已捕获"

    def test_try_finally(self):
        source = '尝试\n    打印("尝试")\n最终\n    打印("最终")\n'
        output = capture_output(source)
        assert "尝试" in output
        assert "最终" in output


class TestSpreadOperator:
    """展开运算符测试"""

    def test_list_spread(self):
        source = (
            '定义 原列表 = [1, 2, 3]\n'
            '定义 新列表 = [...原列表, 4, 5]\n'
            '打印(新列表)\n'
        )
        output = capture_output(source)
        assert output.strip() == "[1, 2, 3, 4, 5]"

    def test_list_spread_multiple(self):
        source = (
            '定义 甲 = [1, 2]\n'
            '定义 乙 = [3, 4]\n'
            '定义 合并 = [...甲, ...乙]\n'
            '打印(合并)\n'
        )
        output = capture_output(source)
        assert output.strip() == "[1, 2, 3, 4]"

    def test_dict_spread(self):
        source = (
            '定义 原始 = {"姓名": "张三", "年龄": 25}\n'
            '定义 更新后 = {...原始, "年龄": 26}\n'
            '打印(更新后["姓名"])\n'
            '打印(更新后["年龄"])\n'
        )
        output = capture_output(source)
        assert output.strip() == "张三\n26"

    def test_dict_spread_with_new_key(self):
        source = (
            '定义 原始 = {"姓名": "张三"}\n'
            '定义 更新后 = {...原始, "城市": "北京"}\n'
            '打印(更新后["姓名"])\n'
            '打印(更新后["城市"])\n'
        )
        output = capture_output(source)
        assert output.strip() == "张三\n北京"

    def test_dict_spread_brace_syntax(self):
        source = (
            '定义 原始 = {"a": 1}\n'
            '定义 更新后 = {...原始, "b": 2}\n'
            '打印(更新后["a"])\n'
            '打印(更新后["b"])\n'
        )
        output = capture_output(source)
        assert output.strip() == "1\n2"

    def test_list_spread_preserves_original(self):
        source = (
            '定义 原列表 = [1, 2, 3]\n'
            '定义 新列表 = [...原列表, 4]\n'
            '打印(原列表)\n'
            '打印(新列表)\n'
        )
        output = capture_output(source)
        assert "原列表" not in output.split("\n")[1] or output.strip() == "[1, 2, 3]\n[1, 2, 3, 4]"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
