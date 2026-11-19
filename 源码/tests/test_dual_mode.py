import sys
import os
from io import StringIO
from contextlib import redirect_stdout

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from dao.errors import 道错误
from dao.lexer import Lexer
from dao.parser import Parser
from dao.interpreter.core import Interpreter
from dao.bytecode.compiler import BytecodeCompiler
from dao.vm.core import VirtualMachine


def _parse(source: str):
    return Parser(Lexer(source).tokenize()).parse()


def run_interpreter(source: str):
    return Interpreter().execute(_parse(source))


def run_vm(source: str):
    return VirtualMachine().run(BytecodeCompiler().compile(_parse(source)))


def run_with_output(runner, source: str):
    """执行程序，返回 (求值结果, 标准输出)。"""
    buf = StringIO()
    with redirect_stdout(buf):
        result = runner(source)
    return result, buf.getvalue()


def assert_dual_equal(source: str):
    """同一程序在 AST 与 VM 两种模式下必须得到相同结果。"""
    ast_result = run_interpreter(source)
    vm_result = run_vm(source)
    assert vm_result == ast_result


def assert_dual_both_error(source: str):
    """同一程序在两种模式下都必须报错（异常类型可不同，但均属 道错误）。"""
    for runner in (run_interpreter, run_vm):
        with pytest.raises(道错误):
            runner(source)


class TestDualMode:
    def test_arithmetic(self):
        src = "1 + 2"
        assert run_interpreter(src) == run_vm(src)

    def test_variable(self):
        src = "定义 x = 42\nx"
        assert run_interpreter(src) == run_vm(src)

    def test_if_branch(self):
        src = "定义 x = 0\n如果 1\n  x = 10\nx"
        assert run_interpreter(src) == run_vm(src)

    def test_while_loop(self):
        src = "定义 x = 0\n定义 i = 0\n当 i < 3\n  x = x + 1\n  i = i + 1\nx"
        assert run_interpreter(src) == run_vm(src)

    def test_function(self):
        src = "函数 f(x)\n  返回 x + 1\n\nf(5)"
        assert run_interpreter(src) == run_vm(src)

    def test_list(self):
        src = "定义 x = [1, 2, 3]\nx"
        assert run_interpreter(src) == run_vm(src)

    def test_string(self):
        src = '定义 x = "hello"\nx'
        assert run_interpreter(src) == run_vm(src)

    def test_comparison(self):
        src = "1 < 2"
        assert run_interpreter(src) == run_vm(src)


class TestDualModeUndefinedVariable:
    """未定义变量访问：两种模式都应报错（AST 抛 名称错误，VM 抛 运行时错误）。"""

    def test_undefined_variable(self):
        assert_dual_both_error("不存在的变量")

    def test_undefined_variable_in_expression(self):
        assert_dual_both_error("定义 x = 1\nx + 不存在的变量")

    def test_undefined_variable_in_function(self):
        assert_dual_both_error("函数 f()\n  返回 不存在的变量\nf()")


class TestDualModeBreakContinue:
    """break / continue 在 while 循环中的行为。"""

    def test_break_in_while(self):
        src = (
            "定义 x = 0\n定义 i = 0\n"
            "当 i < 10\n"
            "  i = i + 1\n"
            "  如果 i == 4\n"
            "    跳出\n"
            "  x = x + 1\n"
            "x"
        )
        assert_dual_equal(src)
        assert run_interpreter(src) == 3

    def test_continue_in_while(self):
        src = (
            "定义 x = 0\n定义 i = 0\n"
            "当 i < 5\n"
            "  i = i + 1\n"
            "  如果 i == 3\n"
            "    继续\n"
            "  x = x + 1\n"
            "x"
        )
        assert_dual_equal(src)
        assert run_interpreter(src) == 4

    def test_break_and_continue_combined(self):
        src = (
            "定义 total = 0\n定义 i = 0\n"
            "当 i < 10\n"
            "  i = i + 1\n"
            "  如果 i == 3\n"
            "    继续\n"
            "  如果 i == 7\n"
            "    跳出\n"
            "  total = total + i\n"
            "total"
        )
        assert_dual_equal(src)
        assert run_interpreter(src) == 18


