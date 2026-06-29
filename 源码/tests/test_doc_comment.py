"""
文档注释测试
============
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

import pytest
from dao.lexer import Lexer
from dao.tokens import TokenType


def tokenize(source: str):
    return Lexer(source).tokenize()


class TestDocComment:
    def test_doc_comment_token(self):
        tokens = tokenize("/// 这是一个文档注释\n")
        doc_tokens = [t for t in tokens if t.type == TokenType.文档注释]
        assert len(doc_tokens) == 1
        assert doc_tokens[0].value == "这是一个文档注释"

    def test_doc_comment_not_confused_with_line_comment(self):
        tokens = tokenize("// 普通注释\n/// 文档注释\n")
        doc_tokens = [t for t in tokens if t.type == TokenType.文档注释]
        line_comment_tokens = [t for t in tokens if t.type == TokenType.文档注释]
        assert len(doc_tokens) == 1
        assert doc_tokens[0].value == "文档注释"

    def test_multiple_doc_comments(self):
        tokens = tokenize("/// 第一行\n/// 第二行\n/// 第三行\n")
        doc_tokens = [t for t in tokens if t.type == TokenType.文档注释]
        assert len(doc_tokens) == 3
        assert doc_tokens[0].value == "第一行"
        assert doc_tokens[1].value == "第二行"
        assert doc_tokens[2].value == "第三行"

    def test_doc_comment_before_function(self):
        tokens = tokenize("/// 计算两个数的和\n函数 加法(甲, 乙)\n    返回 甲 + 乙\n")
        doc_tokens = [t for t in tokens if t.type == TokenType.文档注释]
        assert len(doc_tokens) == 1
        assert doc_tokens[0].value == "计算两个数的和"

    def test_line_comment_not_doc(self):
        tokens = tokenize("// 这不是文档注释\n")
        doc_tokens = [t for t in tokens if t.type == TokenType.文档注释]
        assert len(doc_tokens) == 0