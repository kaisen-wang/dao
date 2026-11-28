"""
@ 注解在字节码 VM 模式下的测试
================================

覆盖《注解功能设计规格》§2.6：BytecodeCompiler 应为带注解的声明生成
等价的注解应用字节码，使 ``--mode vm`` 下行为与 AST 模式一致。

测试同时以 AST 解释器为基准做一致性断言。对现有指令集无法表达的场景
（关键字参数），断言"注解被忽略但声明正常"的降级行为。
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest

from dao.bytecode.compiler import BytecodeCompiler
from dao.errors import 运行时错误
from dao.interpreter.core import Interpreter
from dao.lexer import Lexer
from dao.parser import Parser
from dao.vm.core import VirtualMachine


def _parse(source: str):
    return Parser(Lexer(source).tokenize()).parse()


def run_vm(source: str):
    """源码 -> AST -> 字节码 -> VM 执行。"""
    return VirtualMachine().run(BytecodeCompiler().compile(_parse(source)))


def run_ast(source: str):
    """源码 -> AST 解释器执行（基准）。"""
    return Interpreter().execute(_parse(source))


def test_vm_variable_annotation_replaces_value_matches_ast():
    """简单替换型注解：VM 与 AST 模式结果一致。"""
    src = """\
函数 加一(x)
  返回 x + 1

@加一
定义 x = 10
x
"""
    assert run_vm(src) == 11
    assert run_vm(src) == run_ast(src)


def test_vm_annotation_with_positional_args_matches_ast():
    """带位置参数的注解：被装饰对象作为第一个参数，其后是注解参数。"""
    src = """\
函数 增加(v, n)
  返回 v + n

@增加(5)
定义 x = 10
x
"""
    assert run_vm(src) == 15
    assert run_vm(src) == run_ast(src)


def test_vm_multiple_annotations_apply_bottom_up():
    """多个注解按书写顺序的逆序应用（先乘二 20，再加一 21）。"""
    src = """\
函数 加一(x)
  返回 x + 1
函数 乘二(x)
  返回 x * 2

@加一
@乘二
定义 x = 10
x
"""
    assert run_vm(src) == 21
    assert run_vm(src) == run_ast(src)


def test_vm_annotation_returning_none_keeps_original():
    """注解返回 None 时保留原对象，不替换。"""
    src = """\
函数 无操作(x)
  返回 空

@无操作
定义 x = 10
x
"""
    assert run_vm(src) == 10
    assert run_vm(src) == run_ast(src)


def test_vm_function_annotation_matches_ast():
    """函数声明上的注解同样被应用，包装后写回同名变量。"""
    src = """\
函数 包装(fn)
  返回 fn

@包装
函数 f(x)
  返回 x + 1

f(5)
"""
    assert run_vm(src) == 6
    assert run_vm(src) == run_ast(src)


def test_vm_kwargs_annotation_delegates_to_ast_interpreter():
    """带关键字参数的注解委托内嵌 AST 解释器执行，语义与 AST 模式一致。"""
    src = """\
函数 增加(v, n)
  返回 v + n

@增加(n=5)
定义 x = 10
x
"""
    assert run_vm(src) == 15
    assert run_ast(src) == 15


def test_vm_undefined_annotation_raises_chinese_error():
    """注解函数未定义时抛出中文运行时错误。"""
    src = """\
@不存在的注解
定义 x = 10
x
"""
    with pytest.raises(运行时错误) as exc:
        run_vm(src)
    # 错误消息必须为中文，且含注解名
    assert "不存在" in str(exc.value)
