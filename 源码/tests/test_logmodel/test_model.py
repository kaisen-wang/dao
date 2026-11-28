"""结构化日志数据模型（dao.logmodel.model）的测试。"""

import json
import os
import sys
from datetime import datetime
from types import SimpleNamespace

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from dao.errors import 运行时错误
from dao.logmodel.context import TraceContext
from dao.logmodel.model import (
    SEVERITY_MAP,
    LogRecord,
    create_record,
    now_iso,
    severity_of,
)


class TestLogRecordDefaults:
    def test_default_values(self):
        record = LogRecord("启动")
        assert record.body == "启动"
        assert record.severity_text == "INFO"
        assert record.severity_number == 9
        assert record.timestamp
        assert record.observed_timestamp
        assert record.attributes == {}
        assert record.resource == {}
        assert record.scope == {}
        assert record.trace_id == ""
        assert record.span_id == ""
        assert record.location == ""

    def test_body_is_stringified(self):
        record = LogRecord(123)
        assert record.body == "123"
        assert isinstance(record.body, str)

    def test_timestamps_are_utc_iso_with_z(self):
        record = LogRecord("事件")
        for value in (record.timestamp, record.observed_timestamp):
            assert value.endswith("Z")
            parsed = datetime.fromisoformat(value)
            assert parsed.tzinfo is not None
            assert parsed.microsecond % 1000 == 0  # 毫秒精度：微秒部分是 1000 的整数倍

    def test_timestamp_not_overwritten_when_provided(self):
        record = LogRecord("事件", timestamp="2020-01-01T00:00:00.000Z")
        assert record.timestamp == "2020-01-01T00:00:00.000Z"

    def test_mutable_defaults_are_independent(self):
        first = LogRecord("一")
        second = LogRecord("二")
        first.attributes["k"] = "v"
        first.resource["k"] = "v"
        first.scope["k"] = "v"
        assert second.attributes == {}
        assert second.resource == {}
        assert second.scope == {}


class TestSerialization:
    def test_to_dict_has_all_otel_fields(self):
        record = LogRecord("支付成功")
        data = record.to_dict()
        assert set(data) == {
            "timestamp",
            "observed_timestamp",
            "severity_number",
            "severity_text",
            "body",
            "attributes",
            "resource",
            "scope",
            "trace_id",
            "span_id",
            "location",
        }
        assert data["body"] == "支付成功"
        assert data["severity_number"] == 9
        assert data["severity_text"] == "INFO"

    def test_to_dict_returns_copies_of_mutable_fields(self):
        record = LogRecord("事件", attributes={"a": 1}, resource={"b": 2}, scope={"c": 3})
        data = record.to_dict()
        data["attributes"]["a"] = 99
        data["resource"]["b"] = 99
        data["scope"]["c"] = 99
        assert record.attributes == {"a": 1}
        assert record.resource == {"b": 2}
        assert record.scope == {"c": 3}

    def test_to_json_keeps_chinese_and_parses_back(self):
        record = LogRecord("支付成功", attributes={"结果": "成功"})
        text = record.to_json()
        assert "支付成功" in text
        data = json.loads(text)
        assert data["body"] == "支付成功"
        assert data["attributes"] == {"结果": "成功"}

    def test_to_json_can_escape_unicode(self):
        record = LogRecord("支付成功")
        text = record.to_json(ensure_ascii=True)
        assert "\\u" in text
        assert json.loads(text)["body"] == "支付成功"


class TestCopy:
    def test_copy_deep_copies_mutable_fields(self):
        record = LogRecord(
            "事件",
            attributes={"user.id": "123"},
            resource={"service.name": "支付服务"},
            scope={"name": "服务"},
        )
        duplicate = record.copy()
        duplicate.attributes["user.id"] = "456"
        duplicate.resource["service.name"] = "订单服务"
        duplicate.scope["name"] = "订单"
        assert record.attributes == {"user.id": "123"}
        assert record.resource == {"service.name": "支付服务"}
        assert record.scope == {"name": "服务"}

    def test_copy_preserves_scalar_fields(self):
        record = LogRecord(
            "事件",
            severity_text="ERROR",
            severity_number=17,
            timestamp="2020-01-01T00:00:00.000Z",
            observed_timestamp="2020-01-01T00:00:01.000Z",
            trace_id="a" * 32,
            span_id="b" * 16,
            location="示例.道:1",
        )
        duplicate = record.copy()
        assert duplicate is not record
        assert duplicate.to_dict() == record.to_dict()


