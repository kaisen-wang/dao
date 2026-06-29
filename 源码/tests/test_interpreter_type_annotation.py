import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from dao.lexer import Lexer
from dao.parser import Parser
from dao.interpreter.core import Interpreter


def run_source(source: str):
    tokens = Lexer(source).tokenize()
    ast = Parser(tokens).parse()
    interpreter = Interpreter()
    return interpreter.execute(ast)


class TestInterpreterTypeAnnotation:
    def test_variable_with_type_annotation(self):
        run_source("定义 x: 数值 = 42\n")
        result = run_source("定义 x: 数值 = 42\nx")
        assert result == 42

    def test_variable_without_type_annotation(self):
        result = run_source("定义 x = 42\nx")
        assert result == 42

    def test_function_with_param_types(self):
        result = run_source("函数 f(x: 数值) -> 数值\n  返回 x + 1\n\nf(5)")
        assert result == 6

    def test_function_without_type_annotations(self):
        result = run_source("函数 f(x)\n  返回 x + 1\n\nf(5)")
        assert result == 6

    def test_type_alias_decl(self):
        run_source("类型别名 用户ID = 数值\n")

    def test_type_annotation_ignored_at_runtime(self):
        result = run_source("定义 x: 文本 = 42\nx")
        assert result == 42

    def test_backward_compatible(self):
        result = run_source("定义 a = 1\n定义 b = 2\na + b")
        assert result == 3