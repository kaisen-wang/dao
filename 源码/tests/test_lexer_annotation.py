import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest

from dao.errors import 词法错误
from dao.lexer import Lexer
from dao.tokens import TokenType


def tokenize(source: str):
    return Lexer(source).tokenize()


class TestLexerAnnotation:
    def test_annotation_only(self):
        # @日志 应仅产生 [注解, 换行, 文件结束]
        tokens = tokenize("@日志")
        assert [t.type for t in tokens] == [
            TokenType.注解,
            TokenType.换行,
            TokenType.文件结束,
        ]
        assert tokens[0].value == "日志"

    def test_annotation_followed_by_identifier(self):
        # @缓存 后跟标识符：注解名不含 @，其后标识符正常词法化
        tokens = tokenize("@缓存 名字")
        assert tokens[0].type == TokenType.注解
        assert tokens[0].value == "缓存"
        assert tokens[1].type == TokenType.标识符
        assert tokens[1].value == "名字"

    def test_annotation_with_arguments(self):
        # 参数括号由解析器处理，词法器只负责 @名称，参数走现有词法机制
        tokens = tokenize("@缓存(10)")
        assert tokens[0].type == TokenType.注解
        assert tokens[0].value == "缓存"
        assert [t.type for t in tokens[1:4]] == [
            TokenType.左括号,
            TokenType.数值,
            TokenType.右括号,
        ]

    def test_invalid_annotation(self):
        # 单独的 @ 没有注解名，应抛中文词法错误
        with pytest.raises(词法错误, match="'@' 后需要一个注解名"):
            tokenize("@")

    def test_invalid_annotation_with_space(self):
        # @ 后紧跟空白也不合法
        with pytest.raises(词法错误, match="'@' 后需要一个注解名"):
            tokenize("@ (1)")
