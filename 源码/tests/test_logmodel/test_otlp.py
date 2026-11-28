"""OTLP/HTTP JSON 导出器与尾部采样导出器的测试。"""

from __future__ import annotations

import json
import os
import sys
import threading
import urllib.error
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import ClassVar

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from dao.errors import 运行时错误
from dao.logmodel.exporters import (
    MemoryExporter,
    TailSamplingExporter,
    尾部采样导出器,
)
from dao.logmodel.model import LogRecord
from dao.logmodel.otlp import OTLP导出器, OTLPHTTPExporter, to_otlp_json


def _record(**kwargs) -> LogRecord:
    defaults = {
        "body": "支付成功",
        "severity_text": "INFO",
        "severity_number": 9,
        "timestamp": "2024-11-01T00:00:00.000Z",
        "observed_timestamp": "2024-11-01T00:00:00.100Z",
    }
    defaults.update(kwargs)
    return LogRecord(**defaults)


class TestToOTLPJson:
    def test_empty_records(self):
        assert to_otlp_json([]) == {"resourceLogs": []}

    def test_single_record_structure(self):
        payload = to_otlp_json(
            [
                _record(
                    attributes={"user.id": "123"},
                    resource={"service.name": "支付服务"},
                    scope={"name": "服务"},
                    trace_id="a" * 32,
                    span_id="b" * 16,
                )
            ]
        )
        assert payload == {
            "resourceLogs": [
                {
                    "resource": {
                        "attributes": [
                            {
                                "key": "service.name",
                                "value": {"stringValue": "支付服务"},
                            }
                        ]
                    },
                    "scopeLogs": [
                        {
                            "scope": {"name": "服务"},
                            "logRecords": [
                                {
                                    "timeUnixNano": "1730419200000000000",
                                    "observedTimeUnixNano": "1730419200100000000",
                                    "severityNumber": 9,
                                    "severityText": "INFO",
                                    "body": {"stringValue": "支付成功"},
                                    "attributes": [
                                        {
                                            "key": "user.id",
                                            "value": {"stringValue": "123"},
                                        }
                                    ],
                                    "traceId": "a" * 32,
                                    "spanId": "b" * 16,
                                }
                            ],
                        }
                    ],
                }
            ]
        }

    def test_timestamp_to_nanos(self):
        record = _record(
            timestamp="2026-11-28T02:16:51.983Z",
            observed_timestamp="1970-01-01T00:00:00.000001Z",
        )
        log = to_otlp_json([record])["resourceLogs"][0]["scopeLogs"][0]["logRecords"][0]
        assert log["timeUnixNano"] == "1795832211983000000"
        assert log["observedTimeUnixNano"] == "1000"

    def test_naive_timestamp_treated_as_utc(self):
        record = _record(timestamp="2024-11-01T00:00:00")
        log = to_otlp_json([record])["resourceLogs"][0]["scopeLogs"][0]["logRecords"][0]
        assert log["timeUnixNano"] == "1730419200000000000"

    def test_bad_timestamp_falls_back_to_current_time(self, monkeypatch):
        monkeypatch.setattr("dao.logmodel.otlp.time.time_ns", lambda: 123456789)
        record = _record(timestamp="不是时间", observed_timestamp="不是时间")
        log = to_otlp_json([record])["resourceLogs"][0]["scopeLogs"][0]["logRecords"][0]
        assert log["timeUnixNano"] == "123456789"
        assert log["observedTimeUnixNano"] == "123456789"

    def test_empty_trace_fields_omitted(self):
        log = to_otlp_json([_record()])["resourceLogs"][0]["scopeLogs"][0]["logRecords"][0]
        assert "traceId" not in log
        assert "spanId" not in log

    def test_span_id_alone_is_kept(self):
        log = to_otlp_json([_record(span_id="c" * 16)])["resourceLogs"][0]["scopeLogs"][0][
            "logRecords"
        ][0]
        assert log["spanId"] == "c" * 16
        assert "traceId" not in log

    def test_attributes_preserve_order_and_stringify_values(self):
        record = _record(
            attributes={"first": 7, "second": True, "third": None, "fourth": ["x", 2]}
        )
        attrs = to_otlp_json([record])["resourceLogs"][0]["scopeLogs"][0]["logRecords"][0][
            "attributes"
        ]
        assert [item["key"] for item in attrs] == ["first", "second", "third", "fourth"]
        assert [item["value"]["stringValue"] for item in attrs] == [
            "7",
            "True",
            "None",
            "['x', 2]",
        ]

    def test_body_is_stringified(self):
        record = _record(body=12345)
        log = to_otlp_json([record])["resourceLogs"][0]["scopeLogs"][0]["logRecords"][0]
        assert log["body"] == {"stringValue": "12345"}

    def test_severity_number_is_numeric(self):
        record = _record(severity_number=17, severity_text="ERROR")
        log = to_otlp_json([record])["resourceLogs"][0]["scopeLogs"][0]["logRecords"][0]
        assert log["severityNumber"] == 17
        assert log["severityText"] == "ERROR"

    def test_grouping_by_resource_and_scope(self):
        records = [
            _record(body="一", resource={"service.name": "甲"}, scope={"name": "A"}),
            _record(body="二", resource={"service.name": "乙"}, scope={"name": "A"}),
            _record(body="三", resource={"service.name": "甲"}, scope={"name": "B"}),
            _record(body="四", resource={"service.name": "甲"}, scope={"name": "A"}),
        ]
        payload = to_otlp_json(records)
        groups = payload["resourceLogs"]
        assert len(groups) == 2
        first, second = groups
        assert first["resource"]["attributes"][0]["value"]["stringValue"] == "甲"
        assert second["resource"]["attributes"][0]["value"]["stringValue"] == "乙"
        assert [s["scope"]["name"] for s in first["scopeLogs"]] == ["A", "B"]
        assert [
            r["body"]["stringValue"] for r in first["scopeLogs"][0]["logRecords"]
        ] == ["一", "四"]
        assert len(second["scopeLogs"]) == 1

    def test_equivalent_resource_keys_merge(self):
        records = [
            _record(body="一", resource={"a": "1", "b": "2"}),
            _record(body="二", resource={"b": "2", "a": "1"}),
        ]
        payload = to_otlp_json(records)
        assert len(payload["resourceLogs"]) == 1
        assert len(payload["resourceLogs"][0]["scopeLogs"][0]["logRecords"]) == 2

    def test_empty_resource_and_scope_use_empty_groups(self):
        payload = to_otlp_json([_record(), _record(body="二")])
        assert payload["resourceLogs"][0]["resource"] == {"attributes": []}
        assert payload["resourceLogs"][0]["scopeLogs"][0]["scope"] == {}
        assert len(payload["resourceLogs"][0]["scopeLogs"][0]["logRecords"]) == 2

    def test_all_values_are_json_serializable(self):
        payload = to_otlp_json(
            [_record(resource={"n": object()}, attributes={"x": object()}, scope={"v": 3})]
        )
        encoded = json.dumps(payload, ensure_ascii=False)
        assert isinstance(encoded, str)
        assert "支付成功" in encoded


