"""道语言静态告警工具（linter）
==============================

基于 :class:`dao.lexer.Lexer` 与 :class:`dao.parser.Parser` 生成的 AST 做
轻量静态分析，发现常见的风格问题与潜在错误。与阻断式的
``dao.types.checker``（``--type-check``）不同，linter 只产生告警，不阻断编译。

支持的规则：

======================  ==========================================
规则                    含义
======================  ==========================================
D001                    未使用变量
D002                    重复变量定义
D003                    不可达代码
D004                    过长函数（语句数超过阈值）
D005                    魔法数字
D006                    宽泛捕获（裸 ``捕获``）
D007                    函数/类型缺少文档注释（默认关闭）
======================  ==========================================

命令行用法（在 ``源码`` 目录下运行）::

    python -m dao.tools.linter 文件.道
    python -m dao.tools.linter 目录 --json
    python -m dao.tools.linter 文件.道 --select D001,D003 --ignore D005
    python -m dao.tools.linter 文件.道 --doc-comments --max-statements 30

退出码：0 表示无告警，1 表示发现告警，2 表示参数/文件/解析错误。
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from dataclasses import dataclass, fields
from pathlib import Path

from ..ast_nodes import (
    AbstractDecl,
    Assignment,
    ASTNode,
    AsyncFunctionDecl,
    BreakStmt,
    ClassDecl,
    ContinueStmt,
    EnumDecl,
    ExportStmt,
    FunctionDecl,
    Identifier,
    NumberLiteral,
    ReturnStmt,
    Statement,
    ThrowStmt,
    TraitDecl,
    TryStmt,
    VariableDecl,
)
from ..lexer import Lexer
from ..parser import Parser
from ..tokens import TokenType

#: 规则编号到中文名称的映射（供 ``--select`` / ``--ignore`` 校验与帮助信息使用）。
RULES: dict[str, str] = {
    "D001": "未使用变量",
    "D002": "重复变量定义",
    "D003": "不可达代码",
    "D004": "过长函数",
    "D005": "魔法数字",
    "D006": "宽泛捕获（裸捕获）",
    "D007": "缺失文档注释",
}

#: 默认不视为魔法数字的数值：0 与 1 是常见哨兵/计数基准。
DEFAULT_MAGIC_ALLOWLIST: frozenset = frozenset({0, 1})

#: 默认函数语句数上限。
DEFAULT_MAX_STATEMENTS = 50

_终止语句名称: dict[type, str] = {
    ReturnStmt: "返回",
    ThrowStmt: "抛出",
    BreakStmt: "跳出",
    ContinueStmt: "继续",
}

_文档节点类型 = (
    FunctionDecl,
    AsyncFunctionDecl,
    ClassDecl,
    TraitDecl,
    EnumDecl,
    AbstractDecl,
)


@dataclass(frozen=True)
class LintIssue:
    """一条中文静态告警。行列均为 1 基。"""

    rule: str
    message: str
    line: int
    column: int
    filename: str = ""
    severity: str = "warning"

    def __str__(self) -> str:
        prefix = f"{self.filename}:" if self.filename else ""
        return f"{prefix}{self.line}:{self.column}: {self.rule} {self.message}"

    def to_dict(self) -> dict:
        """供 ``--json`` 输出使用的可序列化表示。"""
        return {
            "rule": self.rule,
            "message": self.message,
            "line": self.line,
            "column": self.column,
            "filename": self.filename,
            "severity": self.severity,
        }


def _children(node: object):
    """递归产出 ``node`` 的直接子节点（兼容 list/tuple/dict 容器）。"""
    if isinstance(node, dict):
        values = list(node.values())
    elif isinstance(node, (list, tuple)):
        values = list(node)
    elif isinstance(node, ASTNode):
        values = [
            getattr(node, f.name)
            for f in fields(node)
            if f.name not in ("line", "column")
        ]
    else:
        return

    for value in values:
        if isinstance(value, ASTNode):
            yield value
        elif isinstance(value, (list, tuple, dict)):
            yield from _children(value)


def _walk(node: ASTNode):
    """深度优先遍历整棵 AST（含容器中的节点）。"""
    yield node
    for child in _children(node):
        yield from _walk(child)


def _statement_lists(node: object):
    """产出 AST 中所有“语句列表”（每个列表是一个独立的作用域块）。"""
    if isinstance(node, dict):
        for value in node.values():
            yield from _statement_lists(value)
    elif isinstance(node, (list, tuple)):
        if node and all(isinstance(item, Statement) for item in node):
            yield node
        # 语句列表本身也要继续深入，找出函数体/分支体等嵌套作用域。
        for value in node:
            yield from _statement_lists(value)
    elif isinstance(node, ASTNode):
        for f in fields(node):
            if f.name in ("line", "column"):
                continue
            yield from _statement_lists(getattr(node, f.name))


def _parse_rules(raw: str | None) -> set[str] | None:
    """解析 ``--select`` / ``--ignore`` 的逗号分隔规则列表。"""
    if raw is None:
        return None
    parts = {part.strip().upper() for part in raw.replace(" ", ",").split(",") if part.strip()}
    if not parts:
        return None
    if "ALL" in parts:
        return set(RULES)
    unknown = sorted(parts - RULES.keys())
    if unknown:
        raise ValueError(f"未知规则编号：{'、'.join(unknown)}。可用规则：{'、'.join(RULES)}")
    return parts


class Linter:
    """道语言静态告警器。

    参数：
        select: 仅启用这些规则（规则编号集合）；``None`` 表示全部。
        ignore: 禁用的规则编号集合，优先级高于 ``select``。
        max_statements: D004 的函数语句数上限。
        magic_allowlist: D005 允许出现的数值集合。
        check_doc_comments: 是否启用默认关闭的 D007。
    """

    def __init__(
        self,
        select: set[str] | None = None,
        ignore: set[str] | None = None,
        max_statements: int = DEFAULT_MAX_STATEMENTS,
        magic_allowlist=frozenset(DEFAULT_MAGIC_ALLOWLIST),
        check_doc_comments: bool = False,
    ):
        self.select = set(select) if select is not None else None
        self.ignore = set(ignore) if ignore is not None else set()
        self.max_statements = max_statements
        self.magic_allowlist = frozenset(magic_allowlist)
        self.check_doc_comments = check_doc_comments

    def _enabled(self, rule: str) -> bool:
        if rule in self.ignore:
            return False
        if self.select is not None:
            return rule in self.select
        return rule in RULES

    def _issue(self, rule: str, message: str, node: ASTNode, filename: str) -> LintIssue:
        return LintIssue(
            rule=rule,
            message=message,
            line=max(1, getattr(node, "line", 0) or 1),
            column=max(1, getattr(node, "column", 0) or 1),
            filename=filename,
        )

    def check(self, source: str, filename: str = "") -> list[LintIssue]:
        """分析源码文本，返回按位置排序的告警列表。"""
        tokens = Lexer(source, filename or "<输入>").tokenize()
        program = Parser(tokens, source).parse()
        nodes = list(_walk(program))

        issues: list[LintIssue] = []
        if self._enabled("D001"):
            issues.extend(self._check_unused_variables(nodes, program, filename))
        if self._enabled("D002"):
            issues.extend(self._check_duplicate_definitions(program, filename))
        if self._enabled("D003"):
            issues.extend(self._check_unreachable_code(program, filename))
        if self._enabled("D004"):
            issues.extend(self._check_long_functions(nodes, filename))
        if self._enabled("D005"):
            issues.extend(self._check_magic_numbers(nodes, filename))
        if self._enabled("D006"):
            issues.extend(self._check_bare_catches(nodes, filename))
        if self.check_doc_comments and self._enabled("D007"):
            issues.extend(self._check_missing_doc_comments(nodes, tokens, filename))

        # 去重并按位置排序，保证输出稳定。
        unique: dict[tuple, LintIssue] = {
            (item.rule, item.line, item.column, item.message, item.filename): item
            for item in issues
        }
        return sorted(
            unique.values(), key=lambda item: (item.line, item.column, item.rule, item.message)
        )

    def check_file(self, path: str | Path) -> list[LintIssue]:
        """分析一个 ``.道`` 文件。"""
        file_path = Path(path)
        return self.check(file_path.read_text(encoding="utf-8"), filename=str(file_path))

    def check_paths(self, paths: list[str | Path]) -> list[LintIssue]:
        """分析多个路径；目录递归展开其中的 ``.道`` 文件。"""
        issues: list[LintIssue] = []
        for file_path in expand_paths(paths):
            issues.extend(self.check_file(file_path))
        return issues

    # -------------------- 各规则实现 --------------------

    def _check_unused_variables(
        self, nodes: list[ASTNode], program: ASTNode, filename: str
    ) -> list[LintIssue]:
        # 赋值语句的左值不是“读取”，不应计入使用次数。
        write_ids = {
            id(node.target)
            for node in nodes
            if isinstance(node, Assignment) and isinstance(node.target, Identifier)
        }
        uses: Counter = Counter()
        for node in nodes:
            if isinstance(node, Identifier) and id(node) not in write_ids:
                uses[node.name] += 1

        # 显式导出的变量、导出语句中的名字以及下划线开头的名字视为有意保留。
        protected = {
            name
            for node in nodes
            if isinstance(node, ExportStmt)
            for name in node.names
        }
        protected.update(
            node.name for node in nodes if isinstance(node, VariableDecl) and node.is_exported
        )

        issues: list[LintIssue] = []
        for node in nodes:
            if not isinstance(node, VariableDecl):
                continue
            name = node.name
            if not name or name in protected or name.startswith("_"):
                continue
            if uses.get(name, 0) == 0:
                issues.append(
                    self._issue(
                        "D001", f"变量“{name}”已定义但从未使用", node, filename
                    )
                )
        return issues

    def _check_duplicate_definitions(self, program: ASTNode, filename: str) -> list[LintIssue]:
        issues: list[LintIssue] = []
        for block in _statement_lists(program):
            first: dict[str, VariableDecl] = {}
            for stmt in block:
                if not isinstance(stmt, VariableDecl):
                    continue
                name = stmt.name
                if name in first:
                    issues.append(
                        self._issue(
                            "D002",
                            f"变量“{name}”重复定义（首次定义于第 {first[name].line} 行）",
                            stmt,
                            filename,
                        )
                    )
                else:
                    first[name] = stmt
        return issues

    def _check_unreachable_code(self, program: ASTNode, filename: str) -> list[LintIssue]:
        issues: list[LintIssue] = []
        for block in _statement_lists(program):
            stop_index = None
            stop_stmt = None
            for index, stmt in enumerate(block):
                for stmt_type, label in _终止语句名称.items():
                    if isinstance(stmt, stmt_type):
                        stop_index, stop_stmt = index, stmt
                        break
                if stop_index is not None:
                    break
            if stop_index is None:
                continue
            label = next(
                label for stmt_type, label in _终止语句名称.items()
                if isinstance(stop_stmt, stmt_type)
            )
            for stmt in block[stop_index + 1 :]:
                issues.append(
                    self._issue("D003", f"{label} 之后的代码不可达", stmt, filename)
                )
        return issues

    def _check_long_functions(self, nodes: list[ASTNode], filename: str) -> list[LintIssue]:
        issues: list[LintIssue] = []
        for node in nodes:
            if isinstance(node, (FunctionDecl, AsyncFunctionDecl)):
                count = len(node.body)
                if count > self.max_statements:
                    issues.append(
                        self._issue(
                            "D004",
                            f"函数“{node.name}”包含 {count} 条语句，超过上限 {self.max_statements}",
                            node,
                            filename,
                        )
                    )
        return issues

    def _check_magic_numbers(self, nodes: list[ASTNode], filename: str) -> list[LintIssue]:
        issues: list[LintIssue] = []
        for node in nodes:
            if isinstance(node, NumberLiteral) and node.value not in self.magic_allowlist:
                issues.append(
                    self._issue("D005", f"魔法数字 {node.value}，建议使用具名常量", node, filename)
                )
        return issues

    def _check_bare_catches(self, nodes: list[ASTNode], filename: str) -> list[LintIssue]:
        issues: list[LintIssue] = []
        for node in nodes:
            if isinstance(node, TryStmt):
                bare = [item for item in node.catches if not item.get("error_type")]
                if bare:
                    issues.append(
                        self._issue(
                            "D006",
                            "捕获 未指定异常类型（裸捕获），建议写成“捕获 错误类型: 变量”",
                            node,
                            filename,
                        )
                    )
        return issues

    def _check_missing_doc_comments(
        self, nodes: list[ASTNode], tokens: list, filename: str
    ) -> list[LintIssue]:
        doc_lines = {token.line for token in tokens if token.type == TokenType.文档注释}
        issues: list[LintIssue] = []
        for node in nodes:
            if isinstance(node, _文档节点类型) and (node.line - 1) not in doc_lines:
                issues.append(
                    self._issue(
                        "D007",
                        f"“{node.name}”缺少文档注释（使用 /// 编写）",
                        node,
                        filename,
                    )
                )
        return issues


def expand_paths(paths: list[str | Path]) -> list[Path]:
    """把路径列表展开为排序后的 ``.道`` 文件列表。"""
    files: list[Path] = []
    for raw in paths:
        path = Path(raw)
        if path.is_dir():
            files.extend(sorted(path.rglob("*.道")))
        elif path.is_file():
            files.append(path)
        else:
            raise FileNotFoundError(f"路径不存在：{path}")
    return files


def main(argv: list[str] | None = None) -> int:
    """命令行入口。"""
    parser = argparse.ArgumentParser(
        prog="python -m dao.tools.linter",
        description="道语言静态告警工具（未使用变量、重复定义、不可达代码等）",
    )
    parser.add_argument("paths", nargs="+", help="待分析的 .道 文件或目录")
    parser.add_argument("--json", action="store_true", help="以 JSON 数组输出告警")
    parser.add_argument(
        "--select", help="仅启用指定规则，逗号分隔，如 D001,D003；默认全部"
    )
    parser.add_argument(
        "--ignore", help="禁用指定规则，逗号分隔，如 D005；优先级高于 --select"
    )
    parser.add_argument(
        "--max-statements",
        type=int,
        default=DEFAULT_MAX_STATEMENTS,
        help=f"D004 的函数语句数上限（默认 {DEFAULT_MAX_STATEMENTS}）",
    )
    parser.add_argument(
        "--doc-comments",
        action="store_true",
        help="启用 D007：函数/类型缺少文档注释时告警（默认关闭）",
    )
    args = parser.parse_args(argv)

    try:
        select = _parse_rules(args.select)
        ignore = _parse_rules(args.ignore)
    except ValueError as error:
        print(f"错误：{error}", file=sys.stderr)
        return 2

    files = expand_paths(args.paths)
    if not files:
        print("错误：未找到任何 .道 文件", file=sys.stderr)
        return 2

    linter = Linter(
        select=select,
        ignore=ignore,
        max_statements=args.max_statements,
        check_doc_comments=args.doc_comments,
    )
    issues: list[LintIssue] = []
    for path in files:
        try:
            issues.extend(linter.check_file(path))
        except Exception as error:  # 解析错误等：不静默吞掉，报告后以 2 退出
            print(f"错误：无法分析“{path}”：{error}", file=sys.stderr)
            return 2

    if args.json:
        sys.stdout.write(
            json.dumps([item.to_dict() for item in issues], ensure_ascii=False, indent=2) + "\n"
        )
    else:
        for item in issues:
            print(item)
        if issues:
            print(f"共发现 {len(issues)} 条告警。")
        else:
            print("未发现问题。")
    return 1 if issues else 0


if __name__ == "__main__":
    sys.exit(main())
