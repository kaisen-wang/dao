"""W3C 追踪上下文与资源元数据（dao.logmodel.context）的测试。"""

import os
import re
import sys
import threading
from dataclasses import FrozenInstanceError

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from dao.errors import 运行时错误
from dao.logmodel.context import (
    Resource,
    TraceContext,
    clear_trace,
    current_resource,
    current_trace,
    current_trace_context,
    extract_headers,
    get_resource,
    inject_headers,
    new_span_id,
    new_trace_id,
    parse_baggage,
    parse_traceparent,
    set_resource,
    start_trace,
)

TRACE_ID = "4bf92f3577b34da6a3ce929d0e0e4736"
SPAN_ID = "00f067aa0ba902b7"


@pytest.fixture(autouse=True)
def _reset_context():
    """每个用例前后隔离 ContextVar，避免测试间互相污染。"""
    current_trace.set(None)
    current_resource.set(None)
    yield
    current_trace.set(None)
    current_resource.set(None)


class TestIdGeneration:
    def test_new_trace_id_format(self):
        value = new_trace_id()
        assert re.fullmatch(r"[0-9a-f]{32}", value)

    def test_new_span_id_format(self):
        value = new_span_id()
        assert re.fullmatch(r"[0-9a-f]{16}", value)

    def test_generated_ids_are_unique(self):
        assert len({new_trace_id() for _ in range(20)}) == 20
        assert len({new_span_id() for _ in range(20)}) == 20


class TestTraceContext:
    def test_traceparent_format(self):
        ctx = TraceContext(TRACE_ID, SPAN_ID, "01")
        assert ctx.traceparent() == f"00-{TRACE_ID}-{SPAN_ID}-01"

    def test_traceparent_lowercases_ids(self):
        ctx = TraceContext(TRACE_ID.upper(), SPAN_ID.upper(), "AA")
        assert ctx.trace_id == TRACE_ID.upper()
        assert ctx.traceparent() == f"00-{TRACE_ID}-{SPAN_ID}-aa"

    def test_invalid_ids_raise(self):
        for trace_id, span_id in [
            ("abc", SPAN_ID),
            (TRACE_ID, "abc"),
            ("g" * 32, SPAN_ID),
            (TRACE_ID, "z" * 16),
        ]:
            with pytest.raises(运行时错误):
                TraceContext(trace_id, span_id)

    def test_baggage_header(self):
        ctx = TraceContext(TRACE_ID, SPAN_ID, baggage={"租户": "acme", "区域": "华东"})
        assert ctx.baggage_header() == "租户=acme,区域=华东"

    def test_to_dict(self):
        ctx = TraceContext(TRACE_ID, SPAN_ID, "01", {"租户": "acme"})
        assert ctx.to_dict() == {
            "trace.id": TRACE_ID,
            "span.id": SPAN_ID,
            "trace.flags": "01",
            "baggage.租户": "acme",
        }

    def test_frozen(self):
        ctx = TraceContext(TRACE_ID, SPAN_ID)
        with pytest.raises(FrozenInstanceError):
            ctx.trace_id = "0" * 32


class TestParseTraceparent:
    def test_parse_valid(self):
        ctx = parse_traceparent(f"00-{TRACE_ID}-{SPAN_ID}-01")
        assert ctx is not None
        assert (ctx.trace_id, ctx.span_id, ctx.trace_flags) == (TRACE_ID, SPAN_ID, "01")

    def test_parse_uppercase_input(self):
        ctx = parse_traceparent(f"00-{TRACE_ID.upper()}-{SPAN_ID.upper()}-AA")
        assert ctx is not None
        assert ctx.trace_id == TRACE_ID
        assert ctx.span_id == SPAN_ID
        assert ctx.trace_flags == "aa"

    def test_parse_strips_whitespace(self):
        ctx = parse_traceparent(f"  00-{TRACE_ID}-{SPAN_ID}-00  ")
        assert ctx is not None
        assert ctx.trace_id == TRACE_ID

    @pytest.mark.parametrize(
        "value",
        [
            "",
            "not-a-header",
            f"xx-{TRACE_ID}-{SPAN_ID}-00",
            f"00-{TRACE_ID}-{SPAN_ID}",
            f"00-{TRACE_ID}-{SPAN_ID}-0",
            None,
            123,
        ],
    )
    def test_parse_invalid_returns_none(self, value):
        assert parse_traceparent(value) is None

    def test_parse_all_zero_trace_id_returns_none(self):
        assert parse_traceparent(f"00-{'0' * 32}-{SPAN_ID}-00") is None

    def test_parse_all_zero_span_id_returns_none(self):
        assert parse_traceparent(f"00-{TRACE_ID}-{'0' * 16}-00") is None

    def test_parse_ff_version_returns_none(self):
        assert parse_traceparent(f"ff-{TRACE_ID}-{SPAN_ID}-00") is None


class TestParseBaggage:
    def test_parse_valid(self):
        assert parse_baggage("租户=acme, 区域=华东") == {"租户": "acme", "区域": "华东"}

    def test_ignores_malformed_pairs(self):
        assert parse_baggage("a=1, bad, =空, b = 2") == {"a": "1", "b": "2"}

    def test_non_string_returns_empty(self):
        assert parse_baggage(None) == {}
        assert parse_baggage(123) == {}


