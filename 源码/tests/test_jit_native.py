"""JIT 原生代码生成的正确性回归测试。"""

import os
import sys
from contextlib import redirect_stdout
from io import StringIO

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from dao.bytecode.compiler import BytecodeCompiler
from dao.errors import 运行时错误
from dao.lexer import Lexer
from dao.parser import Parser
from dao.vm.core import VirtualMachine


def compile_source(source):
    return BytecodeCompiler().compile(Parser(Lexer(source).tokenize()).parse())


def run_vm(source, jit=False, threshold=3):
    vm = VirtualMachine()
    if jit:
        vm.enable_jit(threshold=threshold)
    result = vm.run(compile_source(source))
    return result, vm


def run_output(source, jit=False, threshold=3):
    vm = VirtualMachine()
    if jit:
        vm.enable_jit(threshold=threshold)
    buf = StringIO()
    with redirect_stdout(buf):
        result = vm.run(compile_source(source))
    return result, buf.getvalue(), vm


def function_keys(vm):
    """从类型反馈键还原出被 JIT 过的函数 CodeObject 身份。"""
    return {int(key.rsplit(".", 1)[0]) for key in vm._type_feedback}


class TestJitNative:
    def test_hotspot_triggers_native_codegen(self):
        source = (
            "函数 f(x)\n    返回 x + 1\n"
            "定义 a = f(1) + f(2) + f(3) + f(4)\n"
            "a"
        )
        result, vm = run_vm(source, jit=True, threshold=2)
        assert result == 14
        assert vm._jit_compiler.native_count() >= 1

    def test_type_guard_deopts_and_preserves_result(self):
        source = (
            "函数 恒等(x)\n    返回 x\n"
            "定义 a = 恒等(1) + 恒等(2) + 恒等(3) + 恒等(4)\n"
            '定义 b = 恒等("文本")\n'
            "b"
        )
        result, vm = run_vm(source, jit=True, threshold=2)
        assert result == "文本"
        assert vm._jit_compiler.total_deopts() >= 1
        assert all(vm._jit_compiler.get_native(k) is None for k in function_keys(vm))

    def test_mixed_types_still_correct(self):
        source = (
            "函数 恒等(x)\n    返回 x\n"
            "定义 a = 恒等(1) + 恒等(2) + 恒等(3)\n"
            '定义 b = 恒等("甲") + 恒等("乙")\n'
            "定义 c = 恒等(4) + 恒等(5)\n"
            "c"
        )
        result, vm = run_vm(source, jit=True, threshold=2)
        assert result == 9
        assert vm._jit_compiler.total_deopts() >= 1

    def test_recursion_matches_interpreter(self):
        source = (
            "函数 fib(n)\n"
            "    如果 n <= 1\n"
            "        返回 n\n"
            "    返回 fib(n - 1) + fib(n - 2)\n"
            "fib(14)"
        )
        expected, _ = run_vm(source)
        actual, vm = run_vm(source, jit=True, threshold=3)
        assert actual == expected == 377
        assert vm._jit_compiler.native_count() >= 1

    def test_loop_accumulation_matches_interpreter(self):
        source = (
            "定义 总和 = 0\n"
            "遍历 i 从 0 到 4999\n"
            "    设 总和 = 总和 + i\n"
            "总和"
        )
        expected, _ = run_vm(source)
        actual, vm = run_vm(source, jit=True, threshold=3)
        assert actual == expected == 12497500
        assert vm._jit_compiler.native_count() >= 1

    def test_while_loop_with_jit(self):
        source = (
            "定义 x = 0\n定义 i = 0\n"
            "当 i < 100\n"
            "    x = x + i\n    i = i + 1\n"
            "x"
        )
        expected, _ = run_vm(source)
        actual, _vm = run_vm(source, jit=True, threshold=3)
        assert actual == expected == 4950

    def test_closure_capture_and_mutation(self):
        source = (
            "函数 外层()\n"
            "    定义 计数 = 0\n"
            "    函数 内层()\n"
            "        计数 = 计数 + 1\n"
            "        返回 计数\n"
            "    返回 内层\n"
            "定义 计数器 = 外层()\n"
            "定义 a = 计数器() + 计数器() + 计数器()\n"
            "a"
        )
        expected, _ = run_vm(source)
        actual, _vm = run_vm(source, jit=True, threshold=2)
        assert actual == expected == 6

    def test_builtin_function_call(self):
        source = (
            "函数 求长度(x)\n    返回 长度(x)\n"
            '定义 a = 求长度("abcd") + 求长度("xy") + 求长度("z") + 求长度("")\n'
            "a"
        )
        expected, _ = run_vm(source)
        actual, _vm = run_vm(source, jit=True, threshold=2)
        assert actual == expected == 7

    def test_division_by_zero_propagates(self):
        source = (
            "函数 危险(x)\n    返回 10 / x\n"
            "定义 a = 危险(5) + 危险(2) + 危险(1) + 危险(5)\n"
            "危险(0)"
        )
        expected_error = None
        try:
            run_vm(source)
        except 运行时错误 as exc:
            expected_error = str(exc)
        assert expected_error is not None
        jit_error = None
        try:
            run_vm(source, jit=True, threshold=2)
        except 运行时错误 as exc:
            jit_error = str(exc)
        assert jit_error is not None
        assert "除零错误" in jit_error

    def test_deoptimization_limit(self):
        source = (
            "函数 恒等(x)\n    返回 x\n"
            "定义 a = 恒等(1) + 恒等(2) + 恒等(3)\n"
            '定义 b = 恒等("1") + 恒等("2") + 恒等("3") + 恒等("4") + 恒等("5")\n'
            '定义 c = 恒等("6") + 恒等("7")\n'
            "c"
        )
        result, vm = run_vm(source, jit=True, threshold=2)
        assert result == "67"
        assert vm._jit_compiler.total_deopts() == 3
        assert all(vm._jit_compiler.get_native(k) is None for k in function_keys(vm))

    def test_same_named_functions_do_not_pollute(self):
        source = (
            "函数 f(x)\n    返回 x + 1\n"
            "定义 a = f(1) + f(2)\n"
            "函数 f(x)\n    返回 x * 10\n"
            "定义 b = f(2) + f(3)\n"
            "a + b"
        )
        expected, _ = run_vm(source)
        actual, vm = run_vm(source, jit=True, threshold=2)
        assert actual == expected == 55
        keys = function_keys(vm)
        assert len(keys) == 2
        assert all(vm._jit_compiler.get_native(k) is not None for k in keys)

    def test_list_and_index_operations(self):
        source = (
            "函数 取元素(列表, i)\n    返回 列表[i]\n"
            "定义 a = 取元素([10, 20], 0) + 取元素([30, 40], 1)\n"
            "定义 b = 取元素([50, 60], 1) + 取元素([70, 80], 0)\n"
            "a + b"
        )
        expected, _ = run_vm(source)
        actual, _vm = run_vm(source, jit=True, threshold=2)
        assert actual == expected == 180

    def test_print_and_module_output_identical(self):
        source = (
            "定义 总和 = 0\n"
            "遍历 i 从 1 到 20\n    总和 = 总和 + i\n"
            "打印(总和)\n总和"
        )
        expected, expected_out, _ = run_output(source)
        actual, actual_out, _vm = run_output(source, jit=True, threshold=3)
        assert actual == expected == 210
        assert actual_out == expected_out == "210\n"

    def test_nested_calls_and_conditionals(self):
        source = (
            "函数 分类(n)\n"
            "    如果 n < 0\n        返回 -1\n"
            "    否则如果 n == 0\n        返回 0\n"
            "    返回 1\n"
            "函数 汇总(n)\n"
            "    返回 分类(n) + 分类(n - 1) + 分类(n + 1)\n"
            "定义 a = 汇总(0) + 汇总(1) + 汇总(2) + 汇总(-1)\n"
            "a"
        )
        expected, _ = run_vm(source)
        actual, vm = run_vm(source, jit=True, threshold=2)
        assert actual == expected
        assert vm._jit_compiler.native_count() >= 1
