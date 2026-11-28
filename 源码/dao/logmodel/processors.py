"""结构化日志处理器（参考 OpenTelemetry Collector 的 Processors 层）。

处理器接收一条 :class:`~dao.logmodel.model.LogRecord`，可以原地修改后再返回，
也可以返回 ``None`` 表示该记录被丢弃。多个处理器按顺序串接成处理链。
"""

from __future__ import annotations

import random
import re
from typing import Protocol

from ..errors import 运行时错误
from .context import current_trace_context, get_resource
from .model import LogRecord


class Processor(Protocol):
    """日志处理器协议：返回值 ``None`` 表示丢弃该记录。"""

    def process(self, record: LogRecord) -> LogRecord | None:
        """处理一条日志记录，返回处理后的记录或 ``None``。"""
        ...


class LevelFilter:
    """按严重性数值过滤记录，低于 ``min_severity`` 的记录被丢弃。"""

    def __init__(self, min_severity: int = 9) -> None:
        try:
            self.min_severity: int = int(min_severity)
        except (TypeError, ValueError) as exc:
            raise 运行时错误("最低严重性必须是整数") from exc

    def process(self, record: LogRecord) -> LogRecord | None:
        """低于阈值返回 ``None``，否则原样返回该记录。"""
        if record.severity_number < self.min_severity:
            return None
        return record


class AttributeInjector:
    """把一组静态属性合并到 ``record.attributes``（已有键优先）。"""

    def __init__(self, attributes: dict | None = None) -> None:
        self.attributes: dict = dict(attributes or {})

    def process(self, record: LogRecord) -> LogRecord:
        """合并属性并返回记录。"""
        for key, value in self.attributes.items():
            record.attributes.setdefault(key, value)
        return record


def _key_matches(pattern: str, attr_key: str) -> bool:
    """判断属性键是否命中脱敏规则（忽略大小写，支持子串或点分段名）。"""
    rule = pattern.lower()
    key = attr_key.lower()
    return rule in key or rule in key.split(".")


class RedactionProcessor:
    """敏感信息脱敏：按属性键或正则匹配值，命中则替换为 ``mask``。

    ``keys`` 匹配属性名（子串或点分段名），``patterns`` 为正则表达式，既用于
    匹配属性值文本，也用于对 ``body`` 做正则替换。
    """

    def __init__(
        self,
        keys: list[str] | None = None,
        patterns: list[str] | None = None,
        mask: str = "***",
    ) -> None:
        self.keys: list[str] = [str(key) for key in (keys or [])]
        self.mask: str = str(mask)
        self._patterns: list[re.Pattern[str]] = []
        for pattern in patterns or []:
            try:
                self._patterns.append(re.compile(pattern))
            except re.error as exc:
                raise 运行时错误(f"无效的脱敏正则表达式: {pattern}") from exc

    def process(self, record: LogRecord) -> LogRecord:
        """对命中的属性值和正文做脱敏，返回记录。"""
        for key, value in list(record.attributes.items()):
            text = str(value)
            if any(_key_matches(rule, key) for rule in self.keys) or any(
                pattern.search(text) for pattern in self._patterns
            ):
                record.attributes[key] = self.mask
        for pattern in self._patterns:
            record.body = pattern.sub(self.mask, record.body)
        return record


class SamplingProcessor:
    """按比例采样；``keep_errors`` 为真时 ERROR/FATAL 记录始终保留。"""

    def __init__(self, ratio: float = 1.0, keep_errors: bool = True) -> None:
        try:
            value = float(ratio)
        except (TypeError, ValueError) as exc:
            raise 运行时错误("采样比例必须是 0 到 1 之间的数字") from exc
        if not 0.0 <= value <= 1.0:
            raise 运行时错误("采样比例必须在 0 到 1 之间")
        self.ratio: float = value
        self.keep_errors: bool = bool(keep_errors)

    def process(self, record: LogRecord) -> LogRecord | None:
        """返回 ``None`` 表示被采样丢弃。"""
        if self.keep_errors and (
            record.severity_number >= 17
            or record.severity_text.upper() in {"ERROR", "FATAL"}
        ):
            return record
        if self.ratio >= 1.0 or random.random() < self.ratio:
            return record
        return None


class TraceInjector:
    """从当前 ContextVar 注入追踪 ID 与资源元数据。"""

    def process(self, record: LogRecord) -> LogRecord:
        """把当前追踪上下文与资源合并到记录，返回记录。"""
        ctx = current_trace_context()
        if ctx is not None:
            record.trace_id = ctx.trace_id
            record.span_id = ctx.span_id
        for key, value in get_resource().to_dict().items():
            record.resource.setdefault(key, value)
        return record


class ResourceInjector:
    """把一组静态资源属性合并到 ``record.resource``（已有键优先）。"""

    def __init__(self, resource: dict | None = None) -> None:
        self.resource: dict = dict(resource or {})

    def process(self, record: LogRecord) -> LogRecord:
        """合并资源属性并返回记录。"""
        for key, value in self.resource.items():
            record.resource.setdefault(key, value)
        return record


# 中文别名，便于道语言侧与中文文档使用。
级别过滤器 = LevelFilter
属性注入处理器 = AttributeInjector
脱敏处理器 = RedactionProcessor
采样处理器 = SamplingProcessor
链路注入处理器 = TraceInjector
资源注入处理器 = ResourceInjector

__all__ = [
    "AttributeInjector",
    "LevelFilter",
    "Processor",
    "RedactionProcessor",
    "ResourceInjector",
    "SamplingProcessor",
    "TraceInjector",
    "属性注入处理器",
    "级别过滤器",
    "脱敏处理器",
    "资源注入处理器",
    "采样处理器",
    "链路注入处理器",
]