class TestHeaderRoundTrip:
    def test_extract_headers_valid(self):
        headers = {
            "TraceParent": f"00-{TRACE_ID}-{SPAN_ID}-01",
            "Baggage": "租户=acme",
        }
        ctx = extract_headers(headers)
        assert ctx is not None
        assert ctx.trace_id == TRACE_ID
        assert ctx.span_id == SPAN_ID
        assert ctx.trace_flags == "01"
        assert ctx.baggage == {"租户": "acme"}

    def test_extract_headers_with_list_values(self):
        headers = {
            "traceparent": [f"00-{TRACE_ID}-{SPAN_ID}-00"],
            "baggage": ["租户=acme"],
        }
        ctx = extract_headers(headers)
        assert ctx is not None
        assert ctx.baggage == {"租户": "acme"}

    @pytest.mark.parametrize(
        "headers",
        [
            {},
            {"traceparent": "无效"},
            {"traceparent": f"00-{'0' * 32}-{SPAN_ID}-00"},
            None,
            "not-a-dict",
        ],
    )
    def test_extract_headers_returns_none(self, headers):
        assert extract_headers(headers) is None

    def test_inject_headers_without_context(self):
        assert inject_headers() == {}
        assert inject_headers({"X-Test": "1"}) == {"X-Test": "1"}

    def test_inject_headers_with_context(self):
        start_trace(baggage={"租户": "acme"})
        headers = inject_headers({"X-Request": "abc"})
        assert headers["X-Request"] == "abc"
        assert re.fullmatch(r"00-[0-9a-f]{32}-[0-9a-f]{16}-00", headers["traceparent"])
        assert headers["baggage"] == "租户=acme"

    def test_inject_extract_roundtrip(self):
        original = start_trace(baggage={"租户": "acme", "区域": "华东"})
        headers = inject_headers()
        restored = extract_headers(headers)
        assert restored is not None
        assert restored.trace_id == original.trace_id
        assert restored.span_id == original.span_id
        assert restored.baggage == original.baggage
        assert restored.traceparent() == original.traceparent()


class TestCurrentTrace:
    def test_start_trace_activates_context(self):
        ctx = start_trace(baggage={"租户": "acme"})
        assert current_trace_context() is ctx
        assert ctx.baggage == {"租户": "acme"}
        assert re.fullmatch(r"[0-9a-f]{32}", ctx.trace_id)

    def test_start_trace_with_explicit_ids(self):
        ctx = start_trace(trace_id=TRACE_ID.upper(), span_id=SPAN_ID.upper())
        assert ctx.trace_id == TRACE_ID
        assert ctx.span_id == SPAN_ID

    def test_clear_trace(self):
        start_trace()
        assert current_trace_context() is not None
        clear_trace()
        assert current_trace_context() is None

    def test_contextvar_token_reset(self):
        ctx = TraceContext(TRACE_ID, SPAN_ID)
        token = current_trace.set(ctx)
        try:
            assert current_trace_context() is ctx
        finally:
            current_trace.reset(token)
        assert current_trace_context() is None

    def test_contextvar_isolated_between_threads(self):
        main_ctx = start_trace()
        observed = {}

        def worker():
            observed["before"] = current_trace_context()
            worker_ctx = start_trace()
            observed["after"] = current_trace_context()
            observed["ctx"] = worker_ctx

        thread = threading.Thread(target=worker)
        thread.start()
        thread.join()
        assert observed["before"] is None
        assert observed["after"] is observed["ctx"]
        assert observed["ctx"] is not main_ctx
        assert current_trace_context() is main_ctx


class TestResource:
    def test_default_resource(self):
        resource = Resource()
        assert resource.service_name == "道应用"
        assert resource.host_name == ""
        assert resource.environment == ""

    def test_to_dict_default(self):
        assert Resource().to_dict() == {"service.name": "道应用"}

    def test_to_dict_skips_empty_and_includes_attributes(self):
        resource = Resource(
            service_name="支付服务",
            host_name="node-1",
            environment="生产",
            attributes={"team": "pay"},
        )
        assert resource.to_dict() == {
            "service.name": "支付服务",
            "host.name": "node-1",
            "environment": "生产",
            "team": "pay",
        }
        assert Resource(host_name="node-1").to_dict() == {
            "service.name": "道应用",
            "host.name": "node-1",
        }

    def test_set_resource(self):
        resource = set_resource(
            service_name="支付服务",
            host_name="node-1",
            environment="生产",
            attributes={"team": "pay"},
        )
        assert get_resource() is resource
        assert resource.to_dict()["service.name"] == "支付服务"
        assert resource.to_dict()["environment"] == "生产"

    def test_set_resource_keeps_previous_values_and_merges_attributes(self):
        set_resource(service_name="支付服务", attributes={"team": "pay"})
        resource = set_resource(host_name="node-2", attributes={"region": "华东"})
        assert resource.service_name == "支付服务"
        assert resource.host_name == "node-2"
        assert resource.attributes == {"team": "pay", "region": "华东"}

    def test_get_resource_default(self):
        assert get_resource().to_dict() == {"service.name": "道应用"}
