"""
并发编程模块
==============

为道语言提供并发编程支持：
- 通道（Channel / BufferedChannel）
- 互斥锁（Mutex）
- 原子操作（AtomicInt / AtomicBool）
- 异步执行上下文（AsyncContext）
- 协程调度器（CoroutineScheduler / CoroutinePool）
- 选择器（select_receive / select_receive_sync）
"""

from .async_await import AsyncContext, run_async
from .channels import AsyncBufferedChannel, AsyncChannel, BufferedChannel, Channel
from .coroutines import CoroutinePool, CoroutineScheduler
from .selectors import select_receive, select_receive_sync
from .sync import (
    AtomicBool,
    AtomicInt,
    Barrier,
    Condition,
    Mutex,
    Once,
    RLock,
    Semaphore,
    WaitGroup,
)

__all__ = [
    # 通道
    "Channel",
    "BufferedChannel",
    "AsyncChannel",
    "AsyncBufferedChannel",
    # 同步原语
    "Mutex",
    "RLock",
    "Semaphore",
    "WaitGroup",
    "Barrier",
    "Condition",
    "Once",
    "AtomicInt",
    "AtomicBool",
    # 异步执行
    "AsyncContext",
    "run_async",
    # 协程调度
    "CoroutineScheduler",
    "CoroutinePool",
    # 选择器
    "select_receive",
    "select_receive_sync",
]
