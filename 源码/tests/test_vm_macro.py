"""
宏系统在双模式（AST / VM）下的验收测试
======================================

覆盖自定义宏定义/调用、参数替换、卫生宏、递归宏、宏注入、模式宏、
内置宏 !日志 / !缓存 的输出与副作用、``@注解`` 位置参数与关键字参数，
以及 AST 与 VM 的返回值/输出一致性。

VM 模式当前缺少 MACRO_CALL 等指令的处理，相关用例预期一开始就失败；
断言表达的是真实需求，不使用 skip / xfail 规避。
"""

import os
import sys
from contextlib import redirect_stdout
from io import StringIO

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from dao.bytecode.compiler import BytecodeCompiler
from dao.errors import 运行时错误, 道错误
from dao.interpreter.core import Interpreter
from dao.lexer import Lexer
from dao.parser import Parser
from dao.vm.core import VirtualMachine


def _parse(source: str):
    return Parser(Lexer(source).tokenize(), source).parse()


def run_ast(source: str) -> object:
    """源码 -> AST -> AST 解释器执行（基准语义）。"""
    return Interpreter().execute(_parse(source), source=source)


def run_vm(source: str) -> object:
    """源码 -> AST -> 字节码 -> VM 执行。"""
    return VirtualMachine().run(BytecodeCompiler().compile(_parse(source)))


def run_with_output(runner, source: str):
    """执行程序，返回 (求值结果, 标准输出)。"""
    buf = StringIO()
    with redirect_stdout(buf):
        result = runner(source)
    return result, buf.getvalue()


def assert_dual_equal(source: str) -> object:
    """同一程序在 AST 与 VM 两种模式下必须得到相同结果。"""
    ast_result = run_ast(source)
    vm_result = run_vm(source)
    assert vm_result == ast_result
    return ast_result


def assert_dual_output_equal(source: str):
    """同一程序在两种模式下结果与标准输出都必须一致。"""
    ast_result, ast_out = run_with_output(run_ast, source)
    vm_result, vm_out = run_with_output(run_vm, source)
    assert vm_result == ast_result
    assert vm_out == ast_out
    return ast_result, ast_out


class TestVMMacroBasics:
    """自定义宏定义、调用与参数替换。"""

    def test_custom_macro_definition_and_call(self):
        src = """
定义宏 加一(x)
  返回 引述 $x + 1
定义 结果 = !加一(5)
结果
"""
        assert run_ast(src) == 6
        assert_dual_equal(src)

    def test_macro_parameter_substitution_with_multiple_params(self):
        src = """
定义宏 计算(a, b, c)
  返回 引述 ($a + $b) * $c
定义 结果 = !计算(1, 2, 3)
结果
"""
        assert run_ast(src) == 9
        assert_dual_equal(src)

    def test_macro_with_optional_default_parameter(self):
        src = """
定义宏 可选参数(x, y=10)
  返回 引述 $x + $y
定义 r1 = !可选参数(5)
定义 r2 = !可选参数(5, 20)
r1 + r2
"""
        assert run_ast(src) == 40
        assert_dual_equal(src)

    def test_macro_can_be_called_multiple_times(self):
        src = """
定义宏 双倍(x)
  返回 引述 $x * 2
定义 a = !双倍(3)
定义 b = !双倍(7)
文本(a) + "|" + 文本(b)
"""
        assert run_ast(src) == "6|14"
        assert_dual_equal(src)


class TestVMMacroHygieneAndRecursion:
    """卫生宏与递归宏。"""

    def test_hygienic_macro_does_not_overwrite_outer_variable(self):
        src = """
定义宏 卫生测试(x)
  返回 引述
    定义 temp = $x * 2
    temp
定义 temp = 10
定义 结果 = !卫生测试(5)
文本(temp) + "|" + 文本(结果)
"""
        assert run_ast(src) == "10|10"
        assert_dual_equal(src)

    def test_recursive_macro(self):
        src = """
定义宏 递归宏(n)
  返回 引述
    如果 $n == 0
      0
    否则
      $n + !递归宏($n - 1)
定义 结果 = !递归宏(5)
结果
"""
        assert run_ast(src) == 15
        assert_dual_equal(src)