class _CaptureHandler(BaseHTTPRequestHandler):
    captured: ClassVar[list[dict]] = []

    def do_POST(self) -> None:
        length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(length)
        type(self).captured.append(
            {
                "path": self.path,
                "content_type": self.headers.get("Content-Type"),
                "method": self.command,
                "body": body,
            }
        )
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"{}")

    def log_message(self, format: str, *args) -> None:
        pass


@pytest.fixture
def capture_server():
    server = ThreadingHTTPServer(("127.0.0.1", 0), _CaptureHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    _CaptureHandler.captured.clear()
    try:
        yield server
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)
        _CaptureHandler.captured.clear()


class _FakeResponse:
    def __init__(self, status: int) -> None:
        self.status = status

    def __enter__(self):
        return self

    def __exit__(self, *args) -> bool:
        return False


class TestOTLPHTTPExporter:
    def test_defaults(self):
        exporter = OTLPHTTPExporter("http://localhost:4318/v1/logs")
        assert exporter.endpoint == "http://localhost:4318/v1/logs"
        assert exporter.headers == {"Content-Type": "application/json"}
        assert exporter.timeout == 5.0

    @pytest.mark.parametrize("endpoint", ["", "   ", None])
    def test_empty_endpoint_raises_chinese_error(self, endpoint):
        with pytest.raises(运行时错误, match="端点不能为空"):
            OTLPHTTPExporter(endpoint)

    def test_invalid_endpoint_url_raises_chinese_error(self):
        with pytest.raises(运行时错误, match="导出失败"):
            OTLPHTTPExporter("不是地址").export([_record()])

    def test_custom_headers_override_defaults(self):
        exporter = OTLPHTTPExporter(
            "http://localhost:4318/v1/logs",
            headers={"Content-Type": "application/json; charset=utf-8", "X-Token": "t"},
            timeout=1.5,
        )
        assert exporter.headers["Content-Type"] == "application/json; charset=utf-8"
        assert exporter.headers["X-Token"] == "t"
        assert exporter.timeout == 1.5

    def test_successful_post(self, capture_server):
        endpoint = f"http://127.0.0.1:{capture_server.server_port}/v1/logs"
        exporter = OTLPHTTPExporter(endpoint)
        exporter.export([_record(attributes={"user.id": "123"})])
        assert len(_CaptureHandler.captured) == 1
        request = _CaptureHandler.captured[0]
        assert request["path"] == "/v1/logs"
        assert request["method"] == "POST"
        assert request["content_type"] == "application/json"
        body = json.loads(request["body"].decode("utf-8"))
        assert body["resourceLogs"][0]["scopeLogs"][0]["logRecords"][0]["body"] == {
            "stringValue": "支付成功"
        }

    def test_flush_and_close_are_noop(self):
        exporter = OTLPHTTPExporter("http://localhost:4318/v1/logs")
        assert exporter.flush() is None
        assert exporter.close() is None

    def test_non_2xx_raises_chinese_error(self, monkeypatch):
        monkeypatch.setattr(
            "dao.logmodel.otlp.urllib.request.urlopen",
            lambda *args, **kwargs: _FakeResponse(503),
        )
        exporter = OTLPHTTPExporter("http://localhost:4318/v1/logs")
        with pytest.raises(运行时错误, match="503"):
            exporter.export([_record()])

    def test_http_error_raises_chinese_error(self, monkeypatch):
        def fail(*args, **kwargs):
            raise urllib.error.HTTPError(
                "http://localhost:4318/v1/logs", 404, "Not Found", {}, None
            )

        monkeypatch.setattr("dao.logmodel.otlp.urllib.request.urlopen", fail)
        with pytest.raises(运行时错误, match="404"):
            OTLPHTTPExporter("http://localhost:4318/v1/logs").export([_record()])

    def test_url_error_raises_chinese_error(self, monkeypatch):
        def fail(*args, **kwargs):
            raise urllib.error.URLError("连接被拒绝")

        monkeypatch.setattr("dao.logmodel.otlp.urllib.request.urlopen", fail)
        with pytest.raises(运行时错误, match="连接被拒绝"):
            OTLPHTTPExporter("http://localhost:4318/v1/logs").export([_record()])

    def test_alias(self):
        assert OTLP导出器 is OTLPHTTPExporter


