"""
通道模块
========

为道语言提供通道（Channel）实现：
- 无缓冲通道（Channel）：真正的 rendezvous 语义，发送阻塞直到有接收者取走值
- 缓冲通道（BufferedChannel）：有固定容量缓冲区
- 原生异步通道（AsyncChannel / AsyncBufferedChannel）：基于 asyncio.Queue 的原生异步实现

超时时间可通过构造函数 ``timeout`` 参数或每次调用的 ``timeout`` 参数配置，
默认值保持与旧实现兼容（无缓冲通道 30 秒，缓冲通道 15 秒）。
"""

import asyncio
import concurrent.futures
import threading
import time
from queue import Empty, Full, Queue

from ..errors import 运行时错误

# 无缓冲通道默认超时（与旧实现一致）
DEFAULT_TIMEOUT = 30.0
# 缓冲通道默认超时（与旧实现一致）
DEFAULT_BUFFERED_TIMEOUT = 15.0

_CLOSED = object()  # 通道关闭信号（用于唤醒阻塞的发送者）


class _PendingSend:
    """内部待交接项：携带值、确认队列与取消标记。"""

    __slots__ = ("value", "ack", "cancelled")

    def __init__(self, value):
        self.value = value
        self.ack = Queue(maxsize=1)
        self.cancelled = False


class _QueueView:
    """``select`` 语句使用的队列视图。

    将内部的 ``(值, 确认)`` 交接项转换为纯值，从而让 select 的非阻塞/超时
    接收逻辑无需了解 rendezvous 细节。
    """

    __slots__ = ("_channel",)

    def __init__(self, channel):
        self._channel = channel

    def get_nowait(self):
        return self._channel._take_for_receive(block=False, timeout=None)

    def get(self, block=True, timeout=None):
        return self._channel._take_for_receive(block=block, timeout=timeout)

    def put(self, value, block=True, timeout=None):
        self._channel.send(value, timeout=timeout)

    def empty(self):
        return self._channel._queue.empty()

    def qsize(self):
        return self._channel._queue.qsize()


