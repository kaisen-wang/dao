import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from dao.lexer import Lexer
from dao.parser import Parser
from dao.types.checker import TypeInferenceEngine, TypeErrorReport
from dao.ast_nodes import BasicTypeAnnotation, UnionTypeAnnotation


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