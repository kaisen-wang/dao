import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from dao.lexer import Lexer
from dao.parser import Parser
from dao.ast_nodes import (
    BasicTypeAnnotation,
    FunctionTypeAnnotation,
    GenericTypeAnnotation,
    LambdaExpr,
    OptionalTypeAnnotation,
    TypeAliasDecl,
    UnionTypeAnnotation,
    VariableDecl,
    FunctionDecl,
)


def parse(source: str):
    tokens = Lexer(source).tokenize()
    return Parser(tokens).parse()


class TestTypeAnnotationParsing:
    def test_basic_type_annotation(self):
        ast = parse("定义 x: 数值 = 42\n")
        stmt = ast.statements[0]
        assert isinstance(stmt, VariableDecl)
        assert isinstance(stmt.type_annotation, BasicTypeAnnotation)
        assert stmt.type_annotation.name == "数值"

    def test_generic_type_annotation(self):
        ast = parse("定义 x: 列表[数值] = [1]\n")
        stmt = ast.statements[0]
        assert isinstance(stmt.type_annotation, GenericTypeAnnotation)
        assert stmt.type_annotation.name == "列表"
        assert len(stmt.type_annotation.type_args) == 1
        assert stmt.type_annotation.type_args[0].name == "数值"

    def test_dict_generic_type_annotation(self):
        ast = parse("定义 x: 字典[文本, 数值] = {}\n")
        stmt = ast.statements[0]
        assert isinstance(stmt.type_annotation, GenericTypeAnnotation)
        assert stmt.type_annotation.name == "字典"
        assert len(stmt.type_annotation.type_args) == 2

    def test_union_type_annotation(self):
        ast = parse("定义 x: 文本 | 数值 = 42\n")
        stmt = ast.statements[0]
        assert isinstance(stmt.type_annotation, UnionTypeAnnotation)
        assert len(stmt.type_annotation.types) == 2
        assert stmt.type_annotation.types[0].name == "文本"
        assert stmt.type_annotation.types[1].name == "数值"

    def test_optional_type_annotation(self):
        ast = parse("定义 x: 用户 | 空 = 空\n")
        stmt = ast.statements[0]
        assert isinstance(stmt.type_annotation, OptionalTypeAnnotation)
        assert stmt.type_annotation.inner.name == "用户"

    def test_function_type_annotation(self):
        ast = parse("定义 f: 函数(数值) -> 文本 = 函数(x) => x\n")
        stmt = ast.statements[0]
        assert isinstance(stmt.type_annotation, FunctionTypeAnnotation)
        assert len(stmt.type_annotation.param_types) == 1
        assert stmt.type_annotation.param_types[0].name == "数值"
        assert stmt.type_annotation.return_type.name == "文本"

    def test_variable_without_type_annotation(self):
        ast = parse("定义 x = 42\n")
        stmt = ast.statements[0]
        assert isinstance(stmt, VariableDecl)
        assert stmt.type_annotation is None


class TestFunctionTypeAnnotation:
    def test_function_with_param_types(self):
        ast = parse("函数 加(x: 数值, y: 数值)\n  返回 x\n")
        stmt = ast.statements[0]
        assert isinstance(stmt, FunctionDecl)
        assert len(stmt.param_type_annotations) == 2
        assert stmt.param_type_annotations[0].name == "数值"
        assert stmt.param_type_annotations[1].name == "数值"

    def test_function_with_return_type(self):
        ast = parse("函数 f(x) -> 数值\n  返回 x\n")
        stmt = ast.statements[0]
        assert isinstance(stmt, FunctionDecl)
        assert isinstance(stmt.return_type, BasicTypeAnnotation)
        assert stmt.return_type.name == "数值"

    def test_function_with_param_and_return_types(self):
        ast = parse("函数 f(x: 文本) -> 数值\n  返回 1\n")
        stmt = ast.statements[0]
        assert isinstance(stmt, FunctionDecl)
        assert stmt.param_type_annotations[0].name == "文本"
        assert stmt.return_type.name == "数值"

    def test_function_without_type_annotations(self):
        ast = parse("函数 f(x)\n  返回 x\n")
        stmt = ast.statements[0]
        assert isinstance(stmt, FunctionDecl)
        assert all(t is None for t in stmt.param_type_annotations)
        assert stmt.return_type is None


class TestTypeAliasParsing:
    def test_type_alias_decl(self):
        ast = parse("类型别名 用户ID = 数值\n")
        stmt = ast.statements[0]
        assert isinstance(stmt, TypeAliasDecl)
        assert stmt.name == "用户ID"
        assert isinstance(stmt.target_type, BasicTypeAnnotation)
        assert stmt.target_type.name == "数值"

    def test_type_alias_with_generic(self):
        ast = parse("类型别名 用户列表 = 列表[用户]\n")
        stmt = ast.statements[0]
        assert isinstance(stmt, TypeAliasDecl)
        assert stmt.name == "用户列表"
        assert isinstance(stmt.target_type, GenericTypeAnnotation)
        assert stmt.target_type.name == "列表"


class TestLambdaTypeAnnotation:
    def test_lambda_with_param_types(self):
        ast = parse("定义 f = 函数(x: 数值) => x\n")
        stmt = ast.statements[0]
        lam = stmt.value
        assert isinstance(lam, LambdaExpr)
        assert len(lam.param_type_annotations) == 1
        assert lam.param_type_annotations[0].name == "数值"


class TestBackwardCompatibility:
    def test_variable_without_annotation(self):
        ast = parse("定义 x = 42\n")
        stmt = ast.statements[0]
        assert stmt.type_annotation is None
        assert stmt.name == "x"

    def test_function_without_annotations(self):
        ast = parse("函数 f(x, y)\n  返回 x\n")
        stmt = ast.statements[0]
        assert stmt.return_type is None
        assert all(t is None for t in stmt.param_type_annotations)

    def test_lambda_without_annotations(self):
        ast = parse("定义 f = 函数(x) => x\n")
        stmt = ast.statements[0]
        lam = stmt.value
        assert isinstance(lam, LambdaExpr)
        assert all(t is None for t in lam.param_type_annotations)
        assert lam.return_type is None