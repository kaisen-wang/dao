"""
并发编程模块
==============

为道语言提供并发编程支持：
- 通道（Channel / BufferedChannel）
- 互斥锁（Mutex）
- 原子操作（AtomicInt / AtomicBool）
"""

import asyncio
from queue import Empty, Queue
from threading import Lock

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
        """异步发送数据"""
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, self.send, value)

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
        """异步接收数据"""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, self.receive)

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
        """异步发送数据（缓冲版本）"""
        if self.closed:
            raise 运行时错误("发送到已关闭的通道")

        while True:
            try:
                self.queue.put_nowait(value)
                return
            except Exception:
                await asyncio.sleep(0.001)

    def receive(self):
        """接收数据（阻塞直到有数据）"""
        if self.closed and self.queue.empty():
            raise StopIteration("通道已关闭")

        try:
            return self.queue.get(block=True, timeout=15)
        except Empty:
            raise 运行时错误("通道接收超时")

    async def receive_async(self):
        """异步接收数据（缓冲版本）"""
        if self.closed and self.queue.empty():
            raise StopIteration("通道已关闭")

        while True:
            try:
                return self.queue.get_nowait()
            except Empty:
                await asyncio.sleep(0.001)

    def close(self):
        """关闭通道"""
        self.closed = True


class Mutex:
    """互斥锁

    提供互斥访问共享资源的同步原语。
    """

    def __init__(self):
        self._lock = Lock()

    def acquire(self):
        """获取锁"""
        self._lock.acquire()

    def release(self):
        """释放锁"""
        self._lock.release()

    def __enter__(self):
        """上下文管理器入口"""
        self.acquire()

    def __exit__(self, exc_type, exc_val, exc_tb):
        """上下文管理器出口"""
        self.release()


class AtomicInt:
    """原子整数

    提供线程安全的整数操作。
    """

    def __init__(self, value=0):
        self._value = value
        self._lock = Lock()

    def get(self):
        """获取值"""
        with self._lock:
            return self._value

    def set(self, value):
        """设置值"""
        with self._lock:
            self._value = value

    def add(self, delta):
        """原子加法"""
        with self._lock:
            self._value += delta
            return self._value

    def compare_and_set(self, expected, new_value):
        """比较并设置（CAS）"""
        with self._lock:
            if self._value == expected:
                self._value = new_value
                return True
            return False


class AtomicBool:
    """原子布尔

    提供线程安全的布尔操作。
    """

    def __init__(self, value=False):
        self._value = value
        self._lock = Lock()

    def get(self):
        """获取值"""
        with self._lock:
            return self._value

    def set(self, value):
        """设置值"""
        with self._lock:
            self._value = value

    def toggle(self):
        """原子取反"""
        with self._lock:
            self._value = not self._value
            return self._value

    def compare_and_set(self, expected, new_value):
        """比较并设置（CAS）"""
        with self._lock:
            if self._value == expected:
                self._value = new_value
                return True
            return False


__all__ = [
    "Channel",
    "BufferedChannel",
    "Mutex",
    "AtomicInt",
    "AtomicBool",
]
