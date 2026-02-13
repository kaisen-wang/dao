"""
并发编程解释器
===============

实现道语言的并发编程特性：
- 异步/等待
- 协程和通道
- 同步原语
"""

import asyncio
import time
from concurrent.futures import ThreadPoolExecutor
from queue import Empty, Queue
from threading import Lock, Thread
from typing import Any

from ..ast_nodes import (
    AsyncFunctionDecl,
    AwaitAllExpr,
    AwaitExpr,
    AwaitRaceExpr,
    ChannelExpr,
    ParallelStmt,
    ReceiveExpr,
    SelectCase,
    SelectStmt,
    SendStmt,
    SyncStmt,
)
from ..builtins import (
    DaoFunction,
    DaoInstance,
    get_builtins,
    get_interpreter_builtins,
)
from ..builtins.callables import DaoAsyncFunction
from ..environment import Environment
from ..errors import (
    名称错误,
    类型错误,
    运行时错误,
)
from ..tokens import TokenType


class AsyncContext:
    """异步执行上下文

    管理异步函数的执行环境，包括事件循环、任务调度等。
    """

    def __init__(self):
        self.loop = asyncio.get_event_loop()
        self.current_task = None
        self.tasks = set()
        self.executor = ThreadPoolExecutor()

    async def run(self, coro):
        """运行协程"""
        task = asyncio.create_task(coro)
        self.tasks.add(task)
        return await task

    def run_all(self, coros):
        """并发运行多个协程，等待所有完成"""
        return asyncio.gather(*coros)

    def run_race(self, coros):
        """竞速运行，返回最快完成的"""
        return asyncio.wait(coros, return_when=asyncio.FIRST_COMPLETED)

    def stop(self):
        """停止事件循环"""
        self.loop.stop()

    def close(self):
        """关闭执行上下文"""
        self.executor.shutdown()
        self.loop.close()


class Channel:
    """无缓冲通道（类似 Go 语言的通道）

    发送者会阻塞直到有接收者，接收者会阻塞直到有发送者。
    """

    def __init__(self):
        self.queue = Queue(maxsize=0)  # maxsize=0 表示无缓冲
        self.lock = Lock()
        self.send_ready = Lock()
        self.recv_ready = Lock()

    def send(self, value):
        """发送数据（阻塞直到被接收）"""
        self.send_ready.acquire()
        try:
            self.queue.put(value)
            self.recv_ready.release()  # 通知接收者
            # 等待接收者确认
            while not self.queue.empty():
                time.sleep(0.001)
        finally:
            self.send_ready.release()

    def receive(self):
        """接收数据（阻塞直到有数据）"""
        self.recv_ready.acquire()
        try:
            while self.queue.empty():
                time.sleep(0.001)  # 轮询等待
            value = self.queue.get()
            self.send_ready.release()  # 通知发送者
            return value
        finally:
            self.recv_ready.release()

    def close(self):
        """关闭通道"""
        self.queue.put(None)  # 发送结束信号


class BufferedChannel(Channel):
    """缓冲通道

    有固定容量的缓冲区，缓冲区满时发送者阻塞，缓冲区空时接收者阻塞。
    """

    def __init__(self, capacity):
        super().__init__()
        self.queue = Queue(maxsize=capacity)

    def send(self, value):
        """发送数据（阻塞直到缓冲区有空间）"""
        try:
            self.queue.put(value, block=True, timeout=10)
        except Exception as e:
            raise 运行时错误(f"发送到通道时出错: {e}")

    def receive(self):
        """接收数据（阻塞直到有数据）"""
        try:
            return self.queue.get(block=True, timeout=10)
        except Empty:
            raise 运行时错误("通道接收超时")


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


