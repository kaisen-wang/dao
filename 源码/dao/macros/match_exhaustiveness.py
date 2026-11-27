"""``匹配``（MatchStmt）语句的穷尽性与重叠分支检查。

本模块独立于宏系统的 ``exhaustiveness.py``（后者面向模式匹配宏的
``PatternBranch``）。它直接检查 AST 中的 ``MatchStmt``，提供两类诊断：

1. 穷尽性检查：枚举变体是否全覆盖、布尔字面量是否覆盖真/假；
2. 重叠检查：重复的字面量分支、重复的枚举变体分支。

诊断自带行列信息，便于直接展示给用户。该模块不接入检查器主流程，
由使用者（测试或外部工具）显式调用 ``检查匹配穷尽性``。
"""

from dataclasses import dataclass

from ..ast_nodes import (
    BooleanLiteral,
    EnumVariantPattern,
    FunctionCall,
    Identifier,
    MatchCase,
    MatchStmt,
    MemberAccess,
    NullLiteral,
    NumberLiteral,
    StringLiteral,
)


@dataclass
class 匹配诊断:
    """一条穷尽性/重叠诊断。"""

    消息: str
    行: int = 0
    列: int = 0

    def __str__(self) -> str:
        return f"[行 {self.行}, 列 {self.列}] {self.消息}"


def _是通配符(case: MatchCase) -> bool:
    """判断分支是否为通配符/兜底分支。"""
    if case.is_wildcard:
        return True
    pattern = case.pattern
    return isinstance(pattern, Identifier) and pattern.name == "_"


def _字面量键(pattern):
    """返回字面量模式的可比较键，非字面量返回 ``None``。"""
    if isinstance(pattern, NumberLiteral):
        return ("数值", pattern.value)
    if isinstance(pattern, StringLiteral):
        return ("文本", pattern.value)
    if isinstance(pattern, BooleanLiteral):
        return ("布尔", pattern.value)
    if isinstance(pattern, NullLiteral):
        return ("空", None)
    return None


def _枚举变体键(pattern):
    """从模式中解析 ``(枚举名, 变体名)``，非枚举变体模式返回 ``None``。"""
    if isinstance(pattern, EnumVariantPattern):
        return (pattern.enum_name, pattern.variant_name)
    if isinstance(pattern, MemberAccess) and isinstance(pattern.object, Identifier):
        return (pattern.object.name, pattern.member)
    if (
        isinstance(pattern, FunctionCall)
        and isinstance(pattern.callee, MemberAccess)
        and isinstance(pattern.callee.object, Identifier)
    ):
        return (pattern.callee.object.name, pattern.callee.member)
    return None


def _布尔值(pattern):
    """仅当模式为布尔字面量时返回其值，否则返回 ``None``。"""
    if isinstance(pattern, BooleanLiteral):
        return pattern.value
    return None