class TestSeverity:
    @pytest.mark.parametrize(
        ("level", "text", "number"),
        [
            ("调试", "DEBUG", 5),
            ("信息", "INFO", 9),
            ("警告", "WARN", 13),
            ("错误", "ERROR", 17),
            ("致命", "FATAL", 21),
        ],
    )
    def test_severity_of_chinese(self, level, text, number):
        assert severity_of(level) == (text, number)

    @pytest.mark.parametrize(
        ("level", "text", "number"),
        [
            ("DEBUG", "DEBUG", 5),
            ("Info", "INFO", 9),
            ("warn", "WARN", 13),
            ("WARNING", "WARN", 13),
            ("error", "ERROR", 17),
            ("CRITICAL", "FATAL", 21),
        ],
    )
    def test_severity_of_english(self, level, text, number):
        assert severity_of(level) == (text, number)

    @pytest.mark.parametrize(
        "value",
        [9, "9", "17", 0, 255],
    )
    def test_severity_of_numbers(self, value):
        text, number = severity_of(value)
        assert number == int(value)
        assert text in {"DEBUG", "INFO", "WARN", "ERROR", "FATAL"}

    @pytest.mark.parametrize("bad", ["未知", "", None, "abc", 300, -1, "300"])
    def test_severity_of_invalid_values(self, bad):
        with pytest.raises(运行时错误):
            severity_of(bad)

    def test_severity_map_is_complete(self):
        assert set(SEVERITY_MAP) == {"调试", "信息", "警告", "错误", "致命"}
        for text, number in SEVERITY_MAP.values():
            assert 0 <= number <= 255
            assert severity_of(text) == (text, number)


class TestCreateRecord:
    def test_default_level_and_empty_attributes(self):
        record = create_record("启动")
        assert record.body == "启动"
        assert record.severity_text == "INFO"
        assert record.severity_number == 9
        assert record.attributes == {}
        assert record.resource == {}
        assert record.scope == {}

    def test_level_attributes_and_location(self):
        record = create_record(
            "失败",
            级别="错误",
            属性={"order.id": "1"},
            资源={"service.name": "支付"},
            作用域={"name": "服务"},
            位置="示例.道:8",
        )
        assert record.severity_text == "ERROR"
        assert record.severity_number == 17
        assert record.attributes == {"order.id": "1"}
        assert record.resource == {"service.name": "支付"}
        assert record.scope == {"name": "服务"}
        assert record.location == "示例.道:8"

    def test_trace_context_injected(self):
        ctx = TraceContext("a" * 32, "b" * 16)
        record = create_record("事件", 追踪上下文=ctx)
        assert record.trace_id == "a" * 32
        assert record.span_id == "b" * 16

    def test_trace_context_missing_attributes_become_empty(self):
        record = create_record("事件", 追踪上下文=SimpleNamespace(trace_id="c" * 32))
        assert record.trace_id == "c" * 32
        assert record.span_id == ""

    def test_none_context_leaves_ids_empty(self):
        record = create_record("事件", 追踪上下文=None)
        assert record.trace_id == ""
        assert record.span_id == ""


class TestHelpers:
    def test_now_iso_format(self):
        value = now_iso()
        assert value.endswith("Z")
        assert "." in value
        assert len(value) == len("2026-11-28T09:12:03.123Z")

    def test_repr_contains_level_body_and_trace_prefix(self):
        record = LogRecord("支付成功", trace_id="abcdef" + "0" * 26)
        text = repr(record)
        assert "INFO" in text
        assert "支付成功" in text
        assert "abcdef" in text

    def test_repr_without_trace(self):
        assert "trace=-" in repr(LogRecord("事件"))
