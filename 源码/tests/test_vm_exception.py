"""
异常控制流在双模式（AST / VM / VM+JIT）下的验收测试
====================================================

覆盖尝试/捕获/最终/抛出的基本捕获、错误类型匹配（异常 / 类型错误 /
运行时错误）、用户自定义错误类、finally 执行顺序、未匹配异常传播与
中文报错、try 内 return / break / continue 时 finally 仍执行、嵌套 try、
抛出字符串与对象，以及 JIT 开启时的一致行为。

VM 模式当前缺少 SETUP_TRY / RAISE 等指令与处理器栈，相关用例预期
一开始就失败；断言表达的是真实需求，不使用 skip / xfail 规避。
"""

import os
import sys
from contextlib import redirect_stdout
from io import StringIO

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from dao.bytecode.compiler import BytecodeCompiler
from dao.errors import 道错误
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


def run_vm_jit(source: str) -> object:
    """源码 -> AST -> 字节码 -> 开启 JIT 的 VM 执行。"""
    vm = VirtualMachine()
    vm.enable_jit(threshold=1)
    return vm.run(BytecodeCompiler().compile(_parse(source)))


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


def assert_jit_equal(source: str) -> object:
    """开启 JIT 的 VM 必须与 AST 基准一致。"""
    ast_result = run_ast(source)
    jit_result = run_vm_jit(source)
    assert jit_result == ast_result
    return ast_result


class TestVMExceptionBasic:
    """try/catch 基本捕获。"""

    def test_try_catch_basic_capture(self):
        src = """
尝试
  抛出 "测试错误"
捕获 err
  打印("已捕获")
"""
        ast_result, ast_out = assert_dual_output_equal(src)
        assert ast_result is None
        assert ast_out.strip() == "已捕获"

    def test_catch_variable_exposes_error_message(self):
        src = """
尝试
  抛出 "测试错误"
捕获 err
  打印(err.信息)
"""
        ast_result, ast_out = run_with_output(run_ast, src)
        vm_result, vm_out = run_with_output(run_vm, src)
        assert ast_result is None and vm_result is None
        # VM 字节码只保留行号（无列与源码片段），因此比较关键内容而非完整字符串
        assert "测试错误" in ast_out and "测试错误" in vm_out
        assert "运行时错误" in ast_out and "运行时错误" in vm_out

    def test_try_without_exception_runs_catch_not(self):
        src = """
定义 日志 = ""
尝试
  日志 = 日志 + "尝试;"
捕获 err
  日志 = 日志 + "捕获;"
日志
"""
        assert run_ast(src) == "尝试;"
        assert_dual_equal(src)


class TestVMExceptionTypeMatching:
    """错误类型匹配。"""

    def test_catch_异常_matches_all_errors(self):
        src = """
尝试
  长度(1)
捕获 异常: err
  打印("兜底捕获")
"""
        ast_result, ast_out = assert_dual_output_equal(src)
        assert ast_result is None
        assert ast_out.strip() == "兜底捕获"

    def test_builtin_类型错误_name_reported_on_caught_error(self):
        src = """
定义 结果 = ""
尝试
  长度(1)
捕获 err
  结果 = err.类型
结果
"""
        assert run_ast(src) == "类型错误"
        assert_dual_equal(src)

    def test_builtin_运行时错误_name_reported_on_caught_error(self):
        src = """
定义 结果 = ""
尝试
  抛出 "boom"
捕获 err
  结果 = err.类型
结果
"""
        assert run_ast(src) == "运行时错误"
        assert_dual_equal(src)

    def test_typed_catch_on_custom_error_class(self):
        src = """
类型 业务错误 继承自 错误
尝试
  抛出 业务错误("出错啦")
捕获 业务错误: err
  打印("匹配业务错误")
捕获 异常: err
  打印("兜底")
"""
        ast_result, ast_out = assert_dual_output_equal(src)
        assert ast_result is None
        assert "匹配业务错误" in ast_out
        assert "兜底" not in ast_out