class Channel:
    """真正的无缓冲通道（类似 Go 语言的通道）

    rendezvous 语义：``send`` 把值交给内部队列后一直阻塞，直到某个接收者
    真正取走该值；``receive`` 在没有待交接值时一直阻塞，直到某个发送者
    提供值。因此发送与接收必须"会合"才能完成。

    ``timeout`` 限定单次阻塞的最长秒数；``None``（默认）使用构造时配置的
    超时时间，默认 30 秒。
    """

    def __init__(self, timeout: float = DEFAULT_TIMEOUT):
        self._queue = Queue()  # 无容量限制，交接的阻塞由 ack 控制
        self.closed = False
        self._timeout = timeout
        self._close_lock = threading.Lock()
        # 兼容 select：暴露队列视图而非内部队列
        self._queue_view = _QueueView(self)

    @staticmethod
    def _effective(timeout: float | None, configured: float) -> float:
        return configured if timeout is None else timeout

    def send(self, value, timeout: float | None = None):
        """发送数据：阻塞直到接收者取走值。"""
        if self.closed:
            raise 运行时错误("发送到已关闭的通道")

        pending = _PendingSend(value)
        try:
            self._queue.put(pending)
        except Exception as e:
            raise 运行时错误(f"发送超时: {e}")
        effective = self._timeout if timeout is None else timeout
        try:
            signal = pending.ack.get(block=True, timeout=effective)
        except Empty:
            pending.cancelled = True
            # 尽力移除已取消的交接项，避免超时的值被后续接收者取走
            with self._queue.mutex:
                try:
                    self._queue.queue.remove(pending)
                except ValueError:
                    pass
            raise 运行时错误("发送超时")
        if signal is _CLOSED:
            raise 运行时错误("发送到已关闭的通道")

    async def send_async(self, value, timeout: float | None = None):
        """异步发送（把阻塞的 rendezvous send 放到线程池执行）。"""
        if self.closed:
            raise 运行时错误("发送到已关闭的通道")

        effective = self._effective(timeout, self._timeout)
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            self.send(value, timeout=effective)
            return
        await loop.run_in_executor(None, self.send, value, effective)

    def _take_for_receive(self, block: bool, timeout: float | None):
        """从内部队列取出一个有效交接项并通知发送者。"""
        deadline = None
        if timeout is not None:
            deadline = time.monotonic() + timeout
        while True:
            remaining = None
            if deadline is not None:
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    raise Empty()
            item = self._queue.get(block=block, timeout=remaining)
            if isinstance(item, _PendingSend):
                if item.cancelled:
                    continue
                item.ack.put(True)
                return item.value
            # 外部直接放入的原始值（保持向后兼容）
            return item

    def receive(self, timeout: float | None = None):
        """接收数据：阻塞直到发送者提供值。"""
        if self.closed and self._queue.empty():
            raise StopIteration("通道已关闭")

        effective = self._timeout if timeout is None else timeout
        try:
            return self._take_for_receive(block=True, timeout=effective)
        except Empty:
            if self.closed:
                raise StopIteration("通道已关闭")
            raise 运行时错误("接收超时")
        except 运行时错误:
            raise
        except Exception as e:
            raise 运行时错误(f"接收超时: {e}")

    async def receive_async(self, timeout: float | None = None):
        """异步接收（把阻塞的 rendezvous receive 放到线程池执行）。"""
        if self.closed and self._queue.empty():
            raise StopIteration("通道已关闭")

        effective = self._effective(timeout, self._timeout)
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            return self.receive(timeout=effective)
        return await loop.run_in_executor(None, self.receive, effective)

    @property
    def queue(self):
        """兼容 select 语句的队列访问（纯值视图）。"""
        return self._queue_view

    def close(self):
        """关闭通道，唤醒所有阻塞的发送者。"""
        with self._close_lock:
            if self.closed:
                return
            self.closed = True
            # 唤醒阻塞中的 send：向每个待交接项的确认队列发送关闭信号
            while True:
                try:
                    item = self._queue.get_nowait()
                except Empty:
                    break
                if isinstance(item, _PendingSend):
                    try:
                        item.ack.put_nowait(_CLOSED)
                    except Exception:
                        pass


class BufferedChannel:
    """缓冲通道

    有固定容量的缓冲区，缓冲区满时发送者阻塞，缓冲区空时接收者阻塞。
    ``timeout`` 参数控制阻塞最长秒数，默认 15 秒。
    """

    def __init__(self, capacity, timeout: float = DEFAULT_BUFFERED_TIMEOUT):
        self.queue = Queue(maxsize=capacity)
        self.closed = False
        self._timeout = timeout

    def send(self, value, timeout: float | None = None):
        """发送数据（阻塞直到缓冲区有空间）"""
        if self.closed:
            raise 运行时错误("发送到已关闭的通道")

        effective = self._timeout if timeout is None else timeout
        try:
            self.queue.put(value, block=True, timeout=effective)
        except Full:
            raise 运行时错误("发送超时")
        except 运行时错误:
            raise
        except Exception as e:
            raise 运行时错误(f"发送到通道时出错: {e}")

    async def send_async(self, value, timeout: float | None = None):
        """异步发送数据（原生 asyncio 实现）"""
        if self.closed:
            raise 运行时错误("发送到已关闭的通道")

        effective = self._timeout if timeout is None else timeout
        try:
            loop = asyncio.get_running_loop()
            await loop.run_in_executor(None, self.send, value, effective)
        except RuntimeError:
            self.send(value, timeout=effective)

    def receive(self, timeout: float | None = None):
        """接收数据（阻塞直到有数据）"""
        if self.closed and self.queue.empty():
            raise StopIteration("通道已关闭")

        effective = self._timeout if timeout is None else timeout
        try:
            return self.queue.get(block=True, timeout=effective)
        except Empty:
            if self.closed:
                raise StopIteration("通道已关闭")
            raise 运行时错误("接收超时")
        except 运行时错误:
            raise
        except Exception as e:
            raise 运行时错误(f"通道接收超时: {e}")

    async def receive_async(self, timeout: float | None = None):
        """异步接收数据（原生 asyncio 实现）"""
        if self.closed and self.queue.empty():
            raise StopIteration("通道已关闭")

        effective = self._timeout if timeout is None else timeout
        try:
            loop = asyncio.get_running_loop()
            return await loop.run_in_executor(None, self.receive, effective)
        except RuntimeError:
            return self.receive(timeout=effective)

    def close(self):
        """关闭通道"""
        self.closed = True


