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


class TestDualModePatternMatching:
    """模式匹配：字面量、通配符、列表/字典模式、守卫、嵌套匹配。"""

    def test_literal_number_match(self):
        src = "定义 x = 2\n匹配 x\n  情况 1: 10\n  情况 2: 99\n  情况 _: 0"
        assert_dual_equal(src)
        assert run_interpreter(src) == 99

    def test_literal_string_match(self):
        src = (
            '定义 颜色 = "绿"\n匹配 颜色\n'
            '  情况 "红": 1\n  情况 "绿": 2\n  情况 _: 0'
        )
        assert_dual_equal(src)
        assert run_interpreter(src) == 2

    def test_wildcard_match(self):
        src = "定义 x = 99\n匹配 x\n  情况 1: 10\n  情况 _: 0"
        assert_dual_equal(src)
        assert run_interpreter(src) == 0

    def test_no_case_matched_returns_null(self):
        src = "定义 x = 99\n匹配 x\n  情况 1: 10\n  情况 2: 20"
        assert_dual_equal(src)
        assert run_interpreter(src) is None

    def test_list_pattern_binds_elements(self):
        src = (
            "定义 d = [1, 2]\n匹配 d\n"
            "  情况 [a, b]: a + b\n  情况 _: 0"
        )
        assert_dual_equal(src)
        assert run_interpreter(src) == 3

    def test_dict_pattern_binds_value(self):
        src = (
            '定义 d = {"x": 3}\n匹配 d\n'
            '  情况 {"x": v}: v\n  情况 _: 0'
        )
        assert_dual_equal(src)
        assert run_interpreter(src) == 3

    def test_guard_pattern(self):
        src = (
            "定义 n = 5\n匹配 n\n"
            "  情况 x 当 x > 3: x\n  情况 _: 0"
        )
        assert_dual_equal(src)
        assert run_interpreter(src) == 5

    def test_guard_falls_through_to_wildcard(self):
        src = (
            "定义 n = 1\n匹配 n\n"
            "  情况 x 当 x > 3: x\n  情况 _: 0"
        )
        assert_dual_equal(src)
        assert run_interpreter(src) == 0

    def test_bare_identifier_dispatch_by_value(self):
        src = (
            '定义 A = "A"\n定义 v = "B"\n匹配 v\n'
            '  情况 A: 1\n  情况 _: 2'
        )
        assert_dual_equal(src)
        assert run_interpreter(src) == 2

    def test_return_inside_match_propagates(self):
        src = (
            "函数 f(x)\n"
            "  匹配 x\n"
            "    情况 1: 返回 10\n"
            "    情况 2: 返回 20\n"
            "  返回 0\n"
            "f(2)"
        )
        assert_dual_equal(src)
        assert run_interpreter(src) == 20

    def test_nested_match(self):
        src = (
            "定义 x = 2\n定义 y = 3\n"
            "匹配 x\n"
            "  情况 1: 0\n"
            "  情况 2:\n"
            "    匹配 y\n"
            "      情况 3: 100\n"
            "      情况 _: 0\n"
            "  情况 _: 0"
        )
        assert_dual_equal(src)
        assert run_interpreter(src) == 100


