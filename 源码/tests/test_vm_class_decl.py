"""
类声明在双模式（AST / VM）下的验收测试
======================================

覆盖 ClassDecl / TraitDecl / AbstractDecl 委托 AST 解释器执行的语义：
简单类与实例化、继承、特征默认方法、抽象方法检查、类体闭包捕获、
``继承自 错误`` 自定义错误类、枚举原路径、``取类型`` 查询，
以及 AST 与 VM 的返回值/输出一致性。

VM 模式当前缺少 AST_DECL 等指令的处理，相关用例预期一开始就失败；
断言表达的是真实需求，不使用 skip / xfail 规避。
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


def assert_dual_both_error(source: str, message_contains: str | None = None):
    """同一程序在两种模式下都必须报 道错误（可含指定中文消息）。"""
    for runner in (run_ast, run_vm):
        with pytest.raises(道错误) as exc:
            runner(source)
        if message_contains:
            assert message_contains in str(exc.value)


class TestVMClassDeclBasics:
    """简单类声明、实例化与方法调用。"""

    def test_simple_class_instantiation_and_method_call(self):
        src = """
类型 圆形
  初始化(半径)
    本对象.半径 = 半径
  函数 面积()
    返回 3 * 本对象.半径 * 本对象.半径
定义 c = 圆形(2)
c.面积()
"""
        assert run_ast(src) == 12
        assert_dual_equal(src)

    def test_instance_field_read(self):
        src = """
类型 点
  初始化(x, y)
    本对象.x = x
    本对象.y = y
定义 p = 点(3, 4)
p.x + p.y
"""
        assert run_ast(src) == 7
        assert_dual_equal(src)

    def test_class_without_constructor_can_be_instantiated(self):
        src = """
类型 标记
  函数 名称()
    返回 "标记"
定义 m = 标记()
m.名称()
"""
        assert run_ast(src) == "标记"
        assert_dual_equal(src)


class TestVMClassDeclInheritance:
    """继承与方法解析。"""

    def test_child_inherits_parent_method(self):
        src = """
类型 动物
  函数 说话()
    返回 "汪"
类型 狗 继承自 动物
  函数 跑()
    返回 "跑"
定义 d = 狗()
d.说话()
"""
        assert run_ast(src) == "汪"
        assert_dual_equal(src)

    def test_child_overrides_parent_method(self):
        src = """
类型 图形
  函数 名称()
    返回 "图形"
类型 圆形 继承自 图形
  函数 名称()
    返回 "圆形"
定义 c = 圆形()
c.名称()
"""
        assert run_ast(src) == "圆形"
        assert_dual_equal(src)


class TestVMClassDeclTraits:
    """特征默认方法与抽象方法检查。"""

    def test_trait_default_method_available_to_class(self):
        src = """
特征 可序列化
  函数 序列化()
    返回 "json"
类型 数据
  实现 可序列化
定义 d = 数据()
d.序列化()
"""
        assert run_ast(src) == "json"
        assert_dual_equal(src)

    def test_class_method_overrides_trait_default(self):
        src = """
特征 可序列化
  函数 序列化()
    返回 "trait-default"
类型 数据
  实现 可序列化
  函数 序列化()
    返回 "class-json"
定义 d = 数据()
d.序列化()
"""
        assert run_ast(src) == "class-json"
        assert_dual_equal(src)

    def test_trait_abstract_method_must_be_implemented(self):
        src = """
特征 可绘制
  抽象 draw()
类型 圆形
  实现 可绘制
"""
        assert_dual_both_error(src, "必须实现")


class TestVMClassDeclAbstract:
    """抽象类型与抽象方法检查。"""

    def test_concrete_class_must_implement_abstract_methods(self):
        src = """
抽象 类型 形状
  抽象 获取面积()
类型 圆形 继承自 形状
  初始化(半径)
    本对象.半径 = 半径
"""
        assert_dual_both_error(src, "必须实现")

    def test_abstract_class_cannot_be_instantiated(self):
        src = """
抽象 类型 形状
  抽象 获取面积()
定义 s = 形状()
"""
        assert_dual_both_error(src, "抽象类")

    def test_abstract_subclass_implemented_method_is_callable(self):
        src = """
抽象 类型 形状
  抽象 获取面积()
类型 圆形 继承自 形状
  初始化(半径)
    本对象.半径 = 半径
  函数 获取面积()
    返回 3 * 本对象.半径 * 本对象.半径
定义 c = 圆形(2)
c.获取面积()
"""
        assert run_ast(src) == 12
        assert_dual_equal(src)


class TestVMClassDeclClosure:
    """类体方法对外层变量的闭包捕获。"""

    def test_class_method_captures_outer_variable(self):
        src = """
定义 倍数 = 3
类型 计算器
  函数 乘(x)
    返回 x * 倍数
定义 c = 计算器()
c.乘(4)
"""
        assert run_ast(src) == 12
        assert_dual_equal(src)

    def test_class_method_sees_updated_outer_variable(self):
        src = """
定义 倍数 = 3
类型 计算器
  函数 乘(x)
    返回 x * 倍数
定义 c = 计算器()
倍数 = 5
c.乘(4)
"""
        assert run_ast(src) == 20
        assert_dual_equal(src)


class TestVMClassDeclErrorClass:
    """``继承自 错误`` 的自定义错误类。"""

    def test_custom_error_class_is_catchable(self):
        src = """
类型 业务错误 继承自 错误
尝试
  抛出 业务错误("出错啦")
捕获 err
  打印(err.信息)
"""
        ast_result, ast_out = assert_dual_output_equal(src)
        assert ast_result is None
        assert "出错啦" in ast_out

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


class TestVMClassDeclCompatibility:
    """枚举原路径、类型查询与输出一致性。"""

    def test_enum_declaration_keeps_original_vm_path(self):
        src = """
枚举 颜色
  红
  绿
定义 c = 颜色.绿
匹配 c
  情况 颜色.红: 1
  情况 颜色.绿: 2
  情况 _: 0
"""
        assert run_ast(src) == 2
        assert_dual_equal(src)

    def test_取类型_query_on_instance(self):
        src = """
类型 圆形
  初始化(半径)
    本对象.半径 = 半径
定义 c = 圆形(2)
取类型(c)
"""
        assert run_ast(src) == "圆形"
        assert_dual_equal(src)

    def test_ast_vm_output_consistency_for_class_method(self):
        src = """
类型 圆形
  函数 面积()
    返回 12
定义 c = 圆形()
打印(c.面积())
"""
        ast_result, ast_out = assert_dual_output_equal(src)
        assert ast_result is None
        assert ast_out.strip() == "12"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