class AsyncChannel:
    """原生异步无缓冲通道（真正的 rendezvous 语义）

    发送者与接收者通过等待队列直接会合：发送者把值交给已等待的接收者，
    否则注册为等待者直到有接收者出现；接收者反之。与同步 ``Channel``
    一样，值不会被缓冲。

    ``timeout`` 参数控制单次等待最长秒数，默认 30 秒。
    """

    def __init__(self, timeout: float = DEFAULT_TIMEOUT):
        # 内部交接队列：存放 _PendingSend，send_async/receive_async 通过它
        # 传递值；同时保留 _queue.put/_queue.get 的可替换性（兼容既有测试）。
        self._queue = asyncio.Queue()
        self.closed = False
        self._timeout = timeout
        # asyncio.Queue 与 ack Future 都绑定单个事件循环。同步包装若各自
        # asyncio.run() 会创建不同 loop，跨线程 send/receive 将无法会合。
        # 因此同步包装共用一个持久 loop（后台线程驱动），使 rendezvous 成立。
        self._loop: asyncio.AbstractEventLoop | None = None
        self._loop_thread: threading.Thread | None = None
        self._loop_lock = threading.Lock()

    def _shared_loop(self) -> asyncio.AbstractEventLoop:
        """获取同步包装共用的持久事件循环（懒创建）。"""
        with self._loop_lock:
            if self._loop is None or not self._loop.is_running():
                ready = threading.Event()
                loop = asyncio.new_event_loop()

                def _run_loop():
                    asyncio.set_event_loop(loop)
                    ready.set()
                    loop.run_forever()

                self._loop = loop
                self._loop_thread = threading.Thread(
                    target=_run_loop, name="dao-async-channel", daemon=True
                )
                self._loop_thread.start()
                ready.wait()
            return self._loop

    def _run_sync(self, coro, timeout: float):
        """在共享 loop 上执行协程并等待结果（供同步包装使用）。"""
        loop = self._shared_loop()
        future = asyncio.run_coroutine_threadsafe(coro, loop)
        try:
            return future.result(timeout=timeout)
        except concurrent.futures.TimeoutError:
            future.cancel()
            raise 运行时错误("操作超时")

    def send(self, value, timeout: float | None = None):
        """发送数据（同步包装，跨线程会合）"""
        if self.closed:
            raise 运行时错误("发送到已关闭的通道")
        effective = self._effective(timeout, self._timeout)
        self._run_sync(self.send_async(value, effective), effective + 1.0)

    async def send_async(self, value, timeout: float | None = None):
        """异步发送：把值放入交接队列后阻塞，直到接收者取走。"""
        if self.closed:
            raise 运行时错误("发送到已关闭的通道")

        effective = self._effective(timeout, self._timeout)
        ack = asyncio.get_running_loop().create_future()
        try:
            await self._queue.put((value, ack))
        except asyncio.TimeoutError:
            raise 运行时错误("发送超时")
        try:
            await asyncio.wait_for(ack, timeout=effective)
        except asyncio.TimeoutError:
            raise 运行时错误("发送超时")

    def receive(self, timeout: float | None = None):
        """接收数据（同步包装，跨线程会合）"""
        if self.closed:
            raise StopIteration("通道已关闭")
        effective = self._effective(timeout, self._timeout)
        return self._run_sync(self.receive_async(effective), effective + 1.0)

    async def receive_async(self, timeout: float | None = None):
        """异步接收：阻塞直到发送者提供值。"""
        if self.closed:
            raise StopIteration("通道已关闭")

        effective = self._effective(timeout, self._timeout)
        try:
            item = await asyncio.wait_for(self._queue.get(), timeout=effective)
        except asyncio.TimeoutError:
            if self.closed:
                raise StopIteration("通道已关闭")
            raise 运行时错误("接收超时")
        if item is None and self.closed:
            raise StopIteration("通道已关闭")
        if isinstance(item, tuple) and len(item) == 2:
            value, ack = item
            if not ack.done():
                ack.set_result(True)
            return value
        return item

    @staticmethod
    def _effective(timeout: float | None, configured: float) -> float:
        return configured if timeout is None else timeout

    def close(self):
        """关闭通道，唤醒阻塞中的发送者与接收者。"""
        if self.closed:
            return
        self.closed = True
        # 若共享 loop 已在运行，必须在其上操作队列/future，避免跨线程告警。
        if self._loop is not None and self._loop.is_running():
            self._run_sync(self._close_async(), timeout=5.0)
            return
        # 尚无 loop：队列为空，直接清理即可
        while True:
            try:
                item = self._queue.get_nowait()
            except asyncio.QueueEmpty:
                break

    async def _close_async(self):
        """在共享 loop 上关闭：唤醒阻塞的发送者与接收者。"""
        while True:
            try:
                item = self._queue.get_nowait()
            except asyncio.QueueEmpty:
                break
            if isinstance(item, tuple) and len(item) == 2:
                _, ack = item
                if not ack.done():
                    ack.set_exception(运行时错误("发送到已关闭的通道"))
        try:
            self._queue.put_nowait(None)
        except asyncio.QueueFull:
            pass


