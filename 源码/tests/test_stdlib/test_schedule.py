"""定时调度原语单元测试。"""

import os
import sys
import threading
import time

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from dao.errors import 类型错误
from dao.stdlib.schedule import (
    create_module_env,
    取消全部,
    取消调度,
    周期执行,
    延迟执行,
    等待全部,
)


@pytest.fixture(autouse=True)
def _清理调度():
    """每个测试结束后取消全部任务，避免残留后台线程干扰后续测试。"""
    yield
    取消全部()


def test_延迟执行回调一次():
    事件 = threading.Event()

    def 回调():
        事件.set()

    sid = 延迟执行(30, 回调)
    assert isinstance(sid, int) and sid > 0
    assert 事件.wait(2), "30ms 后回调未被触发"


def test_延迟执行前取消则不触发():
    事件 = threading.Event()
    sid = 延迟执行(200, 事件.set)
    assert 取消调度(sid) is True
    assert 事件.wait(0.3) is False, "已取消的调度不应触发回调"


def test_周期执行多次并可取消():
    计数 = []

    def 回调():
        计数.append(1)

    sid = 周期执行(20, 回调)
    截止 = time.monotonic() + 2
    while len(计数) < 2 and time.monotonic() < 截止:
        time.sleep(0.01)
    assert len(计数) >= 2, "周期任务在规定时间内触发次数不足"

    assert 取消调度(sid) is True
    当前 = len(计数)
    time.sleep(0.1)
    assert len(计数) == 当前, "取消后周期任务仍在触发"


def test_取消不存在的ID返回假():
    assert 取消调度(999999) is False


def test_取消全部阻止待触发任务():
    触发 = []

    sid1 = 延迟执行(60, lambda: 触发.append("一次性1"))
    sid2 = 延迟执行(60, lambda: 触发.append("一次性2"))
    sid3 = 周期执行(20, lambda: 触发.append("周期"))
    assert all(isinstance(x, int) and x > 0 for x in (sid1, sid2, sid3))

    取消全部()
    time.sleep(0.15)
    assert 触发 == [], "取消全部后仍有任务被触发"


@pytest.mark.parametrize("值", [-1, "30", True, False, 1.5, None])
def test_毫秒类型错误(值):
    with pytest.raises(类型错误):
        延迟执行(值, lambda: None)
    with pytest.raises(类型错误):
        周期执行(值, lambda: None)


@pytest.mark.parametrize("值", [None, 123, "回调", object()])
def test_回调不可调用类型错误(值):
    with pytest.raises(类型错误):
        延迟执行(10, 值)
    with pytest.raises(类型错误):
        周期执行(10, 值)


def test_导出元数据稳定():
    期望 = {"延迟执行", "周期执行", "取消调度", "取消全部", "等待全部"}
    env1 = create_module_env()
    env2 = create_module_env()
    assert set(env1.exports) == 期望
    assert set(env2.exports) == 期望
    assert set(env1.values.keys()) == 期望
    for 名字 in 期望:
        assert env1.values[名字].name == 名字
        assert env2.values[名字].name == 名字
        assert env1.values[名字].arity() == env2.values[名字].arity()
    assert env1.values["延迟执行"].arity() == 2
    assert env1.values["周期执行"].arity() == 2
    assert env1.values["取消调度"].arity() == 1
    assert env1.values["取消全部"].arity() == 0
    assert env1.values["等待全部"].arity() == 0


def test_等待全部():
    结果 = []
    延迟执行(20, lambda: 结果.append(1))
    延迟执行(20, lambda: 结果.append(2))
    等待全部()
    assert sorted(结果) == [1, 2]


def test_interpreter_道语言函数回调():
    """真实 Interpreter + 道语言函数作为回调，覆盖 call_function 路径。"""
    from dao.builtins.callables import BuiltinFunction, DaoFunction
    from dao.interpreter import Interpreter
    from dao.lexer import Lexer
    from dao.parser import Parser
    from dao.stdlib.loader import StdlibLoader
    from dao.stdlib.registry import register_module

    register_module("调度", create_module_env)
    StdlibLoader.STDLIB_NAMES = None

    完成 = threading.Event()

    def 标记():
        完成.set()

    interp = Interpreter()
    interp.global_env.define("标记", BuiltinFunction("标记", 标记, 0))
    源码 = """
从 调度 导入 延迟执行

函数 我的回调()
    标记()

延迟执行(30, 我的回调)
"""
    ast = Parser(Lexer(源码).tokenize()).parse()
    interp.execute(ast)

    回调 = interp.global_env.get("我的回调")
    assert isinstance(回调, DaoFunction)
    assert 完成.wait(2), "道语言回调未通过 interpreter.call_function 路径触发"
