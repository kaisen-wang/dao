"""分布式追踪上下文与资源元数据传播。

遵循 W3C Trace Context 标准：traceparent 头格式为
``00-<32位trace_id>-<16位span_id>-<2位flags>``。上下文存放在 ContextVar 中，
保证线程与协程隔离；baggage 用于携带请求级元数据（如租户 ID）。
"""

from __future__ import annotations

import os
import re
import secrets
from contextvars import ContextVar
from dataclasses import dataclass, field

from ..errors import 运行时错误

_TRACEPARENT_RE = re.compile(
    r"^([0-9a-f]{2})-([0-9a-f]{32})-([0-9a-f]{16})-([0-9a-f]{2})$", re.IGNORECASE
)
_ALL_ZERO_TRACE = "0" * 32
_ALL_ZERO_SPAN = "0" * 16


@dataclass(frozen=True)
class TraceContext:
    """一次分布式请求的追踪上下文。"""

    trace_id: str
    span_id: str
    trace_flags: str = "00"
    baggage: dict = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not _TRACEPARENT_RE.fullmatch(self.traceparent()):
            raise 运行时错误("无效的追踪 ID 或跨度 ID")

    def traceparent(self) -> str:
        """返回 W3C traceparent 头字符串。"""
        return (
            f"00-{self.trace_id.lower()}-"
            f"{self.span_id.lower()}-{self.trace_flags.lower()}"
        )

    def baggage_header(self) -> str:
        """返回 W3C baggage 头字符串。"""
        return ",".join(f"{key}={value}" for key, value in self.baggage.items())

    def to_dict(self) -> dict:
        """转换为可写入日志属性的字典。"""
        return {
            "trace.id": self.trace_id,
            "span.id": self.span_id,
            "trace.flags": self.trace_flags,
            **{f"baggage.{key}": value for key, value in self.baggage.items()},
        }


current_trace: ContextVar[TraceContext | None] = ContextVar(
    "dao_current_trace", default=None
)


def new_trace_id() -> str:
    """生成 32 位十六进制 TraceId。"""
    return secrets.token_hex(16)


def new_span_id() -> str:
    """生成 16 位十六进制 SpanId。"""
    return secrets.token_hex(8)


def start_trace(baggage=None, trace_id: str | None = None, span_id: str | None = None) -> TraceContext:
    """创建并激活一条新追踪，返回创建的上下文。"""
    ctx = TraceContext(
        trace_id=(trace_id or new_trace_id()).lower(),
        span_id=(span_id or new_span_id()).lower(),
        baggage=dict(baggage or {}),
    )
    current_trace.set(ctx)
    return ctx


def parse_traceparent(value: str) -> TraceContext | None:
    """解析 W3C traceparent 头；格式无效或全零 ID 返回 None。"""
    if not isinstance(value, str):
        return None
    match = _TRACEPARENT_RE.fullmatch(value.strip())
    if match is None:
        return None
    version, trace_id, span_id, flags = match.groups()
    if version.lower() == "ff":
        return None
    if trace_id.lower() == _ALL_ZERO_TRACE or span_id.lower() == _ALL_ZERO_SPAN:
        return None
    return TraceContext(trace_id.lower(), span_id.lower(), flags.lower())


def parse_baggage(value: str) -> dict:
    """解析 W3C baggage 头，忽略格式非法的键值对。"""
    result: dict = {}
    if not isinstance(value, str):
        return result
    for part in value.split(","):
        key, sep, item = part.strip().partition("=")
        if sep and key:
            result[key.strip()] = item.strip()
    return result


def extract_headers(headers: dict) -> TraceContext | None:
    """从 HTTP 请求头字典中提取并解析追踪上下文（键名大小写不敏感）。"""
    if not isinstance(headers, dict):
        return None
    normalized = {str(key).lower(): value for key, value in headers.items()}
    raw = normalized.get("traceparent")
    if raw is None:
        return None
    # 兼容多个头值（列表 / 元组）的情况
    if isinstance(raw, (list, tuple)):
        raw = raw[0] if raw else None
    ctx = parse_traceparent(raw)
    if ctx is None:
        return None
    baggage = normalized.get("baggage")
    if isinstance(baggage, (list, tuple)):
        baggage = baggage[0] if baggage else None
    return TraceContext(
        trace_id=ctx.trace_id,
        span_id=ctx.span_id,
        trace_flags=ctx.trace_flags,
        baggage=parse_baggage(baggage) if baggage else {},
    )


def inject_headers(headers: dict | None = None) -> dict:
    """把当前追踪上下文注入请求头，返回新的字典。"""
    result = dict(headers or {})
    ctx = current_trace.get()
    if ctx is not None:
        result["traceparent"] = ctx.traceparent()
        if ctx.baggage:
            result["baggage"] = ctx.baggage_header()
    return result


def current_trace_context() -> TraceContext | None:
    """返回当前激活的追踪上下文。"""
    return current_trace.get()


def clear_trace() -> None:
    """清除当前追踪上下文。"""
    current_trace.set(None)


@dataclass
class Resource:
    """日志产生源的元数据（OpenTelemetry Resource）。"""

    service_name: str = "道应用"
    host_name: str = ""
    environment: str = ""
    attributes: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        """转换为扁平属性字典，键采用 OTel 语义约定。"""
        result = {"service.name": self.service_name}
        if self.host_name:
            result["host.name"] = self.host_name
        if self.environment:
            result["environment"] = self.environment
        result.update(self.attributes)
        return result


current_resource: ContextVar[Resource | None] = ContextVar(
    "dao_current_resource", default=None
)


def set_resource(
    service_name: str | None = None,
    host_name: str | None = None,
    environment: str | None = None,
    attributes: dict | None = None,
) -> Resource:
    """设置并激活全局资源元数据；未指定字段保留上一次的值。"""
    previous = current_resource.get() or Resource()
    resource = Resource(
        service_name=service_name if service_name is not None else previous.service_name,
        host_name=host_name if host_name is not None else previous.host_name,
        environment=environment if environment is not None else previous.environment,
        attributes={**previous.attributes, **(attributes or {})},
    )
    current_resource.set(resource)
    return resource


def resource_from_env() -> Resource:
    """从环境变量构建资源元数据，不修改当前 ContextVar。

    支持以下变量：

    * ``OTEL_SERVICE_NAME``：服务名，缺省为「道应用」；
    * ``OTEL_RESOURCE_ATTRIBUTES``：逗号分隔的 ``key=value`` 属性；
    * ``HOSTNAME``：主机名；
    * ``DEPLOY_ENV`` / ``ENVIRONMENT``：部署环境（前者优先）。

    属性项缺少等号或键为空时忽略，键值两侧空白会被去除。
    """
    attributes: dict = {}
    raw_attributes = os.environ.get("OTEL_RESOURCE_ATTRIBUTES")
    if raw_attributes:
        for part in raw_attributes.split(","):
            key, sep, value = part.partition("=")
            key = key.strip()
            if sep and key:
                attributes[key] = value.strip()
    return Resource(
        service_name=os.environ.get("OTEL_SERVICE_NAME") or "道应用",
        host_name=os.environ.get("HOSTNAME", ""),
        environment=os.environ.get("DEPLOY_ENV")
        or os.environ.get("ENVIRONMENT")
        or "",
        attributes=attributes,
    )


def get_resource() -> Resource:
    """返回当前资源元数据；首次调用且未设置时从环境变量加载并激活。"""
    resource = current_resource.get()
    if resource is None:
        resource = resource_from_env()
        current_resource.set(resource)
    return resource
