"""
通道模块
========

为道语言提供通道（Channel）实现：
- 无缓冲通道（Channel）：发送者阻塞直到有接收者
- 缓冲通道（BufferedChannel）：有固定容量缓冲区
- 原生异步通道（AsyncChannel / AsyncBufferedChannel）：基于 asyncio.Queue 的原生异步实现
"""

import asyncio
from queue import Empty, Queue

from ..errors import 运行时错误


class Channel:
    """无缓冲通道（类似 Go 语言的通道）

    发送者会阻塞直到有接收者，接收者会阻塞直到有发送者。
    使用队列实现简单的同步。
    """

    def __init__(self):
        self._queue = Queue(maxsize=1)
        self.closed = False

    def send(self, value):
        """发送数据（阻塞直到被接收）"""
        if self.closed:
            raise 运行时错误("发送到已关闭的通道")

        try:
            self._queue.put(value, block=True, timeout=30.0)
        except Exception:
            raise 运行时错误("发送超时")

    async def send_async(self, value):
        """异步发送数据（原生 asyncio 实现）"""
        if self.closed:
            raise 运行时错误("发送到已关闭的通道")

        try:
            loop = asyncio.get_running_loop()
            await loop.run_in_executor(None, self.send, value)
        except RuntimeError:
            # 没有运行中的事件循环，回退到同步方式
            self.send(value)

    def receive(self):
        """接收数据（阻塞直到有数据）"""
        if self.closed and self._queue.empty():
            raise StopIteration("通道已关闭")

        try:
            return self._queue.get(block=True, timeout=30.0)
        except Exception:
            if self.closed:
                raise StopIteration("通道已关闭")
            raise 运行时错误("接收超时")

    async def receive_async(self):
        """异步接收数据（原生 asyncio 实现）"""
        if self.closed and self._queue.empty():
            raise StopIteration("通道已关闭")

        try:
            loop = asyncio.get_running_loop()
            return await loop.run_in_executor(None, self.receive)
        except RuntimeError:
            # 没有运行中的事件循环，回退到同步方式
            return self.receive()

    def close(self):
        """关闭通道"""
        self.closed = True


class BufferedChannel:
    """缓冲通道

    有固定容量的缓冲区，缓冲区满时发送者阻塞，缓冲区空时接收者阻塞。
    """

    def __init__(self, capacity):
        self.queue = Queue(maxsize=capacity)
        self.closed = False

    def send(self, value):
        """发送数据（阻塞直到缓冲区有空间）"""
        if self.closed:
            raise 运行时错误("发送到已关闭的通道")

        try:
            self.queue.put(value, block=True, timeout=15)
        except Exception as e:
            raise 运行时错误(f"发送到通道时出错: {e}")

    async def send_async(self, value):
        """异步发送数据（原生 asyncio 实现）"""
        if self.closed:
            raise 运行时错误("发送到已关闭的通道")

        try:
            loop = asyncio.get_running_loop()
            await loop.run_in_executor(None, self.send, value)
        except RuntimeError:
            self.send(value)

    def receive(self):
        """接收数据（阻塞直到有数据）"""
        if self.closed and self.queue.empty():
            raise StopIteration("通道已关闭")

        try:
            return self.queue.get(block=True, timeout=15)
        except Empty:
            raise 运行时错误("通道接收超时")

    async def receive_async(self):
        """异步接收数据（原生 asyncio 实现）"""
        if self.closed and self.queue.empty():
            raise StopIteration("通道已关闭")

        try:
            loop = asyncio.get_running_loop()
            return await loop.run_in_executor(None, self.receive)
        except RuntimeError:
            return self.receive()

    def close(self):
        """关闭通道"""
        self.closed = True


class AsyncChannel:
    """原生异步无缓冲通道

    基于 asyncio.Queue 实现，send_async/receive_async 为原生 async def 协程。
    同步 send/receive 方法通过 asyncio.run() 运行异步版本。
    """

    def __init__(self):
        self._queue = asyncio.Queue(maxsize=1)
        self.closed = False

    def send(self, value):
        """发送数据（同步包装）"""
        if self.closed:
            raise 运行时错误("发送到已关闭的通道")
        try:
            asyncio.run(self.send_async(value))
        except RuntimeError:
            # 已有事件循环，使用线程执行
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor() as pool:
                future = pool.submit(asyncio.run, self.send_async(value))
                future.result(timeout=30)

    async def send_async(self, value):
        """异步发送数据（原生协程）"""
        if self.closed:
            raise 运行时错误("发送到已关闭的通道")
        try:
            await asyncio.wait_for(self._queue.put(value), timeout=30.0)
        except asyncio.TimeoutError:
            raise 运行时错误("发送超时")

    def receive(self):
        """接收数据（同步包装）"""
        if self.closed:
            raise StopIteration("通道已关闭")
        try:
            return asyncio.run(self.receive_async())
        except RuntimeError:
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor() as pool:
                future = pool.submit(asyncio.run, self.receive_async())
                return future.result(timeout=30)

    async def receive_async(self):
        """异步接收数据（原生协程）"""
        if self.closed and self._queue.empty():
            raise StopIteration("通道已关闭")
        try:
            return await asyncio.wait_for(self._queue.get(), timeout=30.0)
        except asyncio.TimeoutError:
            if self.closed:
                raise StopIteration("通道已关闭")
            raise 运行时错误("接收超时")

    def close(self):
        """关闭通道"""
        self.closed = True


class AsyncBufferedChannel:
    """原生异步缓冲通道

    基于 asyncio.Queue 实现，有固定容量缓冲区。
    """

    def __init__(self, capacity):
        self._queue = asyncio.Queue(maxsize=capacity)
        self.closed = False

    def send(self, value):
        """发送数据（同步包装）"""
        if self.closed:
            raise 运行时错误("发送到已关闭的通道")
        try:
            asyncio.run(self.send_async(value))
        except RuntimeError:
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor() as pool:
                future = pool.submit(asyncio.run, self.send_async(value))
                future.result(timeout=15)

    async def send_async(self, value):
        """异步发送数据（原生协程）"""
        if self.closed:
            raise 运行时错误("发送到已关闭的通道")
        try:
            await asyncio.wait_for(self._queue.put(value), timeout=15.0)
        except asyncio.TimeoutError:
            raise 运行时错误("发送到通道时出错: 超时")

    def receive(self):
        """接收数据（同步包装）"""
        if self.closed:
            raise StopIteration("通道已关闭")
        try:
            return asyncio.run(self.receive_async())
        except RuntimeError:
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor() as pool:
                future = pool.submit(asyncio.run, self.receive_async())
                return future.result(timeout=15)

    async def receive_async(self):
        """异步接收数据（原生协程）"""
        if self.closed and self._queue.empty():
            raise StopIteration("通道已关闭")
        try:
            return await asyncio.wait_for(self._queue.get(), timeout=15.0)
        except asyncio.TimeoutError:
            raise 运行时错误("通道接收超时")

    def close(self):
        """关闭通道"""
        self.closed = True
