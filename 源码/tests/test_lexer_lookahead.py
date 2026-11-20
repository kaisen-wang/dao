"""
关键字前瞻无副作用测试
======================

覆盖 #12：`异步` / `否则` 的多词前瞻改为纯 peek 后，
复杂上下文（括号内、嵌套）中关键字合并正确，且不污染后续 token 位置及词法器状态。
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

import pytest

from dao.lexer import Lexer
from dao.tokens import TokenType


def _tokens(source: str):
    return Lexer(source).tokenize()


class TestKeywordLookaheadNoLeak:
    """前瞻不得改变游标之外的任何可变状态，也不得污染后续 token 位置"""

    def test_async_lookahead_inside_nested_brackets(self):
        """异步 函数在嵌套方括号内：关键字正确合并，括号深度与后续位置不受污染"""
        source = "定义 f = [异步 函数 取数(), 1]\n打印(f)\n"
        toks = _tokens(source)

        pairs = [(t.type, t.value, t.line, t.column) for t in toks]
        assert (TokenType.异步, "异步", 1, 9) in pairs
        assert (TokenType.函数, "函数", 1, 14) in pairs
        # 前瞻命中后，紧随其后的 token 位置精确无偏移（列 15 而非被多消费后的位置）
        assert (TokenType.标识符, "取数", 1, 15) in pairs
        # 右方括号后括号深度归零：换行 token 正常产生，下一行行号正确
        assert (TokenType.右方括号, "]", 1, 22) in pairs
        assert (TokenType.换行, "\\n", 1, 23) in pairs
        assert (TokenType.标识符, "打印", 2, 1) in pairs
        # 没有因重复前瞻产生多余的「函数」token
        assert sum(1 for t in toks if t.type == TokenType.函数) == 1

    def test_else_if_lookahead_inside_nested_brackets(self):
        """否则 如果在嵌套圆括号内：合并为否则如果，且不残留独立的「如果」token"""
        source = "g((否则 如果 x))\n打印(x)\n"
        toks = _tokens(source)

        pairs = [(t.type, t.value, t.line, t.column) for t in toks]
        assert pairs.count((TokenType.左括号, "(", 1, 2)) == 1
        assert pairs.count((TokenType.左括号, "(", 1, 3)) == 1
        assert (TokenType.否则如果, "否则如果", 1, 4) in pairs
        # 后续标识符位置未被前瞻消费污染
        assert (TokenType.标识符, "x", 1, 10) in pairs
        # 两层右括号后括号深度归零，换行与第二行 token 位置正确
        assert (TokenType.右括号, ")", 1, 11) in pairs
        assert (TokenType.右括号, ")", 1, 12) in pairs
        assert (TokenType.换行, "\\n", 1, 13) in pairs
        assert (TokenType.标识符, "打印", 2, 1) in pairs
        # 前瞻未把「如果」单独吐成 token
        assert not any(t.value == "如果" for t in toks)

    def test_lookahead_miss_keeps_cursor_untouched(self):
        """前瞻未命中时游标保持原位：异步后接非「函数」词仍正常解析"""
        source = "定义 f = (异步, 1)\n打印(f)\n"
        toks = _tokens(source)
        pairs = [(t.type, t.value, t.line, t.column) for t in toks]
        assert (TokenType.异步, "异步", 1, 9) in pairs
        assert (TokenType.逗号, ",", 1, 11) in pairs
        assert (TokenType.右括号, ")", 1, 14) in pairs
        assert (TokenType.换行, "\\n", 1, 15) in pairs
        assert (TokenType.标识符, "打印", 2, 1) in pairs

    def test_peek_next_word_is_pure(self):
        """_peek_next_word 本身不修改 pos/line/column/_bracket_depth 等任何状态"""
        lx = Lexer("  函数 x\n")
        state_names = (
            "pos", "line", "column", "_bracket_depth",
            "_at_line_start", "_pipe_continuation", "indent_stack",
        )
        before = tuple(getattr(lx, name) for name in state_names)
        assert lx._peek_next_word(0) == ("函数", 4)
        assert tuple(getattr(lx, name) for name in state_names) == before

        # 未命中（空格后紧跟非标识符字符）同样无副作用
        lx2 = Lexer("  ,\n")
        before2 = tuple(getattr(lx2, name) for name in state_names)
        assert lx2._peek_next_word(0) == ("", 2)
        assert tuple(getattr(lx2, name) for name in state_names) == before2

        # 命中但词不是目标关键字时，也不产生任何游标移动
        lx3 = Lexer("异步 其他\n")
        before3 = tuple(getattr(lx3, name) for name in state_names)
        word, end = lx3._peek_next_word(2)
        assert (word, end) == ("其他", 5)
        assert tuple(getattr(lx3, name) for name in state_names) == before3


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
