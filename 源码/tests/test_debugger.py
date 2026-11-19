"""
调试器基础层测试
================

覆盖：断点设置/删除、断点命中、单步计数、变量查看、关闭时行为不变、
暂停回调中断、断点文件过滤、块内语句钩子覆盖。
"""

import os
import sys
from contextlib import redirect_stdout
from io import StringIO

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

import pytest

from dao.debug import DebugExecutor, Debugger, 调试暂停, 调试指令
from dao.interpreter import Interpreter
from dao.lexer import Lexer
from dao.parser import Parser


源程序 = '定义 a = 1\n打印(a)\n定义 b = a + 2\n打印(b)\n'


def 解析(src: str):
    return Parser(Lexer(src).tokenize()).parse()


def 调试运行(src: str, 调试器: Debugger, 文件名: str = ""):
    执行器 = DebugExecutor(调试器, 文件名=文件名)
    return 执行器.execute(解析(src), source=src)


def 静默调试运行(src: str, 调试器: Debugger, 文件名: str = ""):
    with redirect_stdout(StringIO()):
        return 调试运行(src, 调试器, 文件名)


def test_断点设置与删除():
    调试器 = Debugger()
    assert 调试器.列出断点() == []

    bp = 调试器.设置断点("demo.道", 3)
    assert bp.文件 == "demo.道" and bp.行号 == 3 and bp.启用 is True
    assert len(调试器.列出断点()) == 1

    # 重复设置不产生副本
    调试器.设置断点("demo.道", 3)
    assert len(调试器.列出断点()) == 1

    # 空文件名表示通配任意文件
    调试器.设置断点("", 5)
    assert len(调试器.列出断点()) == 2

    assert 调试器.删除断点("demo.道", 3) is True
    assert len(调试器.列出断点()) == 1
    assert 调试器.删除断点("demo.道", 3) is False

    调试器.清空断点()
    assert 调试器.列出断点() == []

    with pytest.raises(ValueError):
        调试器.设置断点("demo.道", 0)


def test_断点命中():
    调试器 = Debugger()
    调试器.设置断点("", 2)

    输出 = StringIO()
    with redirect_stdout(输出):
        调试运行(源程序, 调试器, 文件名="t.道")

    # 命中只记录事件，不改变程序输出
    assert 输出.getvalue() == "1\n3\n"
    assert len(调试器.事件列表) == 1
    事件 = 调试器.最后事件
    assert 事件.行号 == 2
    assert 事件.文件 == "t.道"
    assert 事件.语句类型 == "ExpressionStmt"
    assert 事件.步数 == 2
    assert 事件.列号 >= 1


def test_单步执行计数():
    调试器 = Debugger()
    调试器.单步 = True

    静默调试运行(源程序, 调试器)

    assert 调试器.执行计数 == 4
    assert len(调试器.事件列表) == 4
    assert [e.行号 for e in 调试器.事件列表] == [1, 2, 3, 4]
    # 每条语句恰好触发一次（含表达式语句）
    assert [e.步数 for e in 调试器.事件列表] == [1, 2, 3, 4]


def test_变量查看():
    调试器 = Debugger()
    # 第 4 行为 打印(b)，执行前 a、b 均已定义
    调试器.设置断点("", 4)

    静默调试运行(源程序, 调试器)

    assert 调试器.查看变量("a") == 1
    assert 调试器.查看变量("b") == 3
    变量表 = 调试器.查看变量()
    assert 变量表["a"] == 1 and 变量表["b"] == 3
    with pytest.raises(Exception):
        调试器.查看变量("不存在的变量")


def test_调试不开启时行为不变():
    # 原生解释器基准输出
    基准 = StringIO()
    with redirect_stdout(基准):
        Interpreter().execute(解析(源程序), source=源程序)

    # 1) 调试器总开关关闭
    关闭 = Debugger()
    关闭.启用 = False
    输出1 = StringIO()
    with redirect_stdout(输出1):
        调试运行(源程序, 关闭)
    assert 输出1.getvalue() == 基准.getvalue()
    assert 关闭.执行计数 == 0
    assert 关闭.事件列表 == []

    # 2) 调试器启用但既无断点又未开单步
    空配置 = Debugger()
    输出2 = StringIO()
    with redirect_stdout(输出2):
        调试运行(源程序, 空配置)
    assert 输出2.getvalue() == 基准.getvalue()
    assert 空配置.事件列表 == []


def test_暂停回调中断执行():
    调试器 = Debugger()
    调试器.设置断点("", 3)
    捕获 = []

    def 回调(事件):
        捕获.append(事件.行号)
        return 调试指令.暂停

    调试器.暂停回调 = 回调

    输出 = StringIO()
    with redirect_stdout(输出), pytest.raises(调试暂停) as 异常:
        调试运行(源程序, 调试器)

    assert 捕获 == [3]
    assert 异常.value.事件.行号 == 3
    # 第 3 行前中断：仅第 2 行的 打印(a) 已执行
    assert 输出.getvalue() == "1\n"


def test_断点文件过滤():
    调试器 = Debugger()
    调试器.设置断点("a.道", 2)

    静默调试运行(源程序, 调试器, 文件名="b.道")
    assert 调试器.事件列表 == []

    调试器.复位()
    静默调试运行(源程序, 调试器, 文件名="a.道")
    assert len(调试器.事件列表) == 1
    assert 调试器.最后事件.行号 == 2


def test_块内语句钩子覆盖():
    # 块内 ExpressionStmt 不经过 exec_statement，需由 _exec_block 钩子覆盖
    源 = '定义 x = 5\n如果 x > 3\n    打印("大")\n'
    调试器 = Debugger()
    调试器.设置断点("", 3)

    输出 = StringIO()
    with redirect_stdout(输出):
        调试运行(源, 调试器)

    assert 输出.getvalue() == "大\n"
    assert len(调试器.事件列表) == 1
    assert 调试器.最后事件.行号 == 3
    assert 调试器.最后事件.语句类型 == "ExpressionStmt"