class TestVMExceptionFinally:
    """finally 执行顺序与控制流信号。"""

    def test_finally_runs_after_try(self):
        src = """
定义 日志 = ""
尝试
  日志 = 日志 + "尝试;"
最终
  日志 = 日志 + "最终;"
日志
"""
        assert run_ast(src) == "尝试;最终;"
        assert_dual_equal(src)

    def test_finally_runs_after_catch(self):
        src = """
定义 日志 = ""
尝试
  抛出 "boom"
捕获 err
  日志 = 日志 + "捕获;"
最终
  日志 = 日志 + "最终;"
日志
"""
        assert run_ast(src) == "捕获;最终;"
        assert_dual_equal(src)

    def test_return_inside_try_still_runs_finally(self):
        src = """
函数 f()
  尝试
    返回 1
  最终
    打印("finally")
f()
"""
        ast_result, ast_out = assert_dual_output_equal(src)
        assert ast_result == 1
        assert ast_out.strip() == "finally"

    def test_break_inside_try_still_runs_finally(self):
        src = """
定义 结果 = 0
遍历 i 从 1 到 5
  尝试
    如果 i == 3
      跳出
    结果 = 结果 + i
  最终
    打印("F")
结果
"""
        ast_result, ast_out = assert_dual_output_equal(src)
        assert ast_result == 3
        assert ast_out.split() == ["F", "F", "F"]

    def test_continue_inside_try_still_runs_finally(self):
        src = """
定义 结果 = 0
遍历 i 从 1 到 3
  尝试
    如果 i == 2
      继续
    结果 = 结果 + i
  最终
    打印("F")
结果
"""
        ast_result, ast_out = assert_dual_output_equal(src)
        assert ast_result == 4
        assert ast_out.split() == ["F", "F", "F"]


class TestVMExceptionPropagation:
    """未匹配异常传播、嵌套 try、抛出对象。"""

    def test_unmatched_exception_propagates_with_chinese_message(self):
        src = """
类型 甲错误 继承自 错误
类型 乙错误 继承自 错误
尝试
  抛出 甲错误("未匹配的中文错误")
捕获 乙错误: err
  打印("不该捕获")
"""
        for runner in (run_ast, run_vm):
            with pytest.raises(道错误) as exc:
                runner(src)
            assert "未匹配的中文错误" in str(exc.value)

    def test_nested_try_finally_order(self):
        src = """
定义 日志 = ""
尝试
  尝试
    抛出 "内层错误"
  捕获 err
    日志 = 日志 + "内捕获;"
    抛出 "再抛"
  最终
    日志 = 日志 + "内最终;"
捕获 err
  日志 = 日志 + "外捕获;"
最终
  日志 = 日志 + "外最终;"
日志
"""
        assert run_ast(src) == "内捕获;内最终;外捕获;外最终;"
        assert_dual_equal(src)

    def test_throw_string_is_caught_as_runtime_error(self):
        src = """
定义 结果 = ""
尝试
  抛出 "字符串异常"
捕获 err
  结果 = err.类型 + "|" + err.信息
结果
"""
        ast_result = run_ast(src)
        vm_result = run_vm(src)
        # VM 只保留行号，错误信息中的列号与源码光标与 AST 不同，
        # 这里比较语义关键字段：错误类型与消息正文。
        for result in (ast_result, vm_result):
            assert "运行时错误" in result
            assert "字符串异常" in result
        assert vm_result.split("|", 1)[0] == ast_result.split("|", 1)[0]

    def test_throw_custom_error_object_is_caught(self):
        src = """
类型 业务错误 继承自 错误
尝试
  抛出 业务错误("对象错误")
捕获 err
  打印(err.信息)
"""
        ast_result, ast_out = assert_dual_output_equal(src)
        assert ast_result is None
        assert "对象错误" in ast_out


class TestVMExceptionJIT:
    """开启 JIT 后异常行为保持一致。"""

    def test_jit_try_catch_basic(self):
        src = """
尝试
  抛出 "测试错误"
捕获 err
  打印("已捕获")
"""
        ast_result, ast_out = run_with_output(run_ast, src)
        jit_result, jit_out = run_with_output(run_vm_jit, src)
        assert jit_result == ast_result
        assert jit_out == ast_out
        assert jit_out.strip() == "已捕获"

    def test_jit_finally_order(self):
        src = """
定义 日志 = ""
尝试
  日志 = 日志 + "尝试;"
最终
  日志 = 日志 + "最终;"
日志
"""
        assert run_ast(src) == "尝试;最终;"
        assert_jit_equal(src)

    def test_jit_return_inside_try_still_runs_finally(self):
        src = """
函数 f()
  尝试
    返回 1
  最终
    打印("finally")
f()
"""
        ast_result, ast_out = run_with_output(run_ast, src)
        jit_result, jit_out = run_with_output(run_vm_jit, src)
        assert jit_result == ast_result
        assert jit_out == ast_out
        assert ast_result == 1

    def test_jit_nested_try_order(self):
        src = """
定义 日志 = ""
尝试
  尝试
    抛出 "内层错误"
  捕获 err
    日志 = 日志 + "内捕获;"
    抛出 "再抛"
  最终
    日志 = 日志 + "内最终;"
捕获 err
  日志 = 日志 + "外捕获;"
最终
  日志 = 日志 + "外最终;"
日志
"""
        assert run_ast(src) == "内捕获;内最终;外捕获;外最终;"
        assert_jit_equal(src)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
