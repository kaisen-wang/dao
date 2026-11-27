import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from dao.lexer import Lexer
from dao.parser import Parser
from dao.types.checker import TypeInferenceEngine, TypeErrorReport
from dao.ast_nodes import (
    BasicTypeAnnotation,
    GenericTypeAnnotation,
    UnionTypeAnnotation,
)


def check(source: str) -> list[TypeErrorReport]:
    tokens = Lexer(source).tokenize()
    ast = Parser(tokens).parse()
    engine = TypeInferenceEngine()
    return engine.check(ast)


class TestTypeInference:
    def test_infer_number_variable(self):
        reports = check("定义 x = 42\n")
        assert len(reports) == 0

    def test_infer_string_variable(self):
        reports = check("定义 x = \"hello\"\n")
        assert len(reports) == 0

    def test_type_mismatch_detected(self):
        reports = check("定义 x: 文本 = 42\n")
        assert len(reports) == 1
        assert "文本" in reports[0].message and "数值" in reports[0].message

    def test_type_match_no_error(self):
        reports = check("定义 x: 数值 = 42\n")
        assert len(reports) == 0

    def test_infer_binary_op(self):
        reports = check("定义 x: 数值 = 1 + 2\n")
        assert len(reports) == 0

    def test_infer_comparison(self):
        reports = check("定义 x: 布尔 = 1 > 2\n")
        assert len(reports) == 0

    def test_union_type_compatible(self):
        reports = check("定义 x: 文本 | 数值 = 42\n")
        assert len(reports) == 0

    def test_function_return_type_match(self):
        reports = check("函数 f(x) -> 数值\n  返回 1\n")
        assert len(reports) == 0

    def test_function_return_type_mismatch(self):
        reports = check("函数 f(x) -> 文本\n  返回 1\n")
        assert len(reports) == 1
        assert "文本" in reports[0].message

    def test_no_annotation_no_error(self):
        reports = check("定义 x = 42\n定义 y = \"hi\"\n")
        assert len(reports) == 0

    def test_any_type_compatible(self):
        reports = check("定义 x: 任意 = 42\n")
        assert len(reports) == 0


def infer(source: str, variable: str):
    """返回变量推断出的类型注解，供类型推断测试断言。"""
    ast = Parser(Lexer(source).tokenize()).parse()
    engine = TypeInferenceEngine()
    engine.check(ast)
    return engine._var_types.get(variable)


class TestContainerInference:
    def test_list_literal_infers_element_type(self):
        inferred = infer("定义 x = [1, 2, 3]\n", "x")
        assert isinstance(inferred, GenericTypeAnnotation)
        assert inferred.name == "列表"
        assert inferred.type_args[0].name == "数值"

    def test_dict_literal_infers_key_and_value_types(self):
        inferred = infer("定义 x = {\"a\": 1}\n", "x")
        assert isinstance(inferred, GenericTypeAnnotation)
        assert inferred.name == "字典"
        assert [arg.name for arg in inferred.type_args] == ["文本", "数值"]

    def test_empty_list_infers_dynamic_element(self):
        inferred = infer("定义 x = []\n", "x")
        assert isinstance(inferred, GenericTypeAnnotation)
        assert inferred.type_args[0].name == "任意"

    def test_binary_op_infers_boolean_for_comparison(self):
        inferred = infer("定义 x = 1 < 2\n", "x")
        assert isinstance(inferred, BasicTypeAnnotation)
        assert inferred.name == "布尔"

    def test_identifier_propagates_inferred_type(self):
        inferred = infer("定义 a = 42\n定义 b = a\n", "b")
        assert isinstance(inferred, BasicTypeAnnotation)
        assert inferred.name == "数值"
