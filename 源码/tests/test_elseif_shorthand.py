"""
`否则如果` 连写便捷写法测试
==========================

连写 `否则如果` 与分写 `否则 如果` 均由词法器归一为 TokenType.否则如果，
解析与执行语义完全一致。本模块锁定该能力，防止关键字前瞻逻辑回退后
再次出现「必须分写」的错误认知。
"""

import os
import sys
from contextlib import redirect_stdout
from io import StringIO

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from dao.interpreter import Interpreter
from dao.lexer import Lexer
from dao.parser import Parser
from dao.tokens import TokenType


def parse(source: str):
    return Parser(Lexer(source).tokenize()).parse()


def capture(source: str) -> str:
    buf = StringIO()
    with redirect_stdout(buf):
        Interpreter().execute(parse(source))
    return buf.getvalue().strip()


class TestElseIfShorthandLexing:
    """词法层：连写直接命中关键字，无需依赖「否则 + 如果」前瞻合并"""

    def test_shorthand_is_single_token(self):
        tokens = Lexer("否则如果 x > 0\n").tokenize()
        assert tokens[0].type == TokenType.否则如果
        assert tokens[0].value == "否则如果"

    def test_split_form_merges_to_same_token(self):
        tokens = Lexer("否则 如果 x > 0\n").tokenize()
        assert tokens[0].type == TokenType.否则如果
        assert tokens[0].value == "否则如果"

    def test_condition_identifier_not_glued(self):
        """关键字与条件间有空格时，中文标识符不粘连"""
        tokens = Lexer("否则如果 分数 >= 60\n").tokenize()
        values = [t.value for t in tokens]
        assert values[0] == "否则如果"
        assert "分数" in values


class TestElseIfShorthandParsing:
    """解析层：连写生成正常的 elif_clauses"""

    def test_shorthand_builds_elif_clause(self):
        stmt = parse("如果 假\n    打印(1)\n否则如果 真\n    打印(2)\n").statements[0]
        assert len(stmt.elif_clauses) == 1

    def test_multiple_shorthand_branches(self):
        source = (
            "如果 假\n    打印(1)\n"
            "否则如果 假\n    打印(2)\n"
            "否则如果 真\n    打印(3)\n"
            "否则\n    打印(4)\n"
        )
        stmt = parse(source).statements[0]
        assert len(stmt.elif_clauses) == 2
        assert len(stmt.else_body) == 1


class TestElseIfShorthandExecution:
    """执行层：连写分派正确，且与分写形式完全等价"""

    def test_dispatch_to_second_branch(self):
        source = (
            '定义 x = 2\n'
            '如果 x == 1\n    打印("一")\n'
            '否则如果 x == 2\n    打印("二")\n'
            '否则\n    打印("其它")\n'
        )
        assert capture(source) == "二"

    def test_shorthand_equals_split_form(self):
        template = (
            '定义 x = 2\n'
            '如果 x == 1\n    打印("一")\n'
            '{sep} x == 2\n    打印("二")\n'
            '否则\n    打印("其它")\n'
        )
        assert capture(template.format(sep="否则如果")) == capture(
            template.format(sep="否则 如果")
        )

    def test_complex_condition(self):
        source = (
            '定义 x = 7\n'
            '如果 x < 0\n    打印("负")\n'
            '否则如果 (x > 5 并且 x < 10)\n    打印("区间")\n'
            '否则\n    打印("其它")\n'
        )
        assert capture(source) == "区间"

    def test_nested_shorthand(self):
        source = (
            '定义 x = 3\n'
            '如果 x > 5\n'
            '    如果 x > 10\n        打印("大")\n'
            '    否则如果 x > 7\n        打印("中大")\n'
            '否则如果 x > 2\n    打印("小中")\n'
            '否则\n    打印("小")\n'
        )
        assert capture(source) == "小中"
