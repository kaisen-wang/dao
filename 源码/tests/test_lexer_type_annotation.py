import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from dao.lexer import Lexer
from dao.tokens import TokenType


def tokenize(source: str):
    return Lexer(source).tokenize()


class TestLexerTypeAnnotation:
    def test_return_arrow(self):
        tokens = tokenize("->")
        assert tokens[0].type == TokenType.返回箭头
        assert tokens[0].value == "->"

    def test_return_arrow_in_function(self):
        tokens = tokenize("函数 f() -> 数值\n  返回 1\n")
        arrow_found = any(t.type == TokenType.返回箭头 for t in tokens)
        assert arrow_found

    def test_arrow_vs_return_arrow(self):
        tokens1 = tokenize("=>")
        assert tokens1[0].type == TokenType.箭头
        tokens2 = tokenize("->")
        assert tokens2[0].type == TokenType.返回箭头

    def test_pipe_operator_vs_union(self):
        tokens = tokenize("a |> b")
        assert tokens[1].type == TokenType.管道
        tokens2 = tokenize("a | b")
        assert tokens2[1].type == TokenType.竖线

    def test_type_alias_keyword(self):
        tokens = tokenize("类型别名 用户ID = 数值\n")
        assert tokens[0].type == TokenType.类型别名
        assert tokens[0].value == "类型别名"

    def test_colon_in_type_context(self):
        tokens = tokenize("定义 x: 数值 = 42\n")
        colon_found = False
        for t in tokens:
            if t.type == TokenType.冒号:
                colon_found = True
                break
        assert colon_found

    def test_brackets_in_generic(self):
        tokens = tokenize("列表[数值]")
        assert tokens[1].type == TokenType.左方括号
        assert tokens[3].type == TokenType.右方括号

    def test_union_type_annotation(self):
        tokens = tokenize("文本 | 数值")
        assert tokens[0].type == TokenType.标识符
        assert tokens[0].value == "文本"
        assert tokens[1].type == TokenType.竖线
        assert tokens[2].type == TokenType.标识符
        assert tokens[2].value == "数值"

    def test_return_arrow_with_spaces(self):
        tokens = tokenize("函数 f(x: 数值) -> 文本\n  返回 \"hi\"\n")
        types = [t.type for t in tokens]
        assert TokenType.返回箭头 in types
        assert TokenType.冒号 in types