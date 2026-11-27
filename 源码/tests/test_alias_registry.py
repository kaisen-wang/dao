"""类型别名注册表：定义、解析与循环检测。"""

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from dao.ast_nodes import (
    BasicTypeAnnotation,
    GenericTypeAnnotation,
    UnionTypeAnnotation,
)
from dao.errors import 类型别名错误
from dao.types.alias_registry import TypeAliasRegistry


class TestTypeAliasRegistry:
    def test_define_and_resolve(self):
        registry = TypeAliasRegistry()
        target = BasicTypeAnnotation(name="数值")
        registry.define("用户ID", target)
        resolved = registry.resolve("用户ID")
        assert resolved is not None
        assert resolved.name == "数值"

    def test_resolve_nonexistent(self):
        registry = TypeAliasRegistry()
        assert registry.resolve("不存在") is None

    def test_redefine_error(self):
        registry = TypeAliasRegistry()
        registry.define("用户ID", BasicTypeAnnotation(name="数值"))
        try:
            registry.define("用户ID", BasicTypeAnnotation(name="文本"))
            assert False, "应该抛出类型别名错误"
        except 类型别名错误:
            pass

    def test_resolve_annotation_basic(self):
        registry = TypeAliasRegistry()
        registry.define("用户ID", BasicTypeAnnotation(name="数值"))
        ann = BasicTypeAnnotation(name="用户ID")
        resolved = registry.resolve_annotation(ann)
        assert isinstance(resolved, BasicTypeAnnotation)
        assert resolved.name == "数值"

    def test_resolve_annotation_unknown(self):
        registry = TypeAliasRegistry()
        ann = BasicTypeAnnotation(name="未知类型")
        resolved = registry.resolve_annotation(ann)
        assert isinstance(resolved, BasicTypeAnnotation)
        assert resolved.name == "未知类型"

    def test_resolve_annotation_generic(self):
        registry = TypeAliasRegistry()
        registry.define("用户ID", BasicTypeAnnotation(name="数值"))
        ann = GenericTypeAnnotation(name="列表", type_args=[BasicTypeAnnotation(name="用户ID")])
        resolved = registry.resolve_annotation(ann)
        assert isinstance(resolved, GenericTypeAnnotation)
        assert resolved.type_args[0].name == "数值"

    def test_resolve_annotation_union(self):
        registry = TypeAliasRegistry()
        registry.define("ID", BasicTypeAnnotation(name="数值"))
        ann = UnionTypeAnnotation(types=[BasicTypeAnnotation(name="ID"), BasicTypeAnnotation(name="文本")])
        resolved = registry.resolve_annotation(ann)
        assert isinstance(resolved, UnionTypeAnnotation)
        assert resolved.types[0].name == "数值"

    def test_cycle_detection(self):
        registry = TypeAliasRegistry()
        registry.define("A", BasicTypeAnnotation(name="B"))
        try:
            registry.define("B", BasicTypeAnnotation(name="A"))
            assert False, "应该抛出类型别名错误"
        except 类型别名错误:
            pass

    def test_self_reference_detection(self):
        registry = TypeAliasRegistry()
        try:
            registry.define("A", BasicTypeAnnotation(name="A"))
            assert False, "应该抛出类型别名错误"
        except 类型别名错误:
            pass

    def test_chained_resolve(self):
        registry = TypeAliasRegistry()
        registry.define("用户ID", BasicTypeAnnotation(name="数值"))
        registry.define("项目ID", BasicTypeAnnotation(name="数值"))
        ann = BasicTypeAnnotation(name="用户ID")
        resolved = registry.resolve_annotation(ann)
        assert resolved.name == "数值"


class TestTypeAliasRegistryChineseDiagnostics:
    def test_cycle_error_message_is_chinese(self):
        registry = TypeAliasRegistry()
        registry.define("A", BasicTypeAnnotation(name="B"))
        try:
            registry.define("B", BasicTypeAnnotation(name="A"))
            assert False, "应该抛出类型别名错误"
        except 类型别名错误 as exc:
            assert "循环" in exc.message
            assert "类型别名" in exc.message

    def test_self_reference_error_message_names_alias(self):
        registry = TypeAliasRegistry()
        try:
            registry.define("循环类型", BasicTypeAnnotation(name="循环类型"))
            assert False, "应该抛出类型别名错误"
        except 类型别名错误 as exc:
            assert "循环类型" in exc.message

    def test_alias_to_generic_type(self):
        registry = TypeAliasRegistry()
        target = GenericTypeAnnotation(
            name="列表", type_args=[BasicTypeAnnotation(name="数值")]
        )
        registry.define("数值列表", target)
        resolved = registry.resolve("数值列表")
        assert isinstance(resolved, GenericTypeAnnotation)
        assert resolved.name == "列表"
        assert resolved.type_args[0].name == "数值"

    def test_nested_generic_alias_resolution(self):
        registry = TypeAliasRegistry()
        registry.define("ID", BasicTypeAnnotation(name="数值"))
        ann = GenericTypeAnnotation(
            name="字典",
            type_args=[
                BasicTypeAnnotation(name="文本"),
                GenericTypeAnnotation(
                    name="列表", type_args=[BasicTypeAnnotation(name="ID")]
                ),
            ],
        )
        resolved = registry.resolve_annotation(ann)
        assert isinstance(resolved, GenericTypeAnnotation)
        nested = resolved.type_args[1]
        assert isinstance(nested, GenericTypeAnnotation)
        assert nested.type_args[0].name == "数值"
