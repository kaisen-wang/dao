"""结构化日志数据模型（参考 OpenTelemetry Logs Data Model）。

将日志从"文本"升级为"事件"：每条记录是一个 LogRecord，包含事件发生时间、
观察时间、严重性数值与文本、正文、扁平化属性、资源信息、作用域信息，以及
用于关联分布式追踪的 TraceId / SpanId。

字段命名遵循 OpenTelemetry 规范（英文键），便于下游 Collector / 后端直接消费。
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timezone

from ..errors import 运行时错误

# 中文级别 -> (SeverityText, SeverityNumber)。
# SeverityNumber 取 OpenTelemetry 规定区间的起点：
# DEBUG 5-8 / INFO 9-12 / WARN 13-16 / ERROR 17-20 / FATAL 21-24。
SEVERITY_MAP: dict[str, tuple[str, int]] = {
    "调试": ("DEBUG", 5),
    "信息": ("INFO", 9),
    "警告": ("WARN", 13),
    "错误": ("ERROR", 17),
    "致命": ("FATAL", 21),
}

# Python logging 级别名 -> 规范文本（兼容 text logging 的 WARNING / CRITICAL）。
_LEVELNAME_TO_TEXT: dict[str, str] = {
    "DEBUG": "DEBUG",
    "INFO": "INFO",
    "WARNING": "WARN",
    "WARN": "WARN",
    "ERROR": "ERROR",
    "CRITICAL": "FATAL",
    "FATAL": "FATAL",
}

_TEXT_TO_SEVERITY: dict[str, tuple[str, int]] = {
    text: (text, number) for text, number in SEVERITY_MAP.values()
}
_TEXT_TO_SEVERITY["WARNING"] = ("WARN", 13)
_TEXT_TO_SEVERITY["CRITICAL"] = ("FATAL", 21)


def now_iso() -> str:
    """返回 UTC ISO-8601 时间戳（毫秒精度，以 Z 结尾）。"""
    return (
        datetime.now(timezone.utc)  # noqa: UP017  datetime.UTC 为 Python 3.11+ 专有，需兼容 3.10
        .isoformat(timespec="milliseconds")
        .replace("+00:00", "Z")
    )


def severity_of(级别: str) -> tuple[str, int]:
    """把中文级别名或英文级别文本转为 (SeverityText, SeverityNumber)。

    支持中文（调试/信息/警告/错误/致命）、英文文本（DEBUG/WARN/WARNING/
    CRITICAL 等）以及数字字符串。无效值抛出中文运行时错误。
    """
    if isinstance(级别, int):
        return _severity_from_number(级别)
    name = str(级别).strip()
    if name in SEVERITY_MAP:
        return SEVERITY_MAP[name]
    upper = name.upper()
    if upper in _LEVELNAME_TO_TEXT:
        return _TEXT_TO_SEVERITY[_LEVELNAME_TO_TEXT[upper]]
    if upper in _TEXT_TO_SEVERITY:
        return _TEXT_TO_SEVERITY[upper]
    if name.isdigit():
        return _severity_from_number(int(name))
    raise 运行时错误(
        f"无效的日志级别: {级别}，有效值: {', '.join(SEVERITY_MAP.keys())}"
    )


def _severity_from_number(number: int) -> tuple[str, int]:
    """把严重性数值归入所在区间的规范文本。"""
    if not 0 <= number <= 255:
        raise 运行时错误(f"无效的严重性数值: {number}，有效范围: 0-255")
    for text, lower in reversed(
        [(text, num) for text, num in SEVERITY_MAP.values()]
    ):
        if number >= lower:
            return text, number
    return "DEBUG", number


@dataclass
class LogRecord:
    """一条结构化日志记录。

    Attributes:
        body: 日志正文（Body）。
        severity_text: 严重性文本，如 INFO / WARN / ERROR。
        severity_number: 严重性数值，0-255。
        timestamp: 事件发生时间（ISO-8601 UTC）。
        observed_timestamp: 采集系统观察到该事件的时间（ISO-8601 UTC）。
        attributes: 扁平化上下文属性，键建议用点分隔，如 ``user.id``。
        resource: 产生日志的实体元数据，如 ``service.name`` / ``host.name``。
        scope: 产生日志的组件信息（库名、版本）。
        trace_id: 32 位十六进制追踪 ID。
        span_id: 16 位十六进制跨度 ID。
        location: 道语言调用位置（相对命令执行目录的路径:行号）。
    """

    body: str
    severity_text: str = "INFO"
    severity_number: int = 9
    timestamp: str = ""
    observed_timestamp: str = ""
    attributes: dict = field(default_factory=dict)
    resource: dict = field(default_factory=dict)
    scope: dict = field(default_factory=dict)
    trace_id: str = ""
    span_id: str = ""
    location: str = ""

    def __post_init__(self) -> None:
        if not self.timestamp:
            self.timestamp = now_iso()
        if not self.observed_timestamp:
            self.observed_timestamp = now_iso()
        self.body = str(self.body)

    def to_dict(self) -> dict:
        """转换为 OpenTelemetry 风格的扁平字典。"""
        return {
            "timestamp": self.timestamp,
            "observed_timestamp": self.observed_timestamp,
            "severity_number": self.severity_number,
            "severity_text": self.severity_text,
            "body": self.body,
            "attributes": dict(self.attributes),
            "resource": dict(self.resource),
            "scope": dict(self.scope),
            "trace_id": self.trace_id,
            "span_id": self.span_id,
            "location": self.location,
        }

    def to_json(self, ensure_ascii: bool = False) -> str:
        """序列化为单行 JSON（默认保留中文原文）。"""
        return json.dumps(self.to_dict(), ensure_ascii=ensure_ascii)

    def copy(self) -> LogRecord:
        """复制一份记录，供处理器链安全地修改。"""
        return LogRecord(
            body=self.body,
            severity_text=self.severity_text,
            severity_number=self.severity_number,
            timestamp=self.timestamp,
            observed_timestamp=self.observed_timestamp,
            attributes=dict(self.attributes),
            resource=dict(self.resource),
            scope=dict(self.scope),
            trace_id=self.trace_id,
            span_id=self.span_id,
            location=self.location,
        )

    def __repr__(self) -> str:
        return (
            f"<日志记录 {self.severity_text} {self.body!r} "
            f"trace={self.trace_id[:8] or '-'}>"
        )


def create_record(
    消息,
    级别="信息",
    属性=None,
    资源=None,
    作用域=None,
    位置="",
    追踪上下文=None,
) -> LogRecord:
    """便捷构造日志记录：自动填严重性、时间戳与追踪上下文。"""
    text, number = severity_of(级别)
    record = LogRecord(
        body=消息,
        severity_text=text,
        severity_number=number,
        attributes=dict(属性 or {}),
        resource=dict(资源 or {}),
        scope=dict(作用域 or {}),
        location=位置,
    )
    if 追踪上下文 is not None:
        record.trace_id = getattr(追踪上下文, "trace_id", "") or ""
        record.span_id = getattr(追踪上下文, "span_id", "") or ""
    return record
