"""道语言的静态类型检查器。

设计原则：
- 只对"显式写了类型注解"的代码做严格检查；未注解的代码保持动态语义，不报错。
- 所有诊断都带行列位置，并使用中文描述。
- 类型别名、泛型参数、导入签名都参与比较，不再对未知情形一律放行。
"""

import os
from dataclasses import dataclass

from ..ast_nodes import (
    AbstractDecl,
    Assignment,
    BasicTypeAnnotation,
    BinaryOp,
    BooleanLiteral,
    ClassDecl,
    DictLiteral,
    EnumDecl,
    ExportStmt,
    Expression,
    ExpressionStmt,
    ForInStmt,
    ForRangeStmt,
    FunctionCall,
    FunctionDecl,
    FunctionTypeAnnotation,
    GenericTypeAnnotation,
    Identifier,
    IfStmt,
    ImportStmt,
    IndexAccess,
    ListLiteral,
    MacroDefinition,
    NullLiteral,
    NumberLiteral,
    OptionalTypeAnnotation,
    Program,
    ReturnStmt,
    SetLiteral,
    StringLiteral,
    SyncStmt,
    TraitDecl,
    TupleLiteral,
    TypeAliasDecl,
    TypeAnnotation,
    UnaryOp,
    UnionTypeAnnotation,
    VariableDecl,
    WhileStmt,
    TryStmt,
)
from ..errors import 类型别名错误

from .alias_registry import TypeAliasRegistry


@dataclass
class TypeErrorReport:
    """一条中文类型诊断。line/column 为 1 基源码位置。"""

    message: str
    line: int = 0
    column: int = 0

    def __str__(self) -> str:
        return f"类型错误 [行 {self.line}, 列 {self.column}]: {self.message}"


# 视为动态类型的名字：它们可以兼容任何类型，避免误报。
_DYNAMIC_NAMES = {"任意", "动态", "未知"}
_NULL_NAME = "空"

# 泛型名归一化：允许英文别名与中文名等价。
_GENERIC_NAMES = {
    "列表": "列表", "list": "列表",
    "字典": "字典", "dict": "字典",
    "集合": "集合", "set": "集合",
    "元组": "元组", "tuple": "元组",
    "可选": "可选", "optional": "可选",
}


def _is_dynamic(ann: TypeAnnotation | None) -> bool:
    return isinstance(ann, BasicTypeAnnotation) and ann.name in _DYNAMIC_NAMES


def _is_null(ann: TypeAnnotation | None) -> bool:
    return isinstance(ann, BasicTypeAnnotation) and ann.name == _NULL_NAME


def _generic_kind(name: str) -> str:
    return _GENERIC_NAMES.get(name, name)


