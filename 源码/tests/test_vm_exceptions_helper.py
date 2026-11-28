"""
VM 异常辅助函数测试
==================

覆盖从 AST 解释器 exec_try / exec_throw 抽取出的纯函数语义。
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest

from dao.builtins.oop_types import DaoClass, DaoError
from dao.environment import Environment
from dao.errors import (
    产出信号,
    名称错误,
    运行时错误,
    继续信号,
    类型错误,
    跳出信号,
    返回信号,
    道错误,
)
from dao.vm.exceptions import (
    is_control_signal,
    matches_catch,
    normalize_raise,
    wrap_python_exception,
)


def test_normalize_raise_string():
    """字符串抛出 → 运行时错误，并保留位置与来源。"""
    source = '抛出("出错了")'
    exc = normalize_raise("出错了", line=3, column=5, source=source)
    assert isinstance(exc, 运行时错误)
    assert exc.message == "出错了"
    assert exc.line == 3
    assert exc.column == 5
    assert exc.source == source


def test_normalize_raise_dao_error_unchanged():
    """DaoError 实例直接抛出，保持对象身份与 .类型。"""
    klass = DaoClass("我的错误", None, {})
    err = DaoError("自定义错误", error_type=klass)
    assert normalize_raise(err) is err
    assert normalize_raise(err, line=9).类型 is klass


def test_normalize_raise_other_values():
    """其它值抛出 → 运行时错误(str(value))。"""
    for value in (42, [1, 2], {"键": 1}):
        exc = normalize_raise(value, line=1, column=2, source="源码")
        assert isinstance(exc, 运行时错误)
        assert exc.message == str(value)
        assert exc.line == 1 and exc.column == 2 and exc.source == "源码"


def test_wrap_python_exception_fields():
    """普通 Python 异常被包装成带中文信息的错误，字段与 错误信息 对齐。"""
    exc = ValueError("坏值")
    exc.line = 7
    exc.colno = 4
    exc.filename = "a.dao"
    exc.source = "抛出(坏值)"
    wrapped = wrap_python_exception(exc)

    assert isinstance(wrapped, 道错误)
    assert wrapped.信息 == "ValueError 坏值"
    assert wrapped.类型 == "ValueError"
    assert wrapped.行 == 7
    assert wrapped.列 == 4
    assert wrapped.文件名 == "a.dao"
    assert wrapped.来源 == "抛出(坏值)"
    assert wrapped.堆栈 == ""
    # 道错误 自身字段同步填充
    assert wrapped.message == "ValueError 坏值"
    assert wrapped.line == 7 and wrapped.column == 4
    assert wrapped.filename == "a.dao" and wrapped.source == "抛出(坏值)"


def test_wrap_python_exception_with_env_stack():
    """传入 env 时按 exec_try 的格式生成 堆栈 字符串。"""
    env = Environment()
    env.push_frame("主函数", "main.dao", 1)
    env.push_frame("测试", "main.dao", 9)
    wrapped = wrap_python_exception(TypeError("类型不对"), env)

    assert "0. 在 主函数() (文件: main.dao, 行: 1)" in wrapped.堆栈
    assert "1. 在 测试() (文件: main.dao, 行: 9)" in wrapped.堆栈
    assert wrapped.stack == env.get_stack()


def test_wrap_python_exception_explicit_params_override():
    """显式位置参数优先于异常对象自带的位置信息。"""
    exc = ValueError("坏值")
    exc.line = 7
    exc.colno = 4
    wrapped = wrap_python_exception(exc, line=20, column=30, source="显式来源")

    assert wrapped.行 == 20 and wrapped.列 == 30 and wrapped.来源 == "显式来源"
    assert wrapped.line == 20 and wrapped.column == 30


def test_wrapped_exception_is_raiseable():
    """包装结果是可抛出的 道错误（VM 侧可直接 raise）。"""
    wrapped = wrap_python_exception(ValueError("坏值"))
    with pytest.raises(道错误):
        raise wrapped


@pytest.mark.parametrize("error_type", ["异常", None, ""])
def test_matches_catch_all(error_type):
    """'异常' 或未指定类型时捕获全部，但不捕获控制流信号。"""
    assert matches_catch(ValueError("x"), error_type, Environment()) is True
    assert matches_catch(跳出信号(), error_type, Environment()) is False


def test_matches_catch_builtin_error_type():
    """内置错误类型按 isinstance 匹配，含父子类型关系。"""
    env = Environment()
    env.define("类型错误", 类型错误)
    assert matches_catch(类型错误("x"), "类型错误", env) is True
    assert matches_catch(运行时错误("x"), "类型错误", env) is False
    env.define("运行时错误", 运行时错误)
    assert matches_catch(类型错误("x"), "运行时错误", env) is True


def test_matches_catch_user_dao_error_type():
    """用户自定义 DaoError 类型按 .类型 == 类型对象 匹配（精确匹配）。"""
    env = Environment()
    first = DaoClass("一层错误", None, {})
    second = DaoClass("二层错误", first, {})
    env.define("一层错误", first)
    env.define("二层错误", second)

    assert matches_catch(DaoError("x", error_type=first), "一层错误", env) is True
    assert matches_catch(DaoError("x", error_type=second), "一层错误", env) is False
    assert matches_catch(DaoError("x", error_type=second), "二层错误", env) is True


def test_matches_catch_no_match():
    """类型不匹配时不捕获。"""
    env = Environment()
    env.define("类型错误", 类型错误)
    assert matches_catch(ValueError("x"), "类型错误", env) is False
    assert matches_catch(运行时错误("x"), "类型错误", env) is False


def test_matches_catch_lookup_in_parent_env():
    """错误类型沿作用域链查找（对齐 Environment.get）。"""
    parent = Environment()
    parent.define("类型错误", 类型错误)
    child = parent.create_child()
    assert matches_catch(类型错误("x"), "类型错误", child) is True


@pytest.mark.parametrize(
    "signal", [跳出信号(), 继续信号(), 返回信号(1), 产出信号(2)]
)
def test_control_signals_not_caught(signal):
    """四类控制流信号不属于道错误，不能被捕获。"""
    assert is_control_signal(signal) is True
    assert matches_catch(signal, "异常", Environment()) is False
    assert is_control_signal(ValueError("x")) is False
    assert is_control_signal(运行时错误("x")) is False


def test_unknown_error_type_propagates_name_error():
    """未知错误类型沿 AST 语义抛出中文 名称错误，而非静默返回 False。"""
    env = Environment()
    with pytest.raises(名称错误):
        matches_catch(ValueError("x"), "不存在的错误", env)