def 检查匹配穷尽性(
    stmt: MatchStmt,
    枚举定义: dict[str, list[str]] | None = None,
) -> list[匹配诊断]:
    """检查一条 ``MatchStmt`` 的穷尽性与重叠分支。

    Args:
        stmt: 待检查的匹配语句。
        枚举定义: 可选的 ``枚举名 -> 变体名列表`` 映射。只有提供对应枚举的
            定义时，才能判断其变体是否被全覆盖。

    Returns:
        诊断列表（空列表表示未发现问题）。
    """
    枚举定义 = 枚举定义 or {}
    诊断: list[匹配诊断] = []

    if not stmt.cases:
        诊断.append(匹配诊断("匹配语句没有任何情况分支", stmt.line, stmt.column))
        return 诊断

    # ---------- 重叠检查 ----------
    已见字面量: dict[tuple, MatchCase] = {}
    已见变体: dict[tuple, MatchCase] = {}
    for case in stmt.cases:
        key = _字面量键(case.pattern)
        if key is not None:
            if key in 已见字面量:
                previous = 已见字面量[key]
                诊断.append(
                    匹配诊断(
                        f"重复的字面量分支 {key[1]!r}，与行 {previous.line} 的分支重叠",
                        case.line,
                        case.column,
                    )
                )
            else:
                已见字面量[key] = case

        variant = _枚举变体键(case.pattern)
        if variant is not None:
            if variant in 已见变体:
                previous = 已见变体[variant]
                诊断.append(
                    匹配诊断(
                        f"重复的枚举变体分支 {variant[0]}.{variant[1]}，"
                        f"与行 {previous.line} 的分支重叠",
                        case.line,
                        case.column,
                    )
                )
            else:
                已见变体[variant] = case

    # 存在通配符时，后续分支不可达，也视为重叠
    通配符索引 = next((i for i, c in enumerate(stmt.cases) if _是通配符(c)), None)
    if 通配符索引 is not None and 通配符索引 < len(stmt.cases) - 1:
        for case in stmt.cases[通配符索引 + 1 :]:
            诊断.append(
                匹配诊断(
                    "通配符分支之后的分支永远不会被执行",
                    case.line,
                    case.column,
                )
            )

    # ---------- 穷尽性检查 ----------
    # 通配符存在则覆盖所有情况，无需其他穷尽性诊断。
    if 通配符索引 is not None:
        return 诊断

    # 布尔字面量全覆盖检查。
    布尔值集合 = {
        value
        for value in (_布尔值(c.pattern) for c in stmt.cases)
        if value is not None
    }
    if 布尔值集合 and len(布尔值集合) < 2:
        缺少 = []
        if True not in 布尔值集合:
            缺少.append("真")
        if False not in 布尔值集合:
            缺少.append("假")
        诊断.append(
            匹配诊断(
                f"布尔匹配未覆盖所有情况，缺少: {', '.join(缺少)}",
                stmt.line,
                stmt.column,
            )
        )

    # 枚举变体全覆盖检查：仅当所有情况分支都属于同一枚举时才有意义。
    if 已见变体:
        枚举名集合 = {name for name, _ in 已见变体}
        if len(枚举名集合) == 1:
            枚举名 = next(iter(枚举名集合))
            全部变体 = 枚举定义.get(枚举名)
            if 全部变体 is not None:
                已覆盖 = {variant for _, variant in 已见变体}
                缺少变体 = [v for v in 全部变体 if v not in 已覆盖]
                if 缺少变体:
                    诊断.append(
                        匹配诊断(
                            f"枚举 {枚举名} 的匹配未穷尽，缺少变体: "
                            f"{', '.join(缺少变体)}",
                            stmt.line,
                            stmt.column,
                        )
                    )

    return 诊断


def 检查程序穷尽性(
    program,
    枚举定义: dict[str, list[str]] | None = None,
) -> list[tuple[MatchStmt, list[匹配诊断]]]:
    """递归检查程序中所有 ``MatchStmt``（含函数体、循环体、分支体）。"""
    枚举定义 = 枚举定义 or {}
    结果: list[tuple[MatchStmt, list[匹配诊断]]] = []

    def 遍历语句(statements):
        for stmt in statements:
            if isinstance(stmt, MatchStmt):
                结果.append((stmt, 检查匹配穷尽性(stmt, 枚举定义)))
                for case in stmt.cases:
                    遍历语句(case.body)
            else:
                for attr in (
                    "body",
                    "else_body",
                    "try_body",
                    "finally_body",
                    "true_body",
                    "false_body",
                ):
                    子语句 = getattr(stmt, attr, None)
                    if isinstance(子语句, list):
                        遍历语句(子语句)
                for _, branch_body in getattr(stmt, "elif_clauses", []):
                    遍历语句(branch_body)
                for catch in getattr(stmt, "catches", []):
                    遍历语句(catch.get("catch_body", []))

    遍历语句(program.statements)
    return 结果
