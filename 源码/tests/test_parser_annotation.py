"""@ 注解解析器测试（规格 §2.4 / §3）"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest

from dao.ast_nodes import (
    AsyncFunctionDecl,
    ClassDecl,
    FunctionDecl,
    VariableDecl,
)
from dao.errors import 语法错误
from dao.lexer import Lexer
from dao.parser import Parser


def parse(source: str):
    return Parser(Lexer(source).tokenize(), source).parse()


def test_single_annotation_on_function():
    """单个注解附着在函数声明上，args/kwargs 为空"""
    src = """\
@日志
函数 greet(名字)
    返回 "你好" + 名字
"""
    program = parse(src)
    assert len(program.statements) == 1
    func = program.statements[0]
    assert isinstance(func, FunctionDecl)
    assert func.name == "greet"
    assert len(func.annotations) == 1
    ann = func.annotations[0]
    assert ann.name == "日志"
    assert ann.args == []
    assert ann.kwargs == {}
    assert (ann.line, ann.column) == (1, 1)


def test_stacked_annotations_with_args_and_kwargs():
    """多个注解按书写顺序堆叠，位置参数与关键字参数分别解析"""
    src = """\
@缓存(10)
@计时(标签="热点", 级别=2)
函数 fib(n)
    返回 n
"""
    func = parse(src).statements[0]
    assert isinstance(func, FunctionDecl)
    assert [a.name for a in func.annotations] == ["缓存", "计时"]

    cache = func.annotations[0]
    assert len(cache.args) == 1
    assert cache.args[0].value == 10
    assert cache.kwargs == {}

    timer = func.annotations[1]
    assert timer.args == []
    assert set(timer.kwargs) == {"标签", "级别"}
    assert timer.kwargs["标签"].value == "热点"
    assert timer.kwargs["级别"].value == 2


def test_annotation_on_variable_and_class():
    """注解可附着在变量与类型声明上"""
    src = """\
@标记("用户模型")
类型 用户
    定义 名字 = ""

@全局
定义 计数 = 0
"""
    stmts = parse(src).statements
    cls, var = stmts
    assert isinstance(cls, ClassDecl)
    assert cls.annotations[0].name == "标记"
    assert cls.annotations[0].args[0].value == "用户模型"

    assert isinstance(var, VariableDecl)
    assert var.annotations[0].name == "全局"


def test_annotation_on_async_function():
    """注解可附着在异步函数声明上"""
    src = """\
@日志
异步 函数 抓取(url)
    返回 url
"""
    func = parse(src).statements[0]
    assert isinstance(func, AsyncFunctionDecl)
    assert [a.name for a in func.annotations] == ["日志"]


def test_class_body_member_annotations():
    """类体内部方法与属性均可带注解"""
    src = """\
类型 人
    @日志
    定义 名字 = "无名"

    @缓存(3)
    函数 问候(self)
        返回 名字
"""
    cls = parse(src).statements[0]
    assert isinstance(cls, ClassDecl)
    attr, method = cls.body
    assert isinstance(attr, VariableDecl)
    assert [a.name for a in attr.annotations] == ["日志"]
    assert isinstance(method, FunctionDecl)
    assert [a.name for a in method.annotations] == ["缓存"]
    assert method.annotations[0].args[0].value == 3


def test_invalid_annotation_attachment_raises_chinese_error():
    """注解附着到非声明语句时报中文语法错误"""
    src = """\
@日志
如果 真
    打印("你好")
"""
    with pytest.raises(语法错误, match="注解只能用于声明"):
        parse(src)


def test_two_annotations_on_same_line_raises_chinese_error():
    """同一行写两个注解报中文语法错误"""
    src = """\
@甲 @乙
函数 f()
    返回 1
"""
    with pytest.raises(语法错误, match="同一行"):
        parse(src)
