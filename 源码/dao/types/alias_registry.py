from ..ast_nodes import (
    BasicTypeAnnotation,
    GenericTypeAnnotation,
    TypeAnnotation,
    UnionTypeAnnotation,
)
from ..errors import 类型别名错误


class TypeAliasRegistry:
    def __init__(self):
        self._aliases: dict[str, TypeAnnotation] = {}

    def define(self, name: str, target: TypeAnnotation):
        if name in self._aliases:
            raise 类型别名错误(f"类型别名 '{name}' 已存在")
        self._aliases[name] = target
        if self._has_cycle(name, target, set()):
            del self._aliases[name]
            raise 类型别名错误(f"类型别名 '{name}' 存在循环引用")

    def resolve(self, name: str) -> TypeAnnotation | None:
        return self._aliases.get(name)

    def resolve_annotation(self, annotation: TypeAnnotation) -> TypeAnnotation:
        if isinstance(annotation, BasicTypeAnnotation):
            resolved = self._aliases.get(annotation.name)
            if resolved is not None:
                return self.resolve_annotation(resolved)
            return annotation
        if isinstance(annotation, GenericTypeAnnotation):
            resolved_name = self._aliases.get(annotation.name)
            return GenericTypeAnnotation(
                name=annotation.name if resolved_name is None else annotation.name,
                type_args=[self.resolve_annotation(a) for a in annotation.type_args],
                line=annotation.line,
                column=annotation.column,
            )
        if isinstance(annotation, UnionTypeAnnotation):
            return UnionTypeAnnotation(
                types=[self.resolve_annotation(t) for t in annotation.types],
                line=annotation.line,
                column=annotation.column,
            )
        return annotation

    def _has_cycle(self, name: str, target: TypeAnnotation, visited: set[str]) -> bool:
        if name in visited:
            return True
        if isinstance(target, BasicTypeAnnotation):
            resolved = self._aliases.get(target.name)
            if resolved is not None:
                return self._has_cycle(name, resolved, visited | {target.name})
        if isinstance(target, GenericTypeAnnotation):
            for arg in target.type_args:
                if self._has_cycle(name, arg, visited):
                    return True
        if isinstance(target, UnionTypeAnnotation):
            for t in target.types:
                if self._has_cycle(name, t, visited):
                    return True
        return False

    def _check_cycle(self, name: str, target: TypeAnnotation, visited: set[str]):
        if self._has_cycle(name, target, visited):
            raise 类型别名错误(f"类型别名 '{name}' 存在循环引用")