class TestDualModeClosure:
    """闭包：函数捕获外部变量。"""

    def test_closure_captures_variable(self):
        src = "定义 x = 10\n函数 f()\n  返回 x + 1\nf()"
        assert_dual_equal(src)
        assert run_interpreter(src) == 11

    def test_closure_sees_updated_variable(self):
        # 捕获应按引用共享：函数定义后外部变量被修改，闭包应看到新值。
        src = "定义 x = 10\n函数 f()\n  返回 x + 1\nx = 20\nf()"
        assert_dual_equal(src)
        assert run_interpreter(src) == 21

    def test_closure_can_mutate_captured_variable(self):
        src = (
            "定义 计数 = 0\n"
            "函数 递增()\n"
            "  计数 = 计数 + 1\n"
            "  返回 计数\n"
            "递增()\n递增()"
        )
        assert_dual_equal(src)
        assert run_interpreter(src) == 2

    def test_nested_closure(self):
        src = (
            "函数 外层()\n"
            "  定义 y = 5\n"
            "  函数 内层()\n"
            "    返回 y + 1\n"
            "  返回 内层()\n"
            "外层()"
        )
        assert_dual_equal(src)
        assert run_interpreter(src) == 6

    def test_closure_captures_outer_parameter(self):
        src = (
            "函数 外层(x)\n"
            "  函数 内层()\n"
            "    返回 x + 1\n"
            "  返回 内层()\n"
            "外层(5)"
        )
        assert_dual_equal(src)
        assert run_interpreter(src) == 6

    def test_closure_returned_from_function(self):
        src = (
            "函数 外层()\n"
            "  定义 y = 5\n"
            "  函数 内层()\n"
            "    返回 y + 1\n"
            "  返回 内层\n"
            "定义 g = 外层()\n"
            "g()"
        )
        assert_dual_equal(src)
        assert run_interpreter(src) == 6


class TestDualModeBuiltins:
    """内置函数（打印/长度/范围等）。"""

    def test_builtin_print(self):
        src = '打印("你好")'
        ast_res, ast_out = run_with_output(run_interpreter, src)
        vm_res, vm_out = run_with_output(run_vm, src)
        assert ast_res == vm_res
        assert ast_out == vm_out
        assert ast_out.strip() == "你好"

    def test_builtin_length(self):
        assert_dual_equal("长度([1, 2, 3])")

    def test_builtin_range(self):
        assert_dual_equal("范围(1, 3)")

    def test_builtin_int_conversion(self):
        assert_dual_equal('整数("42")')

    def test_builtin_inside_function(self):
        src = "函数 f()\n  返回 长度([1, 2])\nf()"
        assert_dual_equal(src)
        assert run_interpreter(src) == 2

    def test_builtin_multi_arg(self):
        assert_dual_equal("最大值(3, 9, 2)")


class TestDualModeErrorPropagation:
    """错误传播：函数内部错误应向外抛出，两种模式一致报错。"""

    def test_undefined_variable_propagates(self):
        assert_dual_both_error("函数 f()\n  返回 不存在的变量\nf()")

    def test_division_by_zero_propagates(self):
        assert_dual_both_error("函数 f()\n  返回 1 / 0\nf()")

    def test_nested_call_error_propagates(self):
        assert_dual_both_error(
            "函数 内层()\n  返回 不存在的变量\n"
            "函数 外层()\n  返回 内层()\n"
            "外层()"
        )


class TestDualModeMemberAndIndex:
    """成员访问 / 索引访问。"""

    def test_index_list(self):
        assert_dual_equal("[10, 20, 30][1]")

    def test_index_dict(self):
        assert_dual_equal('{"a": 1, "b": 2}["b"]')

    def test_index_string(self):
        assert_dual_equal('"hello"[1]')

    def test_member_dict(self):
        src = '定义 d = {"x": 7}\nd.x'
        assert_dual_equal(src)
        assert run_interpreter(src) == 7

    def test_member_list_builtin(self):
        src = "定义 a = [1, 2, 3]\na.长度"
        assert_dual_equal(src)
        assert run_interpreter(src) == 3

    def test_member_string_builtin(self):
        src = '定义 s = "hello"\ns.大写'
        assert_dual_equal(src)
        assert run_interpreter(src) == "HELLO"


class TestDualModeNestedAndRecursiveCalls:
    """嵌套函数调用与递归。"""

    def test_nested_function_calls(self):
        src = (
            "函数 加一(x)\n  返回 x + 1\n"
            "函数 加二(x)\n  返回 加一(加一(x))\n"
            "加二(5)"
        )
        assert_dual_equal(src)
        assert run_interpreter(src) == 7

    def test_recursive_factorial(self):
        src = (
            "函数 阶乘(n)\n"
            "  如果 n <= 1\n"
            "    返回 1\n"
            "  返回 n * 阶乘(n - 1)\n"
            "阶乘(5)"
        )
        assert_dual_equal(src)
        assert run_interpreter(src) == 120

    def test_recursive_fibonacci(self):
        src = (
            "函数 斐波那契(n)\n"
            "  如果 n < 2\n"
            "    返回 n\n"
            "  返回 斐波那契(n - 1) + 斐波那契(n - 2)\n"
            "斐波那契(8)"
        )
        assert_dual_equal(src)
        assert run_interpreter(src) == 21

    def test_forward_reference_between_functions(self):
        src = "函数 f()\n  返回 g()\n函数 g()\n  返回 5\nf()"
        assert_dual_equal(src)
        assert run_interpreter(src) == 5
