from dataclasses import dataclass, field

from ..ast_nodes import (
    BasicTypeAnnotation,
    BinaryOp,
    BooleanLiteral,
    DictLiteral,
    Expression,
    FunctionDecl,
    Identifier,
    ListLiteral,
    NullLiteral,
    NumberLiteral,
    Program,
    SetLiteral,
    StringLiteral,
    TupleLiteral,
    TypeAnnotation,
    UnionTypeAnnotation,
    VariableDecl,
)


@dataclass
class TypeErrorReport:
    message: str
    line: int = 0
    column: int = 0


class TypeInferenceEngine:
    def __init__(self):
        self._var_types: dict[str, TypeAnnotation] = {}
        self._func_return_types: dict[str, TypeAnnotation] = {}
        self.reports: list[TypeErrorReport] = []

    def check(self, program: Program) -> list[TypeErrorReport]:
        self.reports = []
        self._var_types = {}
        self._func_return_types = {}
        for stmt in program.statements:
            self._check_statement(stmt)
        return self.reports

    def _check_statement(self, stmt):
        if isinstance(stmt, VariableDecl):
            self._check_variable_decl(stmt)
        elif isinstance(stmt, FunctionDecl):
            self._check_function_decl(stmt)

    def _check_variable_decl(self, stmt: VariableDecl):
        inferred = self._infer_expression(stmt.value)
        if inferred is not None:
            self._var_types[stmt.name] = inferred
        if stmt.type_annotation is not None and inferred is not None:
            if not self._is_compatible(stmt.type_annotation, inferred):
                self.reports.append(TypeErrorReport(
                    message=f"变量 '{stmt.name}' 声明类型为 {self._type_name(stmt.type_annotation)}，但推断类型为 {self._type_name(inferred)}",
                    line=stmt.line,
                    column=stmt.column,
                ))

    def _check_function_decl(self, stmt: FunctionDecl):
        if stmt.body:
            for s in stmt.body:
                if hasattr(s, 'value') and s.value is not None:
                    ret_type = self._infer_expression(s.value)
                    if ret_type is not None:
                        self._func_return_types[stmt.name] = ret_type
                        break
            for s in stmt.body:
                self._check_statement(s)
        if stmt.return_type is not None and stmt.name in self._func_return_types:
            inferred_ret = self._func_return_types[stmt.name]
            if not self._is_compatible(stmt.return_type, inferred_ret):
                self.reports.append(TypeErrorReport(
                    message=f"函数 '{stmt.name}' 声明返回类型为 {self._type_name(stmt.return_type)}，但推断返回类型为 {self._type_name(inferred_ret)}",
                    line=stmt.line,
                    column=stmt.column,
                ))
        for i, param in enumerate(stmt.params):
            if i < len(stmt.param_type_annotations) and stmt.param_type_annotations[i] is not None:
                self._var_types[param] = stmt.param_type_annotations[i]

    def _infer_expression(self, expr: Expression) -> TypeAnnotation | None:
        if isinstance(expr, NumberLiteral):
            return BasicTypeAnnotation(name="数值")
        if isinstance(expr, StringLiteral):
            return BasicTypeAnnotation(name="文本")
        if isinstance(expr, BooleanLiteral):
            return BasicTypeAnnotation(name="布尔")
        if isinstance(expr, NullLiteral):
            return BasicTypeAnnotation(name="空")
        if isinstance(expr, ListLiteral):
            return BasicTypeAnnotation(name="列表")
        if isinstance(expr, DictLiteral):
            return BasicTypeAnnotation(name="字典")
        if isinstance(expr, TupleLiteral):
            return BasicTypeAnnotation(name="元组")
        if isinstance(expr, SetLiteral):
            return BasicTypeAnnotation(name="集合")
        if isinstance(expr, Identifier):
            return self._var_types.get(expr.name)
        if isinstance(expr, BinaryOp):
            left = self._infer_expression(expr.left)
            right = self._infer_expression(expr.right)
            op = expr.operator
            if op in ("+", "-", "*", "/", "//", "%", "**"):
                if left and left.name == "数值" and right and right.name == "数值":
                    return BasicTypeAnnotation(name="数值")
                if op == "+" and left and left.name == "文本" and right and right.name == "文本":
                    return BasicTypeAnnotation(name="文本")
            if op in ("并且", "或者", "==", "!=", "<", ">", "<=", ">="):
                return BasicTypeAnnotation(name="布尔")
        return None

    def _is_compatible(self, declared: TypeAnnotation, inferred: TypeAnnotation) -> bool:
        if isinstance(declared, BasicTypeAnnotation) and declared.name == "任意":
            return True
        if isinstance(declared, UnionTypeAnnotation):
            return any(self._is_compatible(t, inferred) for t in declared.types)
        if isinstance(inferred, UnionTypeAnnotation):
            return any(self._is_compatible(declared, t) for t in inferred.types)
        if isinstance(declared, BasicTypeAnnotation) and isinstance(inferred, BasicTypeAnnotation):
            return declared.name == inferred.name
        return True

    def _type_name(self, ann: TypeAnnotation) -> str:
        if isinstance(ann, BasicTypeAnnotation):
            return ann.name
        if isinstance(ann, UnionTypeAnnotation):
            return " | ".join(self._type_name(t) for t in ann.types)
        return str(type(ann).__name__)