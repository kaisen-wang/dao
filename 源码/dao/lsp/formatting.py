"""
道语言源码格式化核心
====================

提供与传输、编辑器无关的 :func:`format_source`，供 LSP 的
``textDocument/formatting`` 与独立格式化器 ``dao.tools.formatter`` 共用。

格式化只做 **词法安全的排版调整**，不改动 Token 语义：

- 以「缩进层级栈」把各级缩进统一为固定宽度（默认 4 个空格），保留相对层级；
- 删除行尾空白、把连续空行折叠为一行；
- 折叠标识符 / 关键字之间的多余空白，并在赋值号 ``=`` 两侧补空格；
- 字符串（含跨行三引号字符串）与注释的内容 **原样保留**，不做任何改写。

道语言不支持制表符缩进，因此行首制表符一律换算为空格。
"""

from __future__ import annotations

import re

# 默认一级缩进宽度（与《02-核心语法》推荐值一致）。
DEFAULT_INDENT_WIDTH = 4
# 连续空行最多保留的行数。
MAX_BLANK_LINES = 1

# 赋值号两侧补空格；避开 ==、>=、<=、!= 与 += 等复合运算符。
_ASSIGN_RE = re.compile(r"(?<![=!<>+*/%\-])\s*=\s*(?!=)")


def _protected_spans(source: str) -> list[tuple[int, int, str]]:
    """返回不得改写的区间 ``(起, 止, 类型)``；类型为 ``string`` / ``comment``。

    行注释的 **行尾空白不包含在区间内**，以便格式化器删除这些空白；
    三引号字符串的内部空白则完整保护，避免改变字符串字面量的值。
    """
    spans: list[tuple[int, int, str]] = []
    index = 0
    length = len(source)
    while index < length:
        char = source[index]
        # 字符串：西文引号与中文引号，三引号可跨行。
        if char in ('"', "'", "\u201c", "\u2018", "\u300c"):
            if char in ('"', "'") and source.startswith(char * 3, index):
                end = index + 3
                while end < length:
                    if source[end] == "\\":
                        end += 2
                        continue
                    if source.startswith(char * 3, end):
                        end += 3
                        break
                    end += 1
                end = min(end, length)
                spans.append((index, end, "string"))
                index = end
                continue
            end = index + 1
            while end < length:
                current = source[end]
                if current == "\\":
                    end += 2
                    continue
                if current in "\r\n":
                    break
                if current == char:
                    end += 1
                    break
                end += 1
            end = min(end, length)
            spans.append((index, end, "string"))
            index = end
            continue
        # 行注释：// 与 注：；// 也可能是整除运算符，这里一并保护到行尾，
        # 宁可少格式化几个字符，也不冒改变 Token 语义的风险。
        if source.startswith("//", index) or source.startswith("注：", index):
            end = index
            while end < length and source[end] not in "\r\n":
                end += 1
            while end > index and source[end - 1] in " \t":
                end -= 1
            spans.append((index, end, "comment"))
            index = end
            continue
        # 块注释 /* ... */ 可跨行，整体保护。
        if source.startswith("/*", index):
            close = source.find("*/", index + 2)
            end = length if close < 0 else close + 2
            spans.append((index, end, "comment"))
            index = end
            continue
        index += 1
    return spans


def _is_protected(spans: list[tuple[int, int, str]], position: int) -> bool:
    return any(start <= position < end for start, end, _ in spans)


def _split_lines(source: str) -> tuple[list[tuple[str, int, bool]], str]:
    """拆行，返回 ``(行文本, 行首偏移, 是否有换行符)`` 列表与换行符样式。"""
    newline = "\r\n" if "\r\n" in source else "\n"
    parts = source.split("\n")
    trailing_newline = source.endswith("\n")
    if trailing_newline and parts and parts[-1] == "":
        parts.pop()
    lines: list[tuple[str, int, bool]] = []
    offset = 0
    for index, part in enumerate(parts):
        body = part.removesuffix("\r")
        has_newline = index < len(parts) - 1 or trailing_newline
        lines.append((body, offset, has_newline))
        offset += len(part) + 1
    return lines, newline


