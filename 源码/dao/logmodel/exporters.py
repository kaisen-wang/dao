"""结构化日志导出器（参考 OpenTelemetry Collector 的 Exporters 层）。

导出器接收一批 :class:`~dao.logmodel.model.LogRecord`，把它们写到控制台、
文件或内存。每条记录以单行 JSON（JSON Lines）表示。
"""

from __future__ import annotations

import os
import sys
from typing import TextIO

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


# 中文别名，便于道语言侧与中文文档使用。
控制台导出器 = ConsoleExporter
文件导出器 = FileExporter
内存导出器 = MemoryExporter

__all__ = [
    "ConsoleExporter",
    "FileExporter",
    "MemoryExporter",
    "内存导出器",
    "控制台导出器",
    "文件导出器",
]