class ConcurrencyEvaluator:
    """并发编程解释器混入类"""

    def __init__(self):
        # 解决循环导入问题 - 使用绝对路径导入
        from dao.interpreter.expressions import ExpressionEvaluator
        from dao.interpreter.statements import StatementExecutor

        # 混入其他解释器类的功能
        self.__class__.__bases__ = (
            StatementExecutor,
            ExpressionEvaluator,
            ConcurrencyEvaluator,
        )

        self.async_context = AsyncContext()

    # ========================
    # 异步函数
    # ========================

    def exec_async_function_decl(self, node: AsyncFunctionDecl, env: Environment):
        """执行异步函数声明"""
        from ..builtins.callables import DaoAsyncFunction

        async_func = DaoAsyncFunction(
            node.name,
            node.params,
            node.body,
            env,
            node.default_values,
            node.is_static,
            node.is_private,
        )
        env.define(node.name, async_func)

    async def eval_async_function_call(self, func: DaoAsyncFunction, args, kwargs):
        """异步调用函数"""
        func_env = func.closure_env.create_child()
        # 绑定参数
        for param, arg in zip(func.params, args):
            func_env.set(param, arg)
        for name, value in kwargs.items():
            func_env.set(name, value)
        # 执行函数体
        return await self._exec_async_block(func.body, func_env)

    async def _exec_async_block(self, statements, env: Environment):
        """执行异步代码块"""
        for stmt in statements:
            await self._exec_statement(stmt, env)

    async def _exec_statement(self, stmt, env: Environment):
        """执行单个语句（异步版本）"""
        token_type = type(stmt).__name__
        handler_name = f"exec_{token_type}"
        if hasattr(self, handler_name):
            await getattr(self, handler_name)(stmt, env)
        else:
            # 调用同步版本的处理程序
            self._dispatch_statement(stmt, env)

    # ========================
    # 等待表达式
    # ========================

    async def eval_await_expr(self, node: AwaitExpr, env: Environment):
        """求值等待表达式"""
        value = self.eval_expression(node.expression, env)

        if hasattr(value, "is_async") and value.is_async:
            # 如果是异步函数，调用它
            coro = self.eval_async_function_call(value, [], {})
            return await coro
        elif hasattr(value, "__call__") and asyncio.iscoroutinefunction(value):
            # 如果是 asyncio 协程函数
            return await value()
        elif asyncio.iscoroutine(value):
            # 如果已经是协程对象
            return await value
        else:
            # 同步值，直接返回
            return value

    async def eval_await_all_expr(self, node: AwaitAllExpr, env: Environment):
        """求值全部等待表达式"""
        coros = []
        for expr in node.expressions:
            value = self.eval_expression(expr, env)
            if hasattr(value, "is_async") and value.is_async:
                coros.append(self.eval_async_function_call(value, [], {}))
            elif asyncio.iscoroutinefunction(value):
                coros.append(value())
            elif asyncio.iscoroutine(value):
                coros.append(value)
            else:
                # 同步值包装成协程
                coros.append(asyncio.to_thread(lambda: value))

        return await asyncio.gather(*coros)

    async def eval_await_race_expr(self, node: AwaitRaceExpr, env: Environment):
        """求值竞速等待表达式"""
        coros = []
        for expr in node.expressions:
            value = self.eval_expression(expr, env)
            if hasattr(value, "is_async") and value.is_async:
                coros.append(self.eval_async_function_call(value, [], {}))
            elif asyncio.iscoroutinefunction(value):
                coros.append(value())
            elif asyncio.iscoroutine(value):
                coros.append(value)
            else:
                coros.append(asyncio.to_thread(lambda: value))

        done, pending = await asyncio.wait(coros, return_when=asyncio.FIRST_COMPLETED)
        return list(done)[0].result()

    # ========================
    # 协程
    # ========================

    def exec_parallel_stmt(self, node: ParallelStmt, env: Environment):
        """执行并行块"""
        # 使用线程执行并行块
        threads = []

        for stmt in node.body:
            thread = Thread(target=self._dispatch_statement, args=(stmt, env))
            thread.start()
            threads.append(thread)

        for thread in threads:
            thread.join()

    # ========================
    # 通道
    # ========================

    def eval_channel_expr(self, node: ChannelExpr, env: Environment):
        """求值通道表达式"""
        if node.capacity is None:
            return Channel()
        else:
            return BufferedChannel(node.capacity)

    def exec_send_stmt(self, node: SendStmt, env: Environment):
        """执行发送语句"""
        channel = self.eval_expression(node.channel, env)
        value = self.eval_expression(node.value, env)

        if isinstance(channel, Channel) or isinstance(channel, BufferedChannel):
            channel.send(value)
        else:
            raise 类型错误("发送操作的目标必须是通道对象")

    def eval_receive_expr(self, node: ReceiveExpr, env: Environment):
        """求值接收表达式"""
        channel = self.eval_expression(node.channel, env)

        if isinstance(channel, Channel) or isinstance(channel, BufferedChannel):
            return channel.receive()
        else:
            raise 类型错误("接收操作的目标必须是通道对象")

    # ========================
    # 选择器
    # ========================

    def exec_select_stmt(self, node: SelectStmt, env: Environment):
        """执行选择语句"""
        for case in node.cases:
            if case.type == "receive":
                try:
                    # 尝试接收
                    channel = self.eval_expression(case.channel, env)
                    if isinstance(channel, Channel) or isinstance(
                        channel, BufferedChannel
                    ):
                        value = channel.receive()
                        case_env = env.create_child()
                        if case.variable:
                            case_env.set(case.variable, value)
                        self._exec_block(case.body, case_env)
                        return
                except Empty:
                    continue  # 超时，继续下一个情况

            elif case.type == "timeout":
                timeout = self.eval_expression(case.timeout_value, env)
                time.sleep(timeout)
                self._exec_block(case.body, env)
                return

    # ========================
    # 同步块
    # ========================

    def exec_sync_stmt(self, node: SyncStmt, env: Environment):
        """执行同步块"""
        mutex = self.eval_expression(node.mutex, env)

        if isinstance(mutex, Mutex):
            with mutex:
                self._exec_block(node.body, env)
        else:
            raise 类型错误("同步块需要互斥锁对象")

    # ========================
    # 异步执行
    # ========================

    def run_async(self, coro):
        """运行协程"""
        return self.async_context.loop.run_until_complete(coro)

    def start_event_loop(self):
        """启动事件循环（在单独线程中）"""

        def loop_runner():
            asyncio.set_event_loop(self.async_context.loop)
            self.async_context.loop.run_forever()

        loop_thread = Thread(target=loop_runner, daemon=True)
        loop_thread.start()

    def stop_event_loop(self):
        """停止事件循环"""
        self.async_context.loop.call_soon_threadsafe(self.async_context.loop.stop)