def _leading_info(body: str) -> tuple[int, int]:
    """返回 ``(缩进宽度, 行首空白字符数)``；制表符按一级缩进估算宽度。"""
    width = 0
    count = 0
    for char in body:
        if char == " ":
            width += 1
        elif char == "\t":
            width += DEFAULT_INDENT_WIDTH
        else:
            break
        count += 1
    return width, count


def _code_level(width: int, stack: list[int]) -> int:
    """按缩进栈把实际宽度映射为层级；不一致宽度视为新的一级以尽量保真。"""
    if width > stack[-1]:
        stack.append(width)
        return len(stack) - 1
    while len(stack) > 1 and stack[-1] > width:
        stack.pop()
    if stack[-1] < width:
        stack.append(width)
    return len(stack) - 1


def _comment_level(width: int, stack: list[int]) -> int:
    """注释行按当前块对齐，不因为注释自身的缩进新建层级。"""
    while len(stack) > 1 and stack[-1] > width:
        stack.pop()
    return len(stack) - 1


def _normalize_spacing(code: str, start: int, spans: list[tuple[int, int, str]]) -> str:
    """折叠 unprotected 区域的多余空白，并规范赋值号两侧空格。"""
    chars: list[str] = []
    index = 0
    while index < len(code):
        if _is_protected(spans, start + index):
            chars.append(code[index])
            index += 1
            continue
        if code[index] in " \t":
            end = index
            while (
                end < len(code)
                and code[end] in " \t"
                and not _is_protected(spans, start + end)
            ):
                end += 1
            # 行尾空白直接丢弃；词与词之间保留一个空格。
            if end < len(code):
                chars.append(" ")
            index = end
            continue
        chars.append(code[index])
        index += 1

    result: list[str] = []
    index = 0
    joined = "".join(chars)
    while index < len(joined):
        if _is_protected(spans, start + index):
            result.append(joined[index])
            index += 1
            continue
        end = index
        while end < len(joined) and not _is_protected(spans, start + end):
            end += 1
        result.append(_ASSIGN_RE.sub(" = ", joined[index:end]))
        index = end
    return "".join(result)


def format_source(source: str, indent_width: int = DEFAULT_INDENT_WIDTH) -> str:
    """格式化道语言源码，返回新文本；不改变字符串字面量与注释内容。

    ``indent_width`` 为一级缩进的空格数，非法值回退到默认值 4。
    函数对任意输入（含空串、语法错误源码）均返回结果而不抛异常。
    """
    if not source:
        return source
    width = (
        indent_width
        if isinstance(indent_width, int) and 1 <= indent_width <= 16
        else DEFAULT_INDENT_WIDTH
    )
    spans = _protected_spans(source)
    lines, newline = _split_lines(source)
    stack = [0]
    formatted_lines: list[str] = []
    blank_run = 0

    for body, start, _ in lines:
        # 位于跨行字符串内部的整行原样保留；注释行仍可清理行尾空白。
        if any(
            begin <= start < end and kind == "string" for begin, end, kind in spans
        ):
            formatted_lines.append(body)
            blank_run = 0
            continue
        stripped = body.strip(" \t")
        if not stripped:
            blank_run += 1
            if blank_run <= MAX_BLANK_LINES:
                formatted_lines.append("")
            continue
        blank_run = 0

        lead, lead_count = _leading_info(body)
        comment_only = stripped.startswith(("//", "注：", "/*"))
        level = _comment_level(lead, stack) if comment_only else _code_level(lead, stack)
        code = _normalize_spacing(body[lead_count:], start + lead_count, spans)
        formatted_lines.append(" " * (level * width) + code)

    text = newline.join(formatted_lines)
    if lines and lines[-1][2]:
        text += newline
    return text