class TypeInferenceEngine:
    """遍历 AST 做类型推断并产生中文类型诊断。"""

    def __init__(self, base_dir: str | None = None, search_paths: list[str] | None = None):
        # base_dir 用于把「导入 工具.数学」解析到同项目的 工具/数学.道
        self.base_dir = base_dir or os.getcwd()
        self.search_paths = list(search_paths or [])
        self._var_types: dict[str, TypeAnnotation] = {}
        self._declared_var_types: dict[str, TypeAnnotation] = {}
        # name -> (参数注解列表, 返回注解, 是否有可变参数)
        self._func_signatures: dict[str, tuple[list[TypeAnnotation | None], TypeAnnotation | None, bool]] = {}
        self._func_return_types: dict[str, TypeAnnotation] = {}
        self.reports: list[TypeErrorReport] = []
        self._aliases = TypeAliasRegistry()
        self._checking_modules: set[str] = set()
        self._alias_error = False

    # ------------------------------------------------------------------
    # 入口
    # ------------------------------------------------------------------

    def check(self, program: Program, base_dir: str | None = None) -> list[TypeErrorReport]:
        if base_dir is not None:
            self.base_dir = base_dir
        self.reports = []
        self._var_types = {}
        self._declared_var_types = {}
        self._func_signatures = {}
        self._func_return_types = {}
        self._aliases = TypeAliasRegistry()
        self._checking_modules = set()
        self._alias_error = False
        self._check_program(program, module_key=f"<根模块:{id(program)}>")
        return self.reports

    def _check_program(self, program: Program, module_key: str):
        if module_key in self._checking_modules:
            return
        self._checking_modules.add(module_key)

        # 每个模块拥有独立的别名空间，避免不同模块的别名重名互相干扰。
        outer_aliases = self._aliases
        outer_alias_error = self._alias_error
        self._aliases = TypeAliasRegistry()
        self._alias_error = False
        try:
            self._register_aliases(program)
            self._check_imports(program)
            for stmt in program.statements:
                self._check_statement(stmt)
        finally:
            self._aliases = outer_aliases
            self._alias_error = outer_alias_error

    # ------------------------------------------------------------------
    # 类型别名
    # ------------------------------------------------------------------

    def _register_aliases(self, program: Program):
        for stmt in program.statements:
            if isinstance(stmt, TypeAliasDecl):
                try:
                    self._aliases.define(stmt.name, stmt.target_type)
                except 类型别名错误 as exc:
                    self._alias_error = True
                    self.reports.append(TypeErrorReport(
                        message=f"类型别名错误：{exc.message}",
                        line=stmt.line,
                        column=stmt.column,
                    ))

    def _resolve_annotation(self, ann: TypeAnnotation | None) -> TypeAnnotation | None:
        """把注解中的类型别名展开。解析失败时退回原注解，不重复报诊断。"""
        if ann is None:
            return None
        try:
            resolved = self._aliases.resolve_annotation(ann)
        except 类型别名错误:
            return ann

        # 泛型名本身也可能是别名，例如：类型别名 整数列 = 列表
        if isinstance(resolved, GenericTypeAnnotation):
            named = self._aliases.resolve(resolved.name)
            if isinstance(named, GenericTypeAnnotation):
                resolved = GenericTypeAnnotation(
                    name=named.name,
                    type_args=resolved.type_args,
                    line=resolved.line,
                    column=resolved.column,
                )
        return resolved

    # ------------------------------------------------------------------
    # 跨模块导入
    # ------------------------------------------------------------------

    def _check_imports(self, program: Program):
        for stmt in program.statements:
            if isinstance(stmt, ImportStmt):
                self._check_import(stmt)

    def _resolve_module_file(self, module_path: str) -> str | None:
        relative = module_path.replace(".", os.sep) + ".道"
        for directory in [self.base_dir] + self.search_paths:
            candidate = os.path.join(directory, relative)
            if os.path.isfile(candidate):
                return candidate
        return None

    def _check_import(self, stmt: ImportStmt):
        # 标准库模块没有同项目 .道 源码，签名由运行时提供，跳过。
        try:
            from ..stdlib.loader import StdlibLoader
            if StdlibLoader.is_stdlib_module(stmt.module_path):
                return
        except ImportError:
            pass

        path = self._resolve_module_file(stmt.module_path)
        if path is None:
            return  # 第三方/已安装模块：无源码可查，保持动态兼容

        from ..lexer import Lexer
        from ..parser import Parser

        with open(path, "r", encoding="utf-8") as handle:
            source = handle.read()
        module_ast = Parser(Lexer(source, path).tokenize()).parse()

        # 检查模块自身（含它自己的导入与别名），但只暴露其顶层符号。
        outer_vars = dict(self._var_types)
        outer_declared = dict(self._declared_var_types)
        outer_funcs = dict(self._func_signatures)
        outer_returns = dict(self._func_return_types)
        self._check_program(module_ast, module_key=os.path.abspath(path))

        exports, definitions = self._module_symbols(module_ast)
        module_vars = {
            name: self._var_types[name]
            for name in definitions if name in self._var_types
        }
        module_signatures = {
            name: self._func_signatures[name]
            for name in definitions if name in self._func_signatures
        }
        module_returns = {
            name: self._func_return_types[name]
            for name in definitions if name in self._func_return_types
        }

        # 恢复当前模块的作用域，只把被导入的符号带回来。
        self._var_types = outer_vars
        self._declared_var_types = outer_declared
        self._func_signatures = outer_funcs
        self._func_return_types = outer_returns

        if stmt.is_from_import:
            for name, alias in stmt.names:
                if exports and name not in exports:
                    self.reports.append(TypeErrorReport(
                        message=f"模块 '{stmt.module_path}' 中没有导出 '{name}'",
                        line=stmt.line, column=stmt.column,
                    ))
                    continue
                if name not in definitions:
                    self.reports.append(TypeErrorReport(
                        message=f"模块 '{stmt.module_path}' 中没有定义 '{name}'",
                        line=stmt.line, column=stmt.column,
                    ))
                    continue
                bound = alias or name
                if name in module_signatures:
                    self._func_signatures[bound] = module_signatures[name]
                if name in module_returns:
                    self._func_return_types[bound] = module_returns[name]
                if name in module_vars:
                    self._var_types[bound] = module_vars[name]
        else:
            # 「导入 模块」：整体导入，导出符号通过限定名使用；
            # 这里只恢复模块中已被检查过的签名，供跨模块调用检查使用。
            prefix = (stmt.alias or stmt.module_path.split(".")[-1]) + "."
            for name, signature in module_signatures.items():
                if not exports or name in exports:
                    self._func_signatures[prefix + name] = signature
            for name, ret in module_returns.items():
                if not exports or name in exports:
                    self._func_return_types[prefix + name] = ret

    @staticmethod
    def _module_symbols(program: Program) -> tuple[set[str], set[str]]:
        exports: set[str] = set()
        definitions: set[str] = set()
        for stmt in program.statements:
            if isinstance(stmt, ExportStmt):
                exports.update(stmt.names)
            elif isinstance(stmt, (VariableDecl, FunctionDecl, ClassDecl, EnumDecl,
                                   TraitDecl, AbstractDecl, TypeAliasDecl, MacroDefinition)):
                definitions.add(stmt.name)
        return exports, definitions

    # ------------------------------------------------------------------
    # 语句检查
    # ------------------------------------------------------------------

    def _check_statement(self, stmt):
        if isinstance(stmt, VariableDecl):
            self._check_variable_decl(stmt)
        elif isinstance(stmt, FunctionDecl):
            self._check_function_decl(stmt)
        elif isinstance(stmt, Assignment):
            self._check_assignment(stmt)
        elif isinstance(stmt, ExpressionStmt):
            self._infer_expression(stmt.expression)
        elif isinstance(stmt, IfStmt):
            for s in stmt.body:
                self._check_statement(s)
            for _, body in stmt.elif_clauses:
                for s in body:
                    self._check_statement(s)
            for s in stmt.else_body:
                self._check_statement(s)
        elif isinstance(stmt, (WhileStmt, ForInStmt, ForRangeStmt, SyncStmt)):
            for s in stmt.body:
                self._check_statement(s)
        elif isinstance(stmt, TryStmt):
            for s in stmt.try_body:
                self._check_statement(s)
            for catch in stmt.catches:
                for s in catch.get("catch_body", []):
                    self._check_statement(s)
            for s in stmt.finally_body:
                self._check_statement(s)

    def _check_variable_decl(self, stmt: VariableDecl):
        inferred = self._infer_expression(stmt.value)
        if inferred is not None:
            self._var_types[stmt.name] = inferred
        if stmt.type_annotation is None or self._alias_error:
            return
        declared = self._resolve_annotation(stmt.type_annotation)
        self._declared_var_types[stmt.name] = declared
        if inferred is None:
            return  # 推断不出时按动态类型处理，避免误报
        if not self._is_compatible(declared, inferred):
            self.reports.append(TypeErrorReport(
                message=(
                    f"变量 '{stmt.name}' 声明类型为 {self._type_name(declared)}，"
                    f"但推断类型为 {self._type_name(inferred)}"
                ),
                line=stmt.line,
                column=stmt.column,
            ))

    def _check_assignment(self, stmt: Assignment):
        if not isinstance(stmt.target, Identifier):
            return
        declared = self._declared_var_types.get(stmt.target.name)
        if declared is None or self._alias_error:
            return
        inferred = self._infer_expression(stmt.value)
        if inferred is None:
            return
        if not self._is_compatible(declared, inferred):
            self.reports.append(TypeErrorReport(
                message=(
                    f"变量 '{stmt.target.name}' 声明类型为 {self._type_name(declared)}，"
                    f"不能赋予 {self._type_name(inferred)} 类型的值"
                ),
                line=stmt.line,
                column=stmt.column,
            ))

    def _check_function_decl(self, stmt: FunctionDecl):
        # 先登记参数类型，函数体内的标识符才能推断出类型。
        param_annotations = [
            self._resolve_annotation(ann) if i < len(stmt.param_type_annotations) else None
            for i, ann in enumerate(stmt.param_type_annotations)
        ]
        for param, ann in zip(stmt.params, param_annotations):
            if ann is not None:
                self._declared_var_types[param] = ann
                self._var_types[param] = ann

        inferred_return = None
        for s in stmt.body:
            inferred_return = self._find_return_type(s)
            if inferred_return is not None:
                break

        for s in stmt.body:
            self._check_statement(s)

        declared_return = self._resolve_annotation(stmt.return_type)
        self._func_signatures[stmt.name] = (param_annotations, declared_return, bool(stmt.rest_param))
        if inferred_return is not None:
            self._func_return_types[stmt.name] = inferred_return
        if declared_return is None or inferred_return is None or self._alias_error:
            return
        if not self._is_compatible(declared_return, inferred_return):
            self.reports.append(TypeErrorReport(
                message=(
                    f"函数 '{stmt.name}' 声明返回类型为 {self._type_name(declared_return)}，"
                    f"但推断返回类型为 {self._type_name(inferred_return)}"
                ),
                line=stmt.line,
                column=stmt.column,
            ))

    def _find_return_type(self, stmt) -> TypeAnnotation | None:
        if isinstance(stmt, ReturnStmt):
            return self._infer_expression(stmt.value) if stmt.value is not None else None
        if isinstance(stmt, (IfStmt, WhileStmt, ForInStmt, ForRangeStmt)):
            for body in (stmt.body, getattr(stmt, "else_body", [])):
                for s in body or []:
                    found = self._find_return_type(s)
                    if found is not None:
                        return found
        return None

    # ------------------------------------------------------------------
    # 表达式推断
    # ------------------------------------------------------------------

    def _infer_expression(self, expr: Expression) -> TypeAnnotation | None:
        if isinstance(expr, NumberLiteral):
            return BasicTypeAnnotation(name="数值", line=expr.line, column=expr.column)
        if isinstance(expr, StringLiteral):
            return BasicTypeAnnotation(name="文本", line=expr.line, column=expr.column)
        if isinstance(expr, BooleanLiteral):
            return BasicTypeAnnotation(name="布尔", line=expr.line, column=expr.column)
        if isinstance(expr, NullLiteral):
            return BasicTypeAnnotation(name="空", line=expr.line, column=expr.column)
        if isinstance(expr, ListLiteral):
            return self._make_generic("列表", [self._infer_expression(e) for e in expr.elements], expr)
        if isinstance(expr, SetLiteral):
            return self._make_generic("集合", [self._infer_expression(e) for e in expr.elements], expr)
        if isinstance(expr, TupleLiteral):
            return self._make_generic("元组", [self._infer_expression(e) for e in expr.elements], expr)
        if isinstance(expr, DictLiteral):
            keys = [self._infer_expression(k) for k, _ in expr.pairs]
            values = [self._infer_expression(v) for _, v in expr.pairs]
            return GenericTypeAnnotation(
                name="字典",
                type_args=[self._merge_types(keys), self._merge_types(values)],
                line=expr.line,
                column=expr.column,
            )
        if isinstance(expr, Identifier):
            return self._var_types.get(expr.name)
        if isinstance(expr, BinaryOp):
            left = self._infer_expression(expr.left)
            right = self._infer_expression(expr.right)
            op = expr.operator
            if op in ("+", "-", "*", "/", "//", "%", "**"):
                if left and left.name == "数值" and right and right.name == "数值":
                    return BasicTypeAnnotation(name="数值", line=expr.line, column=expr.column)
                if op == "+" and left and left.name == "文本" and right and right.name == "文本":
                    return BasicTypeAnnotation(name="文本", line=expr.line, column=expr.column)
            if op in ("并且", "或者", "==", "!=", "<", ">", "<=", ">="):
                return BasicTypeAnnotation(name="布尔", line=expr.line, column=expr.column)
            return None
        if isinstance(expr, UnaryOp):
            if expr.operator in ("不是", "!"):
                return BasicTypeAnnotation(name="布尔", line=expr.line, column=expr.column)
            return self._infer_expression(expr.operand)
        if isinstance(expr, IndexAccess):
            container = self._infer_expression(expr.object)
            if isinstance(container, GenericTypeAnnotation):
                kind = _generic_kind(container.name)
                args = container.type_args
                if kind in ("列表", "集合", "元组") and args:
                    return args[0]
                if kind == "字典" and len(args) >= 2:
                    return args[1]
            return None
        if isinstance(expr, FunctionCall) and isinstance(expr.callee, Identifier):
            self._check_call(expr)
            return self._func_return_types.get(expr.callee.name)
        return None

    def _check_call(self, expr: FunctionCall):
        name = expr.callee.name
        signature = self._func_signatures.get(name)
        if signature is None or self._alias_error:
            return  # 内置函数、未知函数或别名出错时：按动态类型处理
        param_types, _, has_rest = signature
        if not has_rest and len(expr.arguments) > len(param_types):
            self.reports.append(TypeErrorReport(
                message=(
                    f"调用函数 '{name}' 时期望至多 {len(param_types)} 个参数，"
                    f"但传入了 {len(expr.arguments)} 个"
                ),
                line=expr.line,
                column=expr.column,
            ))
        for index, (arg, declared) in enumerate(zip(expr.arguments, param_types), start=1):
            if declared is None:
                continue
            inferred = self._infer_expression(arg)
            if inferred is None:
                continue
            if not self._is_compatible(declared, inferred):
                self.reports.append(TypeErrorReport(
                    message=(
                        f"调用函数 '{name}' 的第 {index} 个参数应为 "
                        f"{self._type_name(declared)}，但传入了 {self._type_name(inferred)}"
                    ),
                    line=arg.line,
                    column=arg.column,
                ))

    def _make_generic(self, name: str, item_types: list, node) -> GenericTypeAnnotation:
        merged = self._merge_types(item_types)
        return GenericTypeAnnotation(
            name=name,
            type_args=[merged],
            line=node.line,
            column=node.column,
        )

    @staticmethod
    def _merge_types(types: list[TypeAnnotation | None]) -> TypeAnnotation:
        present = [t for t in types if t is not None]
        if not present:
            return BasicTypeAnnotation(name="任意")
        first = present[0]
        if all(TypeInferenceEngine._type_name_static(t) == TypeInferenceEngine._type_name_static(first)
               for t in present):
            return first
        return UnionTypeAnnotation(
            types=present,
            line=first.line,
            column=first.column,
        )

    # ------------------------------------------------------------------
    # 类型兼容
    # ------------------------------------------------------------------

    def _is_compatible(self, declared: TypeAnnotation | None,
                       inferred: TypeAnnotation | None) -> bool:
        """判断推断类型能否赋给声明类型。

        关键修正：无法证明兼容的组合返回 False（由调用方产生中文诊断），
        只有确实属于动态/未知的合法情形才返回 True。
        """
        if declared is None or inferred is None:
            return True
        return self._compatible(
            self._resolve_annotation(declared),
            self._resolve_annotation(inferred),
        )

    def _compatible(self, declared: TypeAnnotation, inferred: TypeAnnotation) -> bool:
        if _is_dynamic(declared) or _is_dynamic(inferred):
            return True

        if isinstance(declared, UnionTypeAnnotation):
            return any(self._compatible(t, inferred) for t in declared.types) if declared.types else True
        if isinstance(inferred, UnionTypeAnnotation):
            return any(self._compatible(declared, t) for t in inferred.types) if inferred.types else True

        declared_optional = self._optional_inner(declared)
        inferred_optional = self._optional_inner(inferred)
        if declared_optional is not None:
            if _is_null(inferred):
                return True
            if inferred_optional is not None:
                return self._compatible(declared_optional, inferred_optional)
            return self._compatible(declared_optional, inferred)
        if inferred_optional is not None:
            # 声明方不接受空，但值可能为空：这是真实的不兼容。
            return False

        if isinstance(declared, GenericTypeAnnotation) or isinstance(inferred, GenericTypeAnnotation):
            return self._compatible_generic(declared, inferred)
        if isinstance(declared, FunctionTypeAnnotation) or isinstance(inferred, FunctionTypeAnnotation):
            return self._compatible_function(declared, inferred)
        if isinstance(declared, BasicTypeAnnotation) and isinstance(inferred, BasicTypeAnnotation):
            return declared.name == inferred.name
        # 未知组合不再默认放行。
        return False

    @staticmethod
    def _optional_inner(ann: TypeAnnotation) -> TypeAnnotation | None:
        if isinstance(ann, OptionalTypeAnnotation):
            return ann.inner
        if isinstance(ann, GenericTypeAnnotation) and _generic_kind(ann.name) == "可选" and len(ann.type_args) == 1:
            return ann.type_args[0]
        return None

    def _compatible_generic(self, declared: TypeAnnotation, inferred: TypeAnnotation) -> bool:
        d_generic = isinstance(declared, GenericTypeAnnotation)
        i_generic = isinstance(inferred, GenericTypeAnnotation)

        if d_generic and i_generic:
            if _generic_kind(declared.name) != _generic_kind(inferred.name):
                return False
            d_args, i_args = declared.type_args, inferred.type_args
            if not d_args or not i_args:
                return True  # 裸容器或推断不出元素类型：按动态处理
            if len(d_args) != len(i_args):
                return False
            return all(self._compatible(a, b) for a, b in zip(d_args, i_args))

        if d_generic:
            # 声明为容器、推断为裸容器名：元素类型未知，保持兼容。
            return _generic_kind(declared.name) == inferred.name
        if i_generic:
            # 声明为裸容器名（如「列表」），推断带元素类型：兼容。
            return declared.name == _generic_kind(inferred.name)
        return False

    def _compatible_function(self, declared: TypeAnnotation, inferred: TypeAnnotation) -> bool:
        if not isinstance(declared, FunctionTypeAnnotation) or not isinstance(inferred, FunctionTypeAnnotation):
            return False
        if len(declared.param_types) != len(inferred.param_types):
            return False
        if not self._compatible(declared.return_type, inferred.return_type):
            return False
        return all(self._compatible(d, i) for d, i in zip(declared.param_types, inferred.param_types))

    # ------------------------------------------------------------------
    # 展示
    # ------------------------------------------------------------------

    def _type_name(self, ann: TypeAnnotation | None) -> str:
        if ann is None:
            return "未知类型"
        resolved = self._resolve_annotation(ann)
        return self._type_name_static(resolved)

    @staticmethod
    def _type_name_static(ann: TypeAnnotation) -> str:
        if isinstance(ann, BasicTypeAnnotation):
            return ann.name
        if isinstance(ann, UnionTypeAnnotation):
            return " | ".join(TypeInferenceEngine._type_name_static(t) for t in ann.types)
        if isinstance(ann, OptionalTypeAnnotation):
            return f"{TypeInferenceEngine._type_name_static(ann.inner)} | 空"
        if isinstance(ann, GenericTypeAnnotation):
            args = ", ".join(TypeInferenceEngine._type_name_static(t) for t in ann.type_args)
            return f"{ann.name}[{args}]" if args else ann.name
        if isinstance(ann, FunctionTypeAnnotation):
            params = ", ".join(TypeInferenceEngine._type_name_static(t) for t in ann.param_types)
            return f"函数({params}) -> {TypeInferenceEngine._type_name_static(ann.return_type)}"
        return type(ann).__name__