class AsyncBufferedChannel:
    """原生异步缓冲通道

    基于 asyncio.Queue 实现，有固定容量缓冲区。
    ``timeout`` 参数控制阻塞最长秒数，默认 15 秒。
    """

    def __init__(self, capacity, timeout: float = DEFAULT_BUFFERED_TIMEOUT):
        self._queue = asyncio.Queue(maxsize=capacity)
        self.closed = False
        self._timeout = timeout

    def send(self, value, timeout: float | None = None):
        """发送数据（同步包装）"""
        if self.closed:
            raise 运行时错误("发送到已关闭的通道")
        effective = self._timeout if timeout is None else timeout
        try:
            asyncio.run(self.send_async(value, effective))
        except RuntimeError:
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor() as pool:
                future = pool.submit(asyncio.run, self.send_async(value, effective))
                future.result(timeout=effective)

    async def send_async(self, value, timeout: float | None = None):
        """异步发送数据（原生协程）"""
        if self.closed:
            raise 运行时错误("发送到已关闭的通道")
        effective = self._timeout if timeout is None else timeout
        try:
            await asyncio.wait_for(self._queue.put(value), timeout=effective)
        except asyncio.TimeoutError:
            raise 运行时错误("发送超时")

    def receive(self, timeout: float | None = None):
        """接收数据（同步包装）"""
        if self.closed:
            raise StopIteration("通道已关闭")
        effective = self._timeout if timeout is None else timeout
        try:
            return asyncio.run(self.receive_async(effective))
        except RuntimeError:
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor() as pool:
                future = pool.submit(asyncio.run, self.receive_async(effective))
                return future.result(timeout=effective)

    async def receive_async(self, timeout: float | None = None):
        """异步接收数据（原生协程）"""
        if self.closed and self._queue.empty():
            raise StopIteration("通道已关闭")
        effective = self._timeout if timeout is None else timeout
        try:
            return await asyncio.wait_for(self._queue.get(), timeout=effective)
        except asyncio.TimeoutError:
            raise 运行时错误("通道接收超时")

    def close(self):
        """关闭通道"""
        self.closed = True
