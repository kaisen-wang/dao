"""
@ 注解 AST 节点测试
==================

仅测试 ast_nodes 层的节点定义与构造，不依赖词法器/解析器（由其它环节负责）。
"""

import os
import sys
from dataclasses import fields

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from dao.ast_nodes import (
    AbstractDecl,
    Annotation,
    AsyncFunctionDecl,
    ClassDecl,
    EnumDecl,
    FunctionDecl,
    NumberLiteral,
    StringLiteral,
    TraitDecl,
    VariableDecl,
)

DECL_TYPES = (
    VariableDecl,
    FunctionDecl,
    AsyncFunctionDecl,
    ClassDecl,
    AbstractDecl,
    EnumDecl,
    TraitDecl,
)


def test_annotation_defaults():
    """Annotation 三个业务字段均有正确的默认值"""
    ann = Annotation()
    assert ann.name == ""
    assert ann.args == []
    assert ann.kwargs == {}
    assert [f.name for f in fields(Annotation)] == [
        "line", "column", "name", "args", "kwargs"
    ]


def test_annotation_with_args_and_kwargs():
    """Annotation 可携带位置参数与关键字参数表达式"""
    ann = Annotation(
        name="缓存",
        args=[NumberLiteral(value=10)],
        kwargs={"标签": StringLiteral(value="热点")},
    )
    assert ann.name == "缓存"
    assert ann.args[0].value == 10
    assert ann.kwargs["标签"].value == "热点"


def test_declarations_have_independent_annotations():
    """7 类声明节点均在末尾追加 annotations，且各实例互不共享列表"""
    for cls in DECL_TYPES:
        names = [f.name for f in fields(cls)]
        assert names[-1] == "annotations", cls.__name__

        a = cls()
        b = cls()
        assert a.annotations == []
        assert a.annotations is not b.annotations

        ann = Annotation(name="日志")
        node = cls(annotations=[ann])
        assert node.annotations == [ann]


def test_existing_positional_construction_preserved():
    """原有字段顺序未改变，位置参数构造仍然可用"""
    v = VariableDecl(1, 2, "x", NumberLiteral(value=3), False, False, None)
    assert (v.line, v.column, v.name) == (1, 2, "x")
    assert v.value.value == 3
    assert v.is_constant is False
    assert v.annotations == []
