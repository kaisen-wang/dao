"""结构化日志导出器（参考 OpenTelemetry Collector 的 Exporters 层）。

导出器接收一批 :class:`~dao.logmodel.model.LogRecord`，把它们写到控制台、
文件或内存。每条记录以单行 JSON（JSON Lines）表示。
"""

from __future__ import annotations

import os
import random
import sys
from typing import Any, TextIO

from ..errors import 运行时错误
from .model import LogRecord


class ConsoleExporter:
    """把每条记录以单行 JSON 写到文本流（默认 ``stderr``）。"""

    def __init__(self, stream: TextIO | None = None) -> None:
        self.stream: TextIO = stream if stream is not None else sys.stderr

    def export(self, records: list[LogRecord]) -> None:
        """逐行写入记录。"""
        for record in records:
            self.stream.write(record.to_json() + "\n")

    def flush(self) -> None:
        """刷新底层流。"""
        self.stream.flush()


class FileExporter:
    """以追加方式把记录写入 JSON Lines 文件。"""

    def __init__(self, path: str | os.PathLike[str], encoding: str = "utf-8") -> None:
        self.path = path
        self.encoding = encoding
        self._file: TextIO | None = None

    def _ensure_open(self) -> TextIO:
        """首次写入时打开文件（追加模式）。"""
        if self._file is None:
            try:
                # 文件句柄需跨多次 export/flush 复用，故不用 with 语句
                self._file = open(self.path, "a", encoding=self.encoding)  # noqa: SIM115
            except OSError as exc:
                raise 运行时错误(f"无法打开日志文件: {self.path}") from exc
        return self._file

    def export(self, records: list[LogRecord]) -> None:
        """追加写入一批记录。"""
        stream = self._ensure_open()
        try:
            for record in records:
                stream.write(record.to_json() + "\n")
        except OSError as exc:
            raise 运行时错误(f"无法写入日志文件: {self.path}") from exc

    def flush(self) -> None:
        """刷新文件缓冲（未打开时无需操作）。"""
        if self._file is not None:
            try:
                self._file.flush()
            except OSError as exc:
                raise 运行时错误(f"无法刷新日志文件: {self.path}") from exc

    def close(self) -> None:
        """关闭文件；重复调用安全。"""
        if self._file is not None:
            try:
                self._file.close()
            except OSError as exc:
                raise 运行时错误(f"无法关闭日志文件: {self.path}") from exc
            finally:
                self._file = None


class MemoryExporter:
    """把记录保存在内存中，便于测试与调试。"""

    def __init__(self) -> None:
        self.records: list[LogRecord] = []

    def export(self, records: list[LogRecord]) -> None:
        """追加一批记录。"""
        self.records.extend(records)

    def clear(self) -> None:
        """清空已收集的记录。"""
        self.records.clear()


class TailSamplingExporter:
    """尾部采样导出器：按链路（trace_id）聚合后统一做采样决策。

    有 trace_id 的记录先按 trace 分桶缓存，flush 时若链路中出现 ERROR/FATAL
    则整链保留，否则按 ratio 对整链做一次采样；无 trace_id 的记录立即决策
    并转发。缓冲的 trace 数量受 ``max_traces`` 限制，超限时新 trace 立即决策。
    """

    def __init__(
        self,
        exporter: Any,
        ratio: float = 1.0,
        keep_errors: bool = True,
        max_traces: int = 1000,
    ) -> None:
        if not callable(getattr(exporter, "export", None)):
            raise 运行时错误("尾部采样导出器的 exporter 必须提供 export 方法")
        self.ratio = float(ratio)
        if not 0.0 <= self.ratio <= 1.0:
            raise 运行时错误(f"无效的采样比例: {ratio}，有效范围: 0-1")
        self.keep_errors = bool(keep_errors)
        self.max_traces = int(max_traces)
        if self.max_traces < 1:
            raise 运行时错误(f"无效的 max_traces: {max_traces}，必须大于 0")
        self.exporter = exporter
        self._buffers: dict[str, list[LogRecord]] = {}
        self._closed = False

    @staticmethod
    def _is_error(record: LogRecord) -> bool:
        """判断单条记录是否属于错误级别。"""
        return (
            int(record.severity_number) >= 17
            or str(record.severity_text).upper() in ("ERROR", "FATAL")
        )

    def _should_keep(self, record: LogRecord) -> bool:
        """对单条记录做立即采样决策。"""
        if self.keep_errors and self._is_error(record):
            return True
        return random.random() < self.ratio

    def _flush_trace(self, records: list[LogRecord]) -> None:
        """对一条 trace 的所有记录做一次采样决策，保留时整体转发。"""
        if not records:
            return
        keep = self.keep_errors and any(self._is_error(record) for record in records)
        if not keep:
            keep = random.random() < self.ratio
        if keep:
            self.exporter.export(list(records))

    def export(self, records: list[LogRecord]) -> None:
        """缓冲有 trace_id 的记录；无 trace_id 的记录立即决策并转发。"""
        for record in records:
            trace_id = str(record.trace_id)
            if not trace_id:
                if self._should_keep(record):
                    self.exporter.export([record])
                continue
            if trace_id not in self._buffers:
                if len(self._buffers) >= self.max_traces:
                    # 缓冲区已满：新 trace 立即决策，不占用缓冲槽位。
                    if self._should_keep(record):
                        self.exporter.export([record])
                    continue
                self._buffers[trace_id] = []
            self._buffers[trace_id].append(record)

    def flush(self) -> None:
        """决策并转发所有缓冲的 trace，然后刷新下游导出器。"""
        buffers = self._buffers
        self._buffers = {}
        try:
            for records in buffers.values():
                self._flush_trace(records)
        finally:
            flush = getattr(self.exporter, "flush", None)
            if callable(flush):
                flush()

    def close(self) -> None:
        """先 flush 再关闭下游导出器；重复调用安全。"""
        if self._closed:
            return
        self.flush()
        close = getattr(self.exporter, "close", None)
        if callable(close):
            close()
        self._closed = True


# 中文别名，便于道语言侧与中文文档使用。
控制台导出器 = ConsoleExporter
文件导出器 = FileExporter
内存导出器 = MemoryExporter
尾部采样导出器 = TailSamplingExporter

__all__ = [
    "ConsoleExporter",
    "FileExporter",
    "MemoryExporter",
    "TailSamplingExporter",
    "内存导出器",
    "尾部采样导出器",
    "控制台导出器",
    "文件导出器",
]
