"""``匹配``（MatchStmt）穷尽性与重叠分支检查测试。"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from dao.ast_nodes import EnumDecl, MatchStmt
from dao.lexer import Lexer
from dao.macros.match_exhaustiveness import (
    检查匹配穷尽性,
    检查程序穷尽性,
)
from dao.parser import Parser


def _parse(source: str):
    return Parser(Lexer(source).tokenize()).parse()


def _enum_defs(program) -> dict:
    """从 AST 中提取 ``枚举名 -> 变体名列表`` 映射。"""
    result = {}
    for stmt in program.statements:
        if isinstance(stmt, EnumDecl):
            result[stmt.name] = list(stmt.values)
    return result


def _match_stmts(program) -> list[MatchStmt]:
    return [s for s in program.statements if isinstance(s, MatchStmt)]


def _messages(diagnostics) -> list[str]:
    return [str(d) for d in diagnostics]


class TestMatchExhaustiveness:
    def test_empty_match_reports_missing_cases(self):
        # 语法层面必须至少有一个情况分支，因此直接构造空的 MatchStmt。
        stmt = MatchStmt(line=2, column=1)
        diagnostics = 检查匹配穷尽性(stmt)
        assert len(diagnostics) == 1
        assert "没有任何情况分支" in diagnostics[0].消息
        assert diagnostics[0].行 == 2

    def test_wildcard_covers_all(self):
        program = _parse(
            "定义 x = 99\n匹配 x\n"
            "  情况 1: 打印(\"一\")\n"
            "  情况 _: 打印(\"其他\")\n"
        )
        stmts = _match_stmts(program)
        assert 检查匹配穷尽性(stmts[0]) == []

    def test_duplicate_literal_branch(self):
        program = _parse(
            "定义 x = 1\n匹配 x\n"
            "  情况 1: 打印(\"甲\")\n"
            "  情况 1: 打印(\"乙\")\n"
        )
        stmts = _match_stmts(program)
        diagnostics = 检查匹配穷尽性(stmts[0])
        assert len(diagnostics) == 1
        assert "重复的字面量分支" in diagnostics[0].消息
        assert "行 3" in diagnostics[0].消息
        assert diagnostics[0].行 == 4

    def test_duplicate_string_literal_branch(self):
        program = _parse(
            "定义 x = \"红\"\n匹配 x\n"
            "  情况 \"红\": 打印(1)\n"
            "  情况 \"红\": 打印(2)\n"
        )
        stmts = _match_stmts(program)
        diagnostics = 检查匹配穷尽性(stmts[0])
        assert len(diagnostics) == 1
        assert "重复的字面量分支" in diagnostics[0].消息

    def test_duplicate_enum_variant_branch(self):
        program = _parse(
            "枚举 颜色\n  红\n  绿\n"
            "定义 c = 颜色.红\n匹配 c\n"
            "  情况 颜色.红: 打印(1)\n"
            "  情况 颜色.红: 打印(2)\n"
        )
        stmts = _match_stmts(program)
        diagnostics = 检查匹配穷尽性(stmts[0])
        assert len(diagnostics) == 1
        assert "重复的枚举变体分支 颜色.红" in diagnostics[0].消息

    def test_branch_after_wildcard_is_unreachable(self):
        program = _parse(
            "定义 x = 1\n匹配 x\n"
            "  情况 _: 打印(1)\n"
            "  情况 1: 打印(2)\n"
        )
        stmts = _match_stmts(program)
        diagnostics = 检查匹配穷尽性(stmts[0])
        assert len(diagnostics) == 1
        assert "永远不会被执行" in diagnostics[0].消息
        assert diagnostics[0].行 == 4

    def test_boolean_missing_case(self):
        program = _parse(
            "定义 b = 真\n匹配 b\n"
            "  情况 真: 打印(1)\n"
        )
        stmts = _match_stmts(program)
        diagnostics = 检查匹配穷尽性(stmts[0])
        assert len(diagnostics) == 1
        assert "布尔匹配未覆盖所有情况" in diagnostics[0].消息
        assert "假" in diagnostics[0].消息

    def test_boolean_full_coverage_is_exhaustive(self):
        program = _parse(
            "定义 b = 真\n匹配 b\n"
            "  情况 真: 打印(1)\n"
            "  情况 假: 打印(2)\n"
        )
        stmts = _match_stmts(program)
        assert 检查匹配穷尽性(stmts[0]) == []

    def test_enum_missing_variant(self):
        program = _parse(
            "枚举 颜色\n  红\n  绿\n  蓝\n"
            "定义 c = 颜色.红\n匹配 c\n"
            "  情况 颜色.红: 打印(1)\n"
            "  情况 颜色.绿: 打印(2)\n"
        )
        stmts = _match_stmts(program)
        diagnostics = 检查匹配穷尽性(stmts[0], _enum_defs(program))
        assert len(diagnostics) == 1
        assert "未穷尽" in diagnostics[0].消息
        assert "蓝" in diagnostics[0].消息

    def test_enum_full_variant_coverage(self):
        program = _parse(
            "枚举 颜色\n  红\n  绿\n  蓝\n"
            "定义 c = 颜色.蓝\n匹配 c\n"
            "  情况 颜色.红: 打印(1)\n"
            "  情况 颜色.绿: 打印(2)\n"
            "  情况 颜色.蓝: 打印(3)\n"
        )
        stmts = _match_stmts(program)
        assert 检查匹配穷尽性(stmts[0], _enum_defs(program)) == []

    def test_enum_without_definition_does_not_report_missing(self):
        program = _parse(
            "枚举 颜色\n  红\n  绿\n  蓝\n"
            "定义 c = 颜色.红\n匹配 c\n"
            "  情况 颜色.红: 打印(1)\n"
        )
        stmts = _match_stmts(program)
        diagnostics = 检查匹配穷尽性(stmts[0])
        assert diagnostics == []

    def test_enum_variant_with_binding_duplicate(self):
        program = _parse(
            "枚举 结果\n  成功(值)\n  失败(信息)\n"
            "定义 r = 结果.成功(1)\n匹配 r\n"
            "  情况 结果.成功(v): 打印(v)\n"
            "  情况 结果.成功(w): 打印(w)\n"
        )
        stmts = _match_stmts(program)
        diagnostics = 检查匹配穷尽性(stmts[0])
        assert len(diagnostics) == 1
        assert "重复的枚举变体分支 结果.成功" in diagnostics[0].消息

    def test_diagnostic_string_contains_line_and_column(self):
        program = _parse(
            "定义 x = 1\n匹配 x\n  情况 1: 打印(1)\n  情况 1: 打印(2)\n"
        )
        stmts = _match_stmts(program)
        diagnostics = 检查匹配穷尽性(stmts[0])
        assert str(diagnostics[0]).startswith("[行 4,")


class TestCheckProgramExhaustiveness:
    def test_finds_match_inside_function(self):
        program = _parse(
            "函数 f(x)\n"
            "  匹配 x\n"
            "    情况 1: 返回 10\n"
            "    情况 1: 返回 20\n"
        )
        results = 检查程序穷尽性(program)
        assert len(results) == 1
        _, diagnostics = results[0]
        assert len(diagnostics) == 1
        assert "重复的字面量分支" in diagnostics[0].消息

    def test_finds_multiple_matches(self):
        program = _parse(
            "定义 x = 1\n"
            "匹配 x\n  情况 1: 打印(1)\n  情况 1: 打印(2)\n"
            "定义 y = 2\n"
            "匹配 y\n  情况 真: 打印(3)\n"
        )
        results = 检查程序穷尽性(program)
        assert len(results) == 2
        assert all(diagnostics for _, diagnostics in results)
