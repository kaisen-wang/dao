"""结构化日志处理器、导出器与管道的测试。"""

import io
import json
import os
import sys
import threading

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from dao.errors import 运行时错误
from dao.logmodel.context import (
    current_resource,
    current_trace,
    set_resource,
    start_trace,
)
from dao.logmodel.exporters import (
    ConsoleExporter,
    FileExporter,
    MemoryExporter,
    内存导出器,
    控制台导出器,
    文件导出器,
)
from dao.logmodel.model import LogRecord, create_record
from dao.logmodel.pipeline import (
    AsyncLogPipeline,
    LogPipeline,
    异步日志管道,
    日志管道,
)
from dao.logmodel.processors import (
    AttributeInjector,
    LevelFilter,
    RedactionProcessor,
    ResourceInjector,
    SamplingProcessor,
    TraceInjector,
    属性注入处理器,
    级别过滤器,
    脱敏处理器,
    资源注入处理器,
    采样处理器,
    链路注入处理器,
)


@pytest.fixture(autouse=True)
def _reset_context():
    """隔离 ContextVar，避免测试间互相污染。"""
    current_trace.set(None)
    current_resource.set(None)
    yield
    current_trace.set(None)
    current_resource.set(None)


class TestProcessors:
    def test_processors_have_process_method(self):
        processors = [
            LevelFilter(),
            AttributeInjector(),
            RedactionProcessor(),
            SamplingProcessor(),
            TraceInjector(),
            ResourceInjector(),
        ]
        assert all(callable(getattr(p, "process", None)) for p in processors)

    def test_level_filter_drops_below_threshold(self):
        processor = LevelFilter(13)
        assert processor.process(create_record("调试", "调试")) is None
        kept = processor.process(create_record("警告", "警告"))
        assert isinstance(kept, LogRecord)
        assert kept.severity_number == 13

    def test_level_filter_default_threshold(self):
        processor = LevelFilter()
        assert processor.process(create_record("调试", "调试")) is None
        assert processor.process(create_record("信息", "信息")) is not None

    def test_attribute_injector_keeps_existing_keys(self):
        record = create_record("消息", 属性={"user.id": "1", "keep": "原值"})
        result = AttributeInjector({"user.id": "2", "app": "道"}).process(record)
        assert result is record
        assert record.attributes == {"user.id": "1", "keep": "原值", "app": "道"}

    def test_redaction_by_key(self):
        record = create_record(
            "登录",
            属性={"user.password": "secret", "user.name": "alice", "token": "t"},
        )
        RedactionProcessor(keys=["password", "token"]).process(record)
        assert record.attributes["user.password"] == "***"
        assert record.attributes["token"] == "***"
        assert record.attributes["user.name"] == "alice"

    def test_redaction_by_regex_on_attributes_and_body(self):
        record = create_record("手机 13800138000", 属性={"phone": "13800138000"})
        RedactionProcessor(patterns=[r"\d{11}"]).process(record)
        assert record.attributes["phone"] == "***"
        assert record.body == "手机 ***"

    def test_redaction_invalid_regex_raises_chinese_error(self):
        with pytest.raises(运行时错误, match="无效的脱敏正则表达式"):
            RedactionProcessor(patterns=["["])

    def test_sampling_ratio_zero_drops_info(self):
        assert SamplingProcessor(0.0).process(create_record("信息")) is None

    def test_sampling_keeps_errors_by_default(self):
        processor = SamplingProcessor(0.0)
        assert processor.process(create_record("错误", "错误")) is not None
        assert processor.process(create_record("致命", "致命")) is not None

    def test_sampling_can_drop_errors(self):
        processor = SamplingProcessor(0.0, keep_errors=False)
        assert processor.process(create_record("错误", "错误")) is None

    def test_sampling_invalid_ratio_raises(self):
        with pytest.raises(运行时错误, match="采样比例"):
            SamplingProcessor(1.5)

    def test_trace_injector(self):
        start_trace(trace_id="a" * 32, span_id="b" * 16)
        set_resource(service_name="道服务", attributes={"host.name": "node1"})
        record = create_record("消息", 资源={"service.name": "自定义"})
        TraceInjector().process(record)
        assert record.trace_id == "a" * 32
        assert record.span_id == "b" * 16
        assert record.resource["service.name"] == "自定义"
        assert record.resource["host.name"] == "node1"

    def test_resource_injector(self):
        record = create_record("消息", 资源={"service.name": "原值"})
        ResourceInjector({"service.name": "新值", "env": "test"}).process(record)
        assert record.resource == {"service.name": "原值", "env": "test"}

    def test_chinese_processor_aliases(self):
        assert 级别过滤器 is LevelFilter
        assert 属性注入处理器 is AttributeInjector
        assert 脱敏处理器 is RedactionProcessor
        assert 采样处理器 is SamplingProcessor
        assert 链路注入处理器 is TraceInjector
        assert 资源注入处理器 is ResourceInjector