class TestDualModeEnum:
    """枚举声明、变体构造与枚举模式匹配。"""

    def test_enum_variant_access(self):
        src = "枚举 颜色\n  红\n  绿\n颜色.红"
        assert_dual_equal(src)

    def test_enum_variant_construction(self):
        src = "枚举 结果\n  成功(值)\n  失败(信息)\n结果.成功(42)"
        assert_dual_equal(src)

    def test_enum_simple_variant_match(self):
        src = (
            "枚举 颜色\n  红\n  绿\n"
            "定义 c = 颜色.绿\n匹配 c\n"
            "  情况 颜色.红: 1\n"
            "  情况 颜色.绿: 2\n"
            "  情况 _: 0"
        )
        assert_dual_equal(src)
        assert run_interpreter(src) == 2

    def test_enum_variant_with_binding_match(self):
        src = (
            "枚举 结果\n  成功(值)\n  失败(信息)\n"
            "定义 r = 结果.成功(42)\n匹配 r\n"
            "  情况 结果.成功(v): v\n"
            "  情况 结果.失败(m): m"
        )
        assert_dual_equal(src)
        assert run_interpreter(src) == 42

    def test_enum_variant_failure_binding(self):
        src = (
            "枚举 结果\n  成功(值)\n  失败(信息)\n"
            "定义 r = 结果.失败(\"未找到\")\n匹配 r\n"
            "  情况 结果.成功(v): v\n"
            "  情况 结果.失败(m): m"
        )
        assert_dual_equal(src)
        assert run_interpreter(src) == "未找到"

    def test_enum_variant_builtin_fields(self):
        src = (
            "枚举 结果\n  成功(值)\n"
            "定义 r = 结果.成功(7)\nr.变体名"
        )
        assert_dual_equal(src)
        assert run_interpreter(src) == "成功"

    def test_enum_variant_associated_value_by_param_name(self):
        src = (
            "枚举 结果\n  成功(值)\n"
            "定义 r = 结果.成功(5)\nr.值"
        )
        assert_dual_equal(src)
        assert run_interpreter(src) == 5


class TestDualModeConcurrencyPrimitives:
    """并发原语：通道创建、发送、接收在双模式下行为一致。"""

    def test_create_unbuffered_channel(self):
        src = "定义 c = 通道()\n取类型(c)"
        ast_type = run_interpreter(src)
        vm_type = run_vm(src)
        assert ast_type == vm_type
        assert "Channel" in str(ast_type)

    def test_create_buffered_channel(self):
        src = "定义 c = 通道(2)\n取类型(c)"
        assert_dual_equal(src)

    def test_buffered_channel_send_receive(self):
        src = "定义 c = 通道(2)\n发送 c, 10\n定义 x = 接收 c\nx"
        assert_dual_equal(src)
        assert run_interpreter(src) == 10

    def test_channel_error_on_send_to_non_channel(self):
        # 两种模式都会因对非通道发送而报错
        assert_dual_both_error("定义 x = 1\n发送 x, 2")


class TestDualModeConditionalExpr:
    """三元条件表达式与布尔常量语义。"""

    def test_ternary_true_branch(self):
        src = "定义 x = 1\n定义 r = 真 如果 x 否则 假\nr"
        assert_dual_equal(src)
        assert run_interpreter(src) is True

    def test_ternary_false_branch(self):
        src = "定义 x = 0\n定义 r = 真 如果 x 否则 假\nr"
        assert_dual_equal(src)
        assert run_interpreter(src) is False

    def test_boolean_literal_not_confused_with_int(self):
        # 回归：常量池曾用 == 比较，导致 真 被复用为 1
        assert run_interpreter("真") is True
        assert run_vm("真") is True
        assert run_interpreter("假") is False
        assert run_vm("假") is False


class TestDualModeIndexSemantics:
    """索引访问的类型边界与 AST 解释器对齐。"""

    def test_tuple_index_rejected_in_both_modes(self):
        assert_dual_both_error("定义 t = (1, 2)\nt[0]")

    def test_list_index_out_of_range_in_both_modes(self):
        assert_dual_both_error("[1, 2][9]")

    def test_dict_missing_key_in_both_modes(self):
        assert_dual_both_error('{"a": 1}["b"]')


class TestDualModeCollections:
    """集合、元组、嵌套容器的双模式一致性。"""

    def test_set_literal(self):
        assert_dual_equal("定义 s = {1, 2, 2, 3}\n长度(s)")

    def test_tuple_literal(self):
        assert_dual_equal("定义 t = (1, 2, 3)\n长度(t)")

    def test_nested_list(self):
        assert_dual_equal("定义 x = [[1, 2], [3, 4]]\nx[1][0]")

    def test_dict_with_list_value(self):
        assert_dual_equal('定义 d = {"a": [1, 2]}\nd["a"][1]')

    def test_string_concatenation(self):
        assert_dual_equal('"你" + "好"')

    def test_list_append_member(self):
        src = "定义 a = [1]\na.追加(2)\na"
        assert_dual_equal(src)
        assert run_interpreter(src) == [1, 2]
