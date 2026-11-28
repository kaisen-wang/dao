"""OTLP/HTTP JSON 导出器（参考 OpenTelemetry OTLP/HTTP 协议）。

把结构化日志 :class:`~dao.logmodel.model.LogRecord` 转换为 OTLP/HTTP JSON
请求体，并通过标准库 :mod:`urllib.request` 发送到 Collector（默认端口 4318
的 ``/v1/logs`` 端点）。不依赖任何第三方包。
"""

from __future__ import annotations

import json
import time
import urllib.error
import urllib.request
from datetime import datetime, timedelta, timezone
from typing import Any

from ..errors import 运行时错误
from .model import LogRecord

# OTLP/HTTP JSON 要求 Content-Type 为 application/json。
_DEFAULT_HEADERS: dict[str, str] = {"Content-Type": "application/json"}
_EPOCH = datetime(1970, 1, 1, tzinfo=timezone.utc)  # noqa: UP017  兼容 Python 3.10


def _to_nanos(timestamp: str) -> str:
    """把 ISO-8601 UTC 时间戳转换为纳秒字符串。

    解析失败（空串、格式错误、越界等）时退化为当前时间的纳秒值。
    """
    try:
        text = str(timestamp).strip()
        if not text:
            raise ValueError("空时间戳")
        # Python 3.10 的 fromisoformat 不识别末尾的 Z。
        if text.endswith(("Z", "z")):
            text = text[:-1] + "+00:00"
        value = datetime.fromisoformat(text)
        if value.tzinfo is None:
            value = value.replace(tzinfo=timezone.utc)  # noqa: UP017  兼容 Python 3.10
        delta: timedelta = value.astimezone(timezone.utc) - _EPOCH  # noqa: UP017
        # 用整数运算避免浮点精度损失：毫秒精度的 ISO 串也能得到精确纳秒。
        nanos = (
            delta.days * 86_400 + delta.seconds
        ) * 1_000_000_000 + delta.microseconds * 1_000
        return str(nanos)
    except (TypeError, ValueError, OverflowError, OSError):
        return str(time.time_ns())


def _string_value(value: Any) -> dict[str, str]:
    """把任意属性值转换为 OTLP 的 AnyValue ``stringValue`` 形式。"""
    return {"stringValue": str(value)}


def _attributes(mapping: dict) -> list[dict[str, Any]]:
    """按原始插入顺序把字典转换为 OTLP 属性数组。"""
    return [
        {"key": str(key), "value": _string_value(value)}
        for key, value in mapping.items()
    ]


def _group_key(mapping: dict) -> str:
    """用 JSON 序列化结果作为分组键（键排序后等价字典共享一组）。"""
    return json.dumps(mapping, sort_keys=True, ensure_ascii=False, default=str)


def _scope_dict(scope: dict) -> dict[str, str]:
    """把 scope 转换为 JSON 可序列化的普通字符串字典。"""
    return {str(key): str(value) for key, value in scope.items()}


def _log_record(record: LogRecord) -> dict[str, Any]:
    """把单条 LogRecord 转换为 OTLP JSON 的 LogRecord 对象。"""
    result: dict[str, Any] = {
        "timeUnixNano": _to_nanos(record.timestamp),
        "observedTimeUnixNano": _to_nanos(record.observed_timestamp),
        "severityNumber": int(record.severity_number),
        "severityText": str(record.severity_text),
        "body": _string_value(record.body),
        "attributes": _attributes(record.attributes),
    }
    if record.trace_id:
        result["traceId"] = str(record.trace_id)
    if record.span_id:
        result["spanId"] = str(record.span_id)
    return result


def to_otlp_json(records: list[LogRecord]) -> dict[str, Any]:
    """把一批记录转换为 OTLP/HTTP JSON 请求体。

    先按 ``resource``、再按 ``scope`` 分组为 resourceLogs / scopeLogs；
    同一组内的记录保持原始顺序。
    """
    # 分组键 -> (原始 resource/scope 字典, 该组记录列表)
    resources: dict[str, tuple[dict, dict[str, tuple[dict, list[LogRecord]]]]] = {}
    for record in records:
        resource = dict(record.resource)
        scope = dict(record.scope)
        resource_key = _group_key(resource)
        if resource_key not in resources:
            resources[resource_key] = (resource, {})
        scopes = resources[resource_key][1]
        scope_key = _group_key(scope)
        if scope_key not in scopes:
            scopes[scope_key] = (scope, [])
        scopes[scope_key][1].append(record)

    resource_logs: list[dict[str, Any]] = []
    for resource, scopes in resources.values():
        scope_logs = [
            {
                "scope": _scope_dict(scope),
                "logRecords": [_log_record(item) for item in group_records],
            }
            for scope, group_records in scopes.values()
        ]
        resource_logs.append(
            {
                "resource": {"attributes": _attributes(resource)},
                "scopeLogs": scope_logs,
            }
        )
    return {"resourceLogs": resource_logs}


class OTLPHTTPExporter:
    """把日志批量 POST 到 OTLP/HTTP Collector 端点的导出器。"""

    def __init__(
        self,
        endpoint: str,
        headers: dict | None = None,
        timeout: float = 5.0,
    ) -> None:
        if endpoint is None or not str(endpoint).strip():
            raise 运行时错误("OTLP/HTTP 导出端点不能为空")
        self.endpoint = str(endpoint)
        self.headers: dict[str, str] = dict(_DEFAULT_HEADERS)
        if headers:
            # 用户提供的同名键覆盖默认值。
            self.headers.update({str(key): str(value) for key, value in headers.items()})
        self.timeout = float(timeout)

    def export(self, records: list[LogRecord]) -> None:
        """构造 OTLP/HTTP JSON 请求体并立即发送；失败时抛中文运行时错误。"""
        payload = json.dumps(to_otlp_json(records), ensure_ascii=False).encode("utf-8")
        try:
            request = urllib.request.Request(
                self.endpoint,
                data=payload,
                headers=self.headers,
                method="POST",
            )
            with urllib.request.urlopen(request, timeout=self.timeout) as response:
                status = response.status
        except urllib.error.HTTPError as exc:
            reason = f" HTTP {exc.code} {exc.reason}" if exc.reason else f" HTTP {exc.code}"
            raise 运行时错误(
                f"OTLP/HTTP 导出失败:{reason}，端点: {self.endpoint}"
            ) from exc
        except urllib.error.URLError as exc:
            raise 运行时错误(
                f"OTLP/HTTP 导出失败: 网络错误 {exc.reason}，端点: {self.endpoint}"
            ) from exc
        except (OSError, ValueError) as exc:
            raise 运行时错误(
                f"OTLP/HTTP 导出失败: 网络错误 {exc}，端点: {self.endpoint}"
            ) from exc
        if not 200 <= int(status) < 300:
            raise 运行时错误(
                f"OTLP/HTTP 导出失败: HTTP {status}，端点: {self.endpoint}"
            )

    def flush(self) -> None:
        """立即发送型导出器无需刷新。"""

    def close(self) -> None:
        """立即发送型导出器无需释放资源。"""


# 中文别名，便于道语言侧与中文文档使用。
OTLP导出器 = OTLPHTTPExporter

__all__ = [
    "OTLP导出器",
    "OTLPHTTPExporter",
    "to_otlp_json",
]
