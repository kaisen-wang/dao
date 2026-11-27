"""逻辑查询字符串解析器
======================

把 ``"父母(?x, '小明') 并且 城市(?x, '北京')"`` 这类**查询字符串**解析为
可求解的谓词目标（``LogicStruct``），供 :func:`dao.logic.solver.query` 使用。

支持特性：

* 嵌套结构：``祖孙(grandparent(?x), ?y)``
* 合取：``并且`` / ``且`` / ``and`` / ``&&`` / 顶层 ``,``
* 析取：``或者`` / ``或`` / ``or`` / ``||`` / ``;``
* 否定：``非`` / ``not``
* 变量：``?x``（道语言约定）；同时兼容 Prolog 风格大写标识符 ``X``
  或通过 ``declared_variables`` 显式声明的裸名称
* 字面量：单/双引号字符串、整数/小数、``真/假/true/false``

所有语法错误统一抛出 :class:`~dao.logic.exceptions.QueryError`，消息为
**中文**且包含出错位置（字符下标，从 1 开始），并写入异常的 ``line``/``column``。
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

from .core import LogicAtom, LogicStruct, LogicVariable
from .exceptions import QueryError

__all__ = ["ParsedQuery", "QueryGoal", "parse_query"]


@dataclass
class QueryGoal:
    """一个待求解的谓词目标，可带否定标记。"""

    term: LogicStruct
    negated: bool = False

    def __repr__(self) -> str:  # pragma: no cover - 仅调试展示
        prefix = "非" if self.negated else ""
        return f"{prefix}{self.term!r}"


@dataclass
class ParsedQuery:
    """解析结果：``clauses`` 是析取关系的合取子句列表。"""

    text: str
    clauses: list[list[QueryGoal]]
    variables: list[str]

    @property
    def is_disjunction(self) -> bool:
        return len(self.clauses) > 1

    @property
    def operator(self) -> str:
        return "析取" if self.is_disjunction else "合取"


@dataclass
class _Token:
    kind: str
    value: Any
    pos: int


_合取词 = {"并且", "且", "and", "AND"}
_析取词 = {"或者", "或", "or", "OR"}
_否定词 = {"非", "not", "NOT"}
_布尔词 = {"真": True, "true": True, "True": True, "假": False, "false": False, "False": False}
_转义符 = {"n": "\n", "t": "\t", "r": "\r", "\\": "\\", "'": "'", '"': '"'}

_数字模式 = re.compile(r"-?\d+(?:\.\d+)?")
_普罗格变量模式 = re.compile(r"[A-Z][A-Za-z0-9_]*")


def _是名称首字符(ch: str) -> bool:
    return ch == "_" or ch.isalpha()


def _是名称字符(ch: str) -> bool:
    return ch == "_" or ch.isalnum()


def _语法错误(消息: str, 位置: int) -> QueryError:
    """构造带中文位置信息的查询语法错误。"""
    error = QueryError(f"查询语法错误：{消息}（位置：第 {位置 + 1} 个字符）")
    error.line = 1
    error.column = 位置 + 1
    return error


def _分词(文本: str, 声明变量: set[str]) -> list[_Token]:
    """把查询字符串切分为词法单元，并记录每个单元的位置。"""
    tokens: list[_Token] = []
    i = 0
    length = len(文本)

    while i < length:
        ch = 文本[i]

        if ch.isspace():
            i += 1
            continue

        if ch == "(":
            tokens.append(_Token("左括号", "(", i))
            i += 1
            continue
        if ch == ")":
            tokens.append(_Token("右括号", ")", i))
            i += 1
            continue
        if ch == ",":
            tokens.append(_Token("逗号", ",", i))
            i += 1
            continue
        if ch == ";" or (ch == "|" and i + 1 < length and 文本[i + 1] == "|"):
            tokens.append(_Token("析取", ";" if ch == ";" else "||", i))
            i += 1 if ch == ";" else 2
            continue
        if ch == "&" and i + 1 < length and 文本[i + 1] == "&":
            tokens.append(_Token("合取", "&&", i))
            i += 2
            continue

        if ch in ("'", '"'):
            引号 = ch
            起始 = i
            i += 1
            字符 = []
            while i < length and 文本[i] != 引号:
                if 文本[i] == "\\" and i + 1 < length:
                    字符.append(_转义符.get(文本[i + 1], 文本[i + 1]))
                    i += 2
                else:
                    字符.append(文本[i])
                    i += 1
            if i >= length:
                raise _语法错误("字符串缺少结束引号", 起始)
            i += 1
            tokens.append(_Token("值", "".join(字符), 起始))
            continue

        if ch == "?" and i + 1 < length and _是名称首字符(文本[i + 1]):
            起始 = i
            j = i + 2
            while j < length and _是名称字符(文本[j]):
                j += 1
            tokens.append(_Token("变量", "?" + 文本[i + 1 : j], 起始))
            i = j
            continue

        if ch.isdigit() or (ch == "-" and i + 1 < length and 文本[i + 1].isdigit()):
            匹配 = _数字模式.match(文本, i)
            if 匹配 is None:  # pragma: no cover - 前一个分支已保证匹配成功
                raise _语法错误(f"无法识别的字符 '{ch}'", i)
            原文 = 匹配.group(0)
            值 = float(原文) if "." in 原文 else int(原文)
            tokens.append(_Token("值", 值, i))
            i = 匹配.end()
            continue

        if _是名称首字符(ch):
            起始 = i
            j = i + 1
            while j < length and _是名称字符(文本[j]):
                j += 1
            名称 = 文本[i:j]
            if 名称 in _布尔词:
                tokens.append(_Token("值", _布尔词[名称], 起始))
            elif 名称 in _否定词:
                tokens.append(_Token("否定", 名称, 起始))
            elif 名称 in _合取词:
                tokens.append(_Token("合取", 名称, 起始))
            elif 名称 in _析取词:
                tokens.append(_Token("析取", 名称, 起始))
            elif _普罗格变量模式.fullmatch(名称) or 名称 in 声明变量:
                tokens.append(_Token("变量", "?" + 名称, 起始))
            else:
                tokens.append(_Token("名称", 名称, 起始))
            i = j
            continue

        raise _语法错误(f"无法识别的字符 '{ch}'", i)

    tokens.append(_Token("结束", None, length))
    return tokens


class _解析器:
    def __init__(self, 文本: str, 声明变量: set[str]):
        self.文本 = 文本
        self.词法单元 = _分词(文本, 声明变量)
        self.位置 = 0
        self.变量: list[str] = []

    def _当前(self) -> _Token:
        return self.词法单元[self.位置]

    def _前进(self) -> _Token:
        当前 = self.词法单元[self.位置]
        self.位置 += 1
        return 当前

    def _期望(self, 种类: str, 说明: str) -> _Token:
        当前 = self._当前()
        if 当前.kind != 种类:
            raise _语法错误(f"期望{说明}，实际遇到 {self._描述(当前)}", 当前.pos)
        return self._前进()

    @staticmethod
    def _描述(token: _Token) -> str:
        if token.kind == "结束":
            return "查询结尾"
        return f"'{token.value}'"

    def parse(self) -> ParsedQuery:
        if self._当前().kind == "结束":
            raise _语法错误("查询不能为空", 0)

        子句 = [self._解析合取()]
        while self._当前().kind == "析取":
            self._前进()
            子句.append(self._解析合取())

        if self._当前().kind != "结束":
            当前 = self._当前()
            raise _语法错误(f"多余的查询内容 {self._描述(当前)}", 当前.pos)

        return ParsedQuery(self.文本, 子句, self._收集变量(子句))

    def _解析合取(self) -> list[QueryGoal]:
        目标 = [self._解析目标()]
        # 顶层逗号表示合取；结构内部的逗号已由 _解析结构 消费。
        while self._当前().kind in ("合取", "逗号"):
            self._前进()
            目标.append(self._解析目标())
        return 目标

    def _解析目标(self) -> QueryGoal:
        否定 = False
        if self._当前().kind == "否定":
            self._前进()
            否定 = True
        return QueryGoal(self._解析结构(), 否定)

    def _解析结构(self) -> LogicStruct:
        名称 = self._期望("名称", "谓词名称")
        self._期望("左括号", "左括号 '('")

        参数: list[Any] = []
        if self._当前().kind != "右括号":
            while True:
                参数.append(self._解析参数())
                if self._当前().kind == "逗号":
                    self._前进()
                    continue
                break

        self._期望("右括号", "右括号 ')'")
        return LogicStruct(名称.value, tuple(参数))

    def _解析参数(self) -> Any:
        当前 = self._当前()
        if 当前.kind == "名称":
            return self._解析结构()
        if 当前.kind == "变量":
            self._前进()
            if 当前.value not in self.变量:
                self.变量.append(当前.value)
            return LogicVariable(当前.value)
        if 当前.kind == "值":
            self._前进()
            return LogicAtom(当前.value)
        raise _语法错误(f"期望参数（变量、字面量或嵌套结构），实际遇到 {self._描述(当前)}", 当前.pos)

    def _收集变量(self, 子句: list[list[QueryGoal]]) -> list[str]:
        变量表: list[str] = []

        def 收集(项: Any) -> None:
            if isinstance(项, LogicVariable) and 项.name not in 变量表:
                变量表.append(项.name)
            elif isinstance(项, LogicStruct):
                for 参数 in 项.args:
                    收集(参数)
            elif isinstance(项, (list, tuple)):
                for 子项 in 项:
                    收集(子项)

        for 合取子句 in 子句:
            for 目标 in 合取子句:
                收集(目标.term)
        # 显式声明但目标中未出现的变量也一并展示（值为空绑定）。
        for 名称 in self.变量:
            if 名称 not in 变量表:
                变量表.append(名称)
        return 变量表


def parse_query(文本: str, declared_variables: list[str] | tuple[str, ...] | set[str] | None = None) -> ParsedQuery:
    """解析查询字符串并返回 :class:`ParsedQuery`。

    Args:
        文本: 形如 ``"父母(?x, '小明') 并且 城市(?x, '北京')"`` 的查询字符串。
        declared_variables: 需要按变量处理的裸名称（``x`` 与 ``?x`` 等价）。

    Raises:
        QueryError: 查询为空、语法错误或包含无法识别的字符。
    """
    if not isinstance(文本, str):
        raise QueryError(f"查询目标必须是文本，收到: {type(文本).__name__}")

    声明 = set()
    for 名称 in declared_variables or ():
        if not isinstance(名称, str) or not 名称:
            raise QueryError(f"变量声明必须是非空文本，收到: {名称!r}")
        裸名称 = 名称.removeprefix("?")
        声明.add(裸名称)

    return _解析器(文本, 声明).parse()
