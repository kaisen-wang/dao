"""结构化日志处理管道（参考 OpenTelemetry Collector 分层设计）。

``Receivers -> Processors -> Exporters``：调用方通过 :meth:`LogPipeline.emit`
投递记录，记录按顺序经过处理器链（返回 ``None`` 即丢弃），再交给导出器。

:class:`LogPipeline` 是同步批量管道（不启线程，行为确定）；
:class:`AsyncLogPipeline` 在后台单线程中完成处理，``emit`` 非阻塞。
"""

from __future__ import annotations

import queue
import threading
import time
from types import TracebackType

from ..errors import 运行时错误
from .exporters import MemoryExporter
from .model import LogRecord
from .processors import Processor


class LogPipeline:
    """同步日志处理管道。

    Args:
        processors: 处理器列表，按给定顺序执行。
        exporter: 导出器；为 ``None`` 时使用 :class:`MemoryExporter`。
        batch_size: 缓冲达到该数量即导出；小于等于 1 时逐条导出。
        flush_interval: 距上次导出超过该秒数时，在下一次 ``emit`` 时导出；
            ``None`` 表示不按时间触发。
    """

    def __init__(
        self,
        processors: list[Processor] | None = None,
        exporter: object | None = None,
        batch_size: int = 1,
        flush_interval: float | None = None,
    ) -> None:
        self.processors: list[Processor] = []
        for processor in processors or []:
            if not callable(getattr(processor, "process", None)):
                raise 运行时错误("处理器必须提供 process 方法")
            self.processors.append(processor)
        self.exporter = exporter if exporter is not None else MemoryExporter()
        try:
            self.batch_size: int = int(batch_size)
        except (TypeError, ValueError) as exc:
            raise 运行时错误("批量大小必须是整数") from exc
        self.flush_interval = flush_interval
        self._buffer: list[LogRecord] = []
        self._buffer_lock = threading.Lock()
        self._last_flush = time.monotonic()
        self._closed = False

    def _flush_buffer(self) -> None:
        """导出缓冲中的全部记录；调用者须持有 ``_buffer_lock``。"""
        self._last_flush = time.monotonic()
        if not self._buffer:
            return
        batch, self._buffer = self._buffer, []
        if self.exporter is None:
            return
        try:
            self.exporter.export(batch)  # type: ignore[attr-defined]
            flush = getattr(self.exporter, "flush", None)
            if callable(flush):
                flush()
        except Exception as exc:
            self._buffer = batch + self._buffer
            raise 运行时错误("导出日志记录失败") from exc

    def _interval_due(self) -> bool:
        """判断是否达到按时间导出的间隔。"""
        if not self.flush_interval or self.flush_interval <= 0:
            return False
        return time.monotonic() - self._last_flush >= self.flush_interval

    def emit(self, record: LogRecord) -> None:
        """投递一条记录，依次经过处理器后加入缓冲。"""
        if not isinstance(record, LogRecord):
            raise 运行时错误("emit 只接受 LogRecord 实例")
        with self._buffer_lock:
            if self._closed:
                raise 运行时错误("日志管道已关闭，无法继续写入")
            current: LogRecord | None = record
            for processor in self.processors:
                current = processor.process(current) if current is not None else None
                if current is None:
                    return
            self._buffer.append(current)
            if (
                self.batch_size <= 1
                or len(self._buffer) >= self.batch_size
                or self._interval_due()
            ):
                self._flush_buffer()

    def flush(self) -> None:
        """导出缓冲中的全部记录。"""
        with self._buffer_lock:
            self._flush_buffer()

    def close(self) -> None:
        """先 flush，再关闭导出器（若提供 ``close``）。"""
        if self._closed:
            return
        self.flush()
        self._closed = True
        close = getattr(self.exporter, "close", None)
        if callable(close):
            close()

    def __enter__(self) -> LogPipeline:  # noqa: PYI034  兼容 Python 3.10
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> bool:
        self.close()
        return False


class AsyncLogPipeline(LogPipeline):
    """后台单线程异步管道。

    ``emit`` 只把记录入队；工作线程完成处理与批量导出。``flush`` 阻塞直到
    队列清空；``stop`` 发送停止信号并等待线程退出；``close`` 先 stop 再 flush。
    """

    def __init__(
        self,
        processors: list[Processor] | None = None,
        exporter: object | None = None,
        batch_size: int = 1,
        flush_interval: float | None = None,
    ) -> None:
        super().__init__(processors, exporter, batch_size, flush_interval)
        self._queue: queue.Queue[LogRecord | None] = queue.Queue()
        self._state_lock = threading.Lock()
        self._worker: threading.Thread | None = None
        self._started = False
        self._stopped = False
        self._worker_error: BaseException | None = None

    def start(self) -> None:
        """启动后台工作线程；重复调用无副作用。"""
        with self._state_lock:
            if self._started:
                return
            if self._stopped or self._closed:
                raise 运行时错误("异步日志管道已停止，无法启动")
            self._started = True
            worker = threading.Thread(
                target=self._run, name="道-异步日志管道", daemon=True
            )
            self._worker = worker
            worker.start()

    def stop(self) -> None:
        """停止接收新记录并等待工作线程退出。"""
        with self._state_lock:
            if self._stopped:
                return
            self._stopped = True
            worker = self._worker
            started = self._started
        if not started or worker is None:
            return
        self._queue.put(None)  # 停止哨兵，排在所有已入队记录之后
        worker.join()
        self._worker = None
        with self._buffer_lock:
            self._flush_buffer()

    def _run(self) -> None:
        """工作线程主循环：异常一律捕获，避免线程泄漏或 ``join`` 挂起。"""
        interval = self.flush_interval
        while True:
            if interval and interval > 0:
                try:
                    item = self._queue.get(timeout=interval)
                except queue.Empty:
                    try:
                        with self._buffer_lock:
                            self._flush_buffer()
                    except BaseException as exc:  # noqa: BLE001  后台异常必须全部捕获
                        self._worker_error = exc
                    continue
            else:
                item = self._queue.get()
            try:
                if item is None:
                    return
                try:
                    super().emit(item)
                except BaseException as exc:  # noqa: BLE001  防止工作线程意外退出
                    self._worker_error = exc
            finally:
                try:
                    self._queue.task_done()
                except ValueError:
                    pass

    def emit(self, record: LogRecord) -> None:
        """非阻塞入队；尚未启动时自动启动工作线程。"""
        if not isinstance(record, LogRecord):
            raise 运行时错误("emit 只接受 LogRecord 实例")
        with self._state_lock:
            if self._stopped or self._closed:
                raise 运行时错误("异步日志管道已停止，无法继续写入")
            need_start = not self._started
        if need_start:
            self.start()
        self._queue.put(record)

    def flush(self) -> None:
        """阻塞直到队列清空，然后导出残留缓冲。"""
        with self._state_lock:
            need_start = (
                not self._started
                and not self._stopped
                and not self._closed
                and not self._queue.empty()
            )
        if need_start:
            self.start()
        self._queue.join()
        with self._buffer_lock:
            self._flush_buffer()

    def close(self) -> None:
        """停止工作线程，flush 后关闭导出器。"""
        self.stop()
        super().close()

    def __enter__(self) -> AsyncLogPipeline:  # noqa: PYI034  兼容 Python 3.10
        self.start()
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> bool:
        self.close()
        return False


# 中文别名，便于道语言侧与中文文档使用。
日志管道 = LogPipeline
异步日志管道 = AsyncLogPipeline

__all__ = [
    "AsyncLogPipeline",
    "LogPipeline",
    "异步日志管道",
    "日志管道",
]