class TestTailSamplingExporter:
    @staticmethod
    def _records(prefix: str, count: int, **kwargs) -> list[LogRecord]:
        return [
            _record(body=f"{prefix}{i}", trace_id=prefix * 32, **kwargs)
            for i in range(count)
        ]

    def test_invalid_ratio(self):
        with pytest.raises(运行时错误, match="采样比例"):
            TailSamplingExporter(MemoryExporter(), ratio=1.5)
        with pytest.raises(运行时错误, match="采样比例"):
            TailSamplingExporter(MemoryExporter(), ratio=-0.1)

    def test_invalid_exporter(self):
        with pytest.raises(运行时错误, match="export"):
            TailSamplingExporter(object())

    def test_invalid_max_traces(self):
        with pytest.raises(运行时错误, match="max_traces"):
            TailSamplingExporter(MemoryExporter(), max_traces=0)

    def test_error_trace_kept_entirely(self, monkeypatch):
        inner = MemoryExporter()
        exporter = TailSamplingExporter(inner, ratio=0.0)
        records = self._records("a", 3)
        records[1].severity_number = 17
        records[1].severity_text = "ERROR"
        monkeypatch.setattr("dao.logmodel.exporters.random.random", lambda: 0.99)
        exporter.export(records)
        assert inner.records == []
        exporter.flush()
        assert inner.records == records

    def test_error_text_alone_keeps_trace(self, monkeypatch):
        inner = MemoryExporter()
        exporter = TailSamplingExporter(inner, ratio=0.0)
        records = self._records("b", 2, severity_text="FATAL", severity_number=1)
        monkeypatch.setattr("dao.logmodel.exporters.random.random", lambda: 0.99)
        exporter.export(records)
        exporter.flush()
        assert inner.records == records

    def test_normal_trace_sampled_as_whole(self, monkeypatch):
        inner = MemoryExporter()
        exporter = TailSamplingExporter(inner, ratio=0.5)
        monkeypatch.setattr("dao.logmodel.exporters.random.random", lambda: 0.2)
        exporter.export(self._records("c", 3))
        exporter.flush()
        assert len(inner.records) == 3

    def test_normal_trace_dropped_as_whole(self, monkeypatch):
        inner = MemoryExporter()
        exporter = TailSamplingExporter(inner, ratio=0.5)
        monkeypatch.setattr("dao.logmodel.exporters.random.random", lambda: 0.8)
        exporter.export(self._records("d", 3))
        exporter.flush()
        assert inner.records == []

    def test_one_random_decision_per_trace(self, monkeypatch):
        inner = MemoryExporter()
        exporter = TailSamplingExporter(inner, ratio=0.5)
        calls: list[float] = []

        def fake_random():
            calls.append(0.2)
            return 0.2

        monkeypatch.setattr("dao.logmodel.exporters.random.random", fake_random)
        exporter.export(self._records("e", 5))
        exporter.flush()
        assert len(calls) == 1

    def test_keep_errors_false_drops_error_trace(self, monkeypatch):
        inner = MemoryExporter()
        exporter = TailSamplingExporter(inner, ratio=0.0, keep_errors=False)
        monkeypatch.setattr("dao.logmodel.exporters.random.random", lambda: 0.9)
        exporter.export(self._records("f", 2, severity_text="ERROR", severity_number=17))
        exporter.flush()
        assert inner.records == []

    def test_without_trace_immediate_keep(self, monkeypatch):
        inner = MemoryExporter()
        exporter = TailSamplingExporter(inner, ratio=1.0)
        record = _record(body="无追踪")
        exporter.export([record])
        assert inner.records == [record]
        assert exporter._buffers == {}

    def test_without_trace_immediate_drop(self, monkeypatch):
        inner = MemoryExporter()
        exporter = TailSamplingExporter(inner, ratio=0.0, keep_errors=False)
        exporter.export([_record(body="无追踪")])
        assert inner.records == []

    def test_without_trace_error_kept_at_zero_ratio(self, monkeypatch):
        inner = MemoryExporter()
        exporter = TailSamplingExporter(inner, ratio=0.0)
        record = _record(body="错误", severity_text="ERROR", severity_number=17)
        monkeypatch.setattr("dao.logmodel.exporters.random.random", lambda: 0.99)
        exporter.export([record])
        assert inner.records == [record]

    def test_max_traces_bounds_buffer(self, monkeypatch):
        inner = MemoryExporter()
        exporter = TailSamplingExporter(inner, ratio=1.0, max_traces=2)
        exporter.export(self._records("a", 1))
        exporter.export(self._records("b", 1))
        exporter.export(self._records("c", 1))
        assert len(exporter._buffers) == 2
        exporter.flush()
        assert len(inner.records) == 3

    def test_flush_calls_inner_flush(self):
        class CountingExporter(MemoryExporter):
            flushes = 0

            def flush(self) -> None:
                type(self).flushes += 1

        inner = CountingExporter()
        exporter = TailSamplingExporter(inner)
        exporter.flush()
        assert CountingExporter.flushes == 1

    def test_close_is_idempotent(self):
        class CountingExporter(MemoryExporter):
            closes = 0

            def close(self) -> None:
                type(self).closes += 1

        inner = CountingExporter()
        exporter = TailSamplingExporter(inner, ratio=1.0)
        exporter.export(self._records("z", 2))
        exporter.close()
        exporter.close()
        assert len(inner.records) == 2
        assert CountingExporter.closes == 1

    def test_alias(self):
        assert 尾部采样导出器 is TailSamplingExporter