class TestVMMacroInjectionAndPattern:
    """宏块注入与模式匹配宏。"""

    def test_macro_block_injection_returns_list_whole(self):
        src = """
定义宏 包裹(块)
  返回 引述
    定义 x = $块
    x
定义 r = !包裹()
  [7, 8, 9]
r
"""
        assert run_ast(src) == [7, 8, 9]
        assert_dual_equal(src)

    def test_pattern_macro_literal_match(self):
        src = """
定义宏 描述(值) 匹配
  0 => 引述 "零"
  _ => 引述 "非零"
定义 a = !描述(0)
定义 b = !描述(5)
文本(a) + "|" + 文本(b)
"""
        assert run_ast(src) == "零|非零"
        assert_dual_equal(src)

    def test_pattern_macro_list_destructure(self):
        src = """
定义宏 头部(列表) 匹配
  [头, ...尾] => 引述 $头
定义 r = !头部([10, 20, 30])
r
"""
        assert run_ast(src) == 10
        assert_dual_equal(src)


class TestVMMacroBuiltins:
    """内置宏 !日志 / !缓存 的输出与副作用。"""

    def test_builtin_日志_emits_enter_and_exit_logs(self):
        src = """
定义 值 = 0
!日志("测试函数")
  值 = 42
值
"""
        ast_result, ast_out = assert_dual_output_equal(src)
        assert ast_result == 42
        assert ">>> 进入: 测试函数" in ast_out
        assert "<<< 退出: 测试函数" in ast_out

    def test_builtin_缓存_executes_block_on_first_call(self):
        src = """
定义 _缓存表 = {}
定义 调用次数 = 0
定义 结果1 = !缓存("键1")
  调用次数 = 调用次数 + 1
  调用次数
文本(调用次数) + "|" + 文本(结果1)
"""
        assert run_ast(src) == "1|1"
        assert_dual_equal(src)


class TestVMMacroAnnotation:
    """``@注解`` 位置参数与关键字参数。"""

    def test_annotation_with_positional_args_matches_ast(self):
        src = """
函数 增加(v, n)
  返回 v + n
@增加(5)
定义 x = 10
x
"""
        assert run_ast(src) == 15
        assert run_vm(src) == 15
        assert_dual_equal(src)

    def test_annotation_with_kwargs_follows_ast_semantics(self):
        src = """
函数 增加(v, n)
  返回 v + n
@增加(n=5)
定义 x = 10
x
"""
        # 已知差异：VM 当前对 kwargs 注解降级（忽略注解，x 保持 10）。
        # 真实需求按 AST 语义：注解应正确应用得到 15，故 VM 也必须得到 15。
        assert run_ast(src) == 15
        assert run_vm(src) == 15
        assert_dual_equal(src)


class TestVMMacroConsistencyAndErrors:
    """AST/VM 一致性与中文报错。"""

    def test_ast_vm_output_consistency_for_macro_call(self):
        src = """
定义宏 加一(x)
  返回 引述 $x + 1
打印(!加一(5))
"""
        ast_result, ast_out = assert_dual_output_equal(src)
        assert ast_result is None
        assert ast_out.strip() == "6"

    def test_undefined_macro_raises_chinese_error(self):
        src = """
定义 结果 = !不存在的宏(5)
"""
        for runner in (run_ast, run_vm):
            with pytest.raises(道错误) as exc:
                runner(src)
            assert "未找到宏定义" in str(exc.value)

    def test_macro_error_type_is_runtime_error(self):
        src = "定义 结果 = !不存在的宏(5)"
        with pytest.raises(运行时错误):
            run_vm(src)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