class TestExporters:
    def test_console_exporter_writes_json_lines(self):
        stream = io.StringIO()
        exporter = ConsoleExporter(stream)
        exporter.export([create_record("你好"), create_record("世界")])
        exporter.flush()
        lines = stream.getvalue().splitlines()
        assert len(lines) == 2
        assert json.loads(lines[0])["body"] == "你好"
        assert "世界" in lines[1]

    def test_file_exporter_appends_json_lines(self, tmp_path):
        path = tmp_path / "logs.jsonl"
        exporter = FileExporter(path)
        exporter.export([create_record("第一条")])
        exporter.export([create_record("第二条")])
        exporter.close()
        lines = path.read_text(encoding="utf-8").splitlines()
        assert [json.loads(line)["body"] for line in lines] == ["第一条", "第二条"]

    def test_file_exporter_close_is_idempotent(self, tmp_path):
        path = tmp_path / "logs.jsonl"
        exporter = FileExporter(path)
        exporter.export([create_record("一")])
        exporter.close()
        exporter.close()
        exporter.export([create_record("二")])
        exporter.close()
        lines = path.read_text(encoding="utf-8").splitlines()
        assert len(lines) == 2

    def test_memory_exporter_and_clear(self):
        exporter = MemoryExporter()
        exporter.export([create_record("甲"), create_record("乙")])
        assert [r.body for r in exporter.records] == ["甲", "乙"]
        exporter.clear()
        assert exporter.records == []

    def test_chinese_exporter_aliases(self):
        assert 控制台导出器 is ConsoleExporter
        assert 文件导出器 is FileExporter
        assert 内存导出器 is MemoryExporter


class TestLogPipeline:
    def test_batch_size_one_exports_immediately(self):
        exporter = MemoryExporter()
        pipeline = LogPipeline(exporter=exporter)
        pipeline.emit(create_record("即时"))
        assert [r.body for r in exporter.records] == ["即时"]

    def test_batch_size_waits_for_flush(self):
        exporter = MemoryExporter()
        pipeline = LogPipeline(exporter=exporter, batch_size=3)
        pipeline.emit(create_record("1"))
        pipeline.emit(create_record("2"))
        assert exporter.records == []
        pipeline.emit(create_record("3"))
        assert len(exporter.records) == 3
        pipeline.emit(create_record("4"))
        assert len(exporter.records) == 3
        pipeline.flush()
        assert len(exporter.records) == 4

    def test_processor_can_drop_record(self):
        exporter = MemoryExporter()
        pipeline = LogPipeline(processors=[LevelFilter(13)], exporter=exporter)
        pipeline.emit(create_record("被丢弃", "调试"))
        pipeline.emit(create_record("保留", "警告"))
        assert [r.body for r in exporter.records] == ["保留"]

    def test_context_manager_closes_file_exporter(self, tmp_path):
        path = tmp_path / "pipeline.jsonl"
        with LogPipeline(exporter=FileExporter(path)) as pipeline:
            pipeline.emit(create_record("上下文"))
        assert len(path.read_text(encoding="utf-8").splitlines()) == 1

    def test_close_prevents_emit(self):
        pipeline = LogPipeline(exporter=MemoryExporter())
        pipeline.close()
        with pytest.raises(运行时错误, match="已关闭"):
            pipeline.emit(create_record("消息"))

    def test_emit_rejects_non_record(self):
        pipeline = LogPipeline(exporter=MemoryExporter())
        with pytest.raises(运行时错误, match="LogRecord"):
            pipeline.emit("不是记录")

    def test_chinese_pipeline_alias(self):
        assert 日志管道 is LogPipeline


class TestAsyncLogPipeline:
    def test_flush_exports_queued_records(self):
        exporter = MemoryExporter()
        pipeline = AsyncLogPipeline(exporter=exporter, batch_size=100)
        pipeline.start()
        try:
            for i in range(5):
                pipeline.emit(create_record(f"消息{i}"))
            pipeline.flush()
            assert [r.body for r in exporter.records] == [f"消息{i}" for i in range(5)]
        finally:
            pipeline.close()

    def test_emit_auto_starts_worker(self):
        exporter = MemoryExporter()
        pipeline = AsyncLogPipeline(exporter=exporter, batch_size=100)
        pipeline.emit(create_record("自动启动"))
        pipeline.flush()
        assert [r.body for r in exporter.records] == ["自动启动"]
        pipeline.close()

    def test_batch_size_triggers_background_export(self):
        exporter = MemoryExporter()
        pipeline = AsyncLogPipeline(exporter=exporter, batch_size=2)
        with pipeline:
            for i in range(3):
                pipeline.emit(create_record(f"{i}"))
            pipeline.flush()
            assert len(exporter.records) == 3

    def test_emit_after_stop_raises(self):
        pipeline = AsyncLogPipeline(exporter=MemoryExporter())
        pipeline.start()
        pipeline.stop()
        with pytest.raises(运行时错误, match="已停止"):
            pipeline.emit(create_record("消息"))
        pipeline.close()

    def test_close_is_idempotent(self):
        pipeline = AsyncLogPipeline(exporter=MemoryExporter())
        pipeline.emit(create_record("消息"))
        pipeline.close()
        pipeline.close()

    def test_processor_error_does_not_leak_worker_thread(self):
        class Broken:
            def process(self, record):
                raise ValueError("处理器故障")

        pipeline = AsyncLogPipeline(
            processors=[Broken()], exporter=MemoryExporter(), batch_size=100
        )
        with pipeline:
            for i in range(3):
                pipeline.emit(create_record(f"{i}"))
            pipeline.flush()
        assert pipeline._worker is None
        assert not any(
            t.name == "道-异步日志管道" and t.is_alive() for t in threading.enumerate()
        )

    def test_chinese_async_pipeline_alias(self):
        assert 异步日志管道 is AsyncLogPipeline
