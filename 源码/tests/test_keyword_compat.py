"""
上下文关键字兼容性测试
======================

覆盖高频中文词汇作为变量名/参数名时的可用性，以及保留字的结构语法不回退。
"""

import io
import os
import sys
from contextlib import redirect_stdout

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from dao.ast_nodes import (
    Assignment,
    AwaitAllExpr,
    AwaitExpr,
    ChannelExpr,
    ForRangeStmt,
    FunctionDecl,
    ImportStmt,
    LogicBlock,
    VariableDecl,
)
from dao.errors import 语法错误
from dao.interpreter import Interpreter
from dao.lexer import Lexer
from dao.parser import Parser

# 这些高频词在「变量名/参数名」位置应可用，同时保留各自的结构语法
高频词 = [
    "步长", "设置", "默认", "静态", "获取", "全部", "规则", "事实",
    "异步", "等待", "通道", "发送", "接收", "选择", "超时",
]


def parse(source: str):
    tokens = Lexer(source).tokenize()
    return Parser(tokens, source).parse()


def run(source: str) -> str:
    ast = parse(source)
    interpreter = Interpreter()
    output = io.StringIO()
    with redirect_stdout(output):
        interpreter.execute(ast)
    return output.getvalue()


# ---------- 三个真实案例 ----------


def test_真实案例_函数参数步长():
    """函数 加(步长=1) 应能解析并执行，步长可在函数体内引用"""
    source = """函数 加(步长=1)
    返回 步长
打印(加())
打印(加(3))
"""
    ast = parse(source)
    assert isinstance(ast.statements[0], FunctionDecl)
    assert ast.statements[0].params == ["步长"]
    assert run(source).split() == ["1", "3"]


def test_真实案例_变量声明设置():
    """定义 设置 = 1 应能解析并执行"""
    source = "定义 设置 = 1\n打印(设置)\n"
    ast = parse(source)
    assert isinstance(ast.statements[0], VariableDecl)
    assert ast.statements[0].name == "设置"
    assert run(source).strip() == "1"


def test_真实案例_从异步导入():
    """从 异步 导入 X 必须路由到导入语句，而不是遍历语句"""
    source = "从 异步 导入 创建任务\n"
    ast = parse(source)
    stmt = ast.statements[0]
    assert isinstance(stmt, ImportStmt)
    assert stmt.is_from_import is True
    assert stmt.module_path == "异步"
    assert stmt.names[0][0] == "创建任务"


# ---------- 赋值目标 ----------


def test_设置可作为赋值目标():
    source = "定义 设置 = 1\n设 设置 = 9\n打印(设置)\n"
    ast = parse(source)
    assert isinstance(ast.statements[1], Assignment)
    assert run(source).strip() == "9"


# ---------- 高频词作变量名（解析 + 执行） ----------


@pytest.mark.parametrize("名称", 高频词)
def test_高频词作变量名(名称):
    source = f"定义 {名称} = 42\n打印({名称})\n"
    ast = parse(source)
    assert isinstance(ast.statements[0], VariableDecl)
    assert ast.statements[0].name == 名称
    assert run(source).strip() == "42"


# ---------- 高频词作参数名（解析 + 执行） ----------


@pytest.mark.parametrize("名称", 高频词)
def test_高频词作参数名(名称):
    source = f"函数 取值({名称}=7)\n    返回 {名称}\n打印(取值())\n"
    ast = parse(source)
    fn = ast.statements[0]
    assert isinstance(fn, FunctionDecl)
    assert 名称 in fn.params
    assert run(source).strip() == "7"


def test_高频词作循环变量名():
    source = "遍历 步长 在 [1, 2]\n    打印(步长)\n"
    assert run(source).split() == ["1", "2"]


# ---------- 保留字诊断 ----------


@pytest.mark.parametrize(
    ("源码", "期望片段"),
    [
        ("定义 定义 = 1\n", "“定义”是保留关键字，不能用作变量名"),
        ("设 定义 = 1\n", "“定义”是保留关键字，不能用作变量名"),
        ("函数 f(如果=1)\n    返回 1\n", "“如果”是保留关键字，不能用作参数名"),
    ],
)
def test_硬保留字报错含明确提示(源码, 期望片段):
    with pytest.raises(语法错误) as exc_info:
        parse(源码)
    assert 期望片段 in str(exc_info.value)


# ---------- 结构语法不回退 ----------


def test_遍历步长仍为结构语法():
    source = "遍历 i 从 1 到 5 步长 2\n    打印(i)\n"
    ast = parse(source)
    stmt = ast.statements[0]
    assert isinstance(stmt, ForRangeStmt)
    assert stmt.step.value == 2
    assert run(source).split() == ["1", "3", "5"]


def test_获取设置属性访问器仍可用():
    source = """类型 计数器
    初始化()
        本对象._值 = 0

    获取 值()
        返回 本对象._值

    设置 值(v)
        本对象._值 = v

定义 c = 计数器()
c.值 = 10
打印(c.值)
"""
    assert run(source).strip() == "10"


def test_事实规则仍为逻辑块语法():
    source = """逻辑 家
    事实: 父母("甲", "乙")
    规则: 祖孙(?祖, ?孙) 如果 父母(?祖, ?孙)
"""
    block = parse(source).statements[0]
    assert isinstance(block, LogicBlock)
    assert len(block.facts) == 1
    assert len(block.rules) == 1


def test_通道构造表达式仍可用():
    source = "定义 ch = 通道(2)\n"
    stmt = parse(source).statements[0]
    assert isinstance(stmt.value, ChannelExpr)


def test_全部等待表达式仍可用():
    source = "定义 结果 = 全部(甲, 乙)\n"
    stmt = parse(source).statements[0]
    assert isinstance(stmt.value, AwaitAllExpr)


def test_等待前缀表达式仍可用():
    source = "定义 结果 = 等待 任务\n"
    stmt = parse(source).statements[0]
    assert isinstance(stmt.value, AwaitExpr)
