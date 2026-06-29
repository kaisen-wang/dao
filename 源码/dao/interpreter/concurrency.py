"""
并发编程解释器
===============

实现道语言的并发编程特性：
- 异步/等待
- 协程和通道
- 同步原语
"""

import asyncio
from concurrent.futures import ThreadPoolExecutor
from threading import Thread

from ..ast_nodes import (
    AsyncFunctionDecl,
    AwaitAllExpr,
    AwaitExpr,
    AwaitRaceExpr,
    ChannelExpr,
    ParallelStmt,
    ReceiveExpr,
    SelectStmt,
    SendStmt,
    SyncStmt,
)
from ..builtins.callables import DaoAsyncFunction
from ..concurrency import (
    BufferedChannel,
    Channel,
    Mutex,
)
from ..environment import Environment
from ..errors import 类型错误


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


class ConcurrencyEvaluator:
    """并发编程解释器混入类"""

    def __init__(self):
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
        for param, arg in zip(func.params, args):
            func_env.set(param, arg)
        for name, value in kwargs.items():
            func_env.set(name, value)
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
            self.exec_statement(stmt, env)

    # ========================
    # 等待表达式
    # ========================

    async def eval_await_expr(self, node: AwaitExpr, env: Environment):
        """求值等待表达式"""
        value = self.eval_expression(node.expression, env)

        if hasattr(value, "is_async") and value.is_async:
            coro = self.eval_async_function_call(value, [], {})
            return await coro
        elif hasattr(value, "__call__") and asyncio.iscoroutinefunction(value):
            return await value()
        elif asyncio.iscoroutine(value):
            return await value
        else:
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
        import threading

        threads = []
        for stmt in node.body:
            t = threading.Thread(target=self._dispatch_statement, args=(stmt, env))
            t.start()
            threads.append(t)

        for t in threads:
            t.join(timeout=30.0)

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
        """执行选择语句（同步版本）"""
        timeout_case = next((c for c in node.cases if c.type == "timeout"), None)
        timeout = None
        if timeout_case:
            timeout = self.eval_expression(timeout_case.timeout_value, env)

        for case in node.cases:
            if case.type == "condition":
                if hasattr(case, "condition"):
                    condition_value = self.eval_expression(case.condition, env)
                    if condition_value:
                        case_env = env.create_child()
                        if case.variable:
                            case_env.set(case.variable, condition_value)
                        self._exec_block(case.body, case_env)
                        return

        for case in node.cases:
            if case.type == "receive":
                try:
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
                except Exception:
                    continue

        if timeout_case:
            import time

            time.sleep(timeout)
            self._exec_block(timeout_case.body, env)

    async def exec_select_stmt_async(self, node: SelectStmt, env: Environment):
        """执行选择语句（异步版本）"""
        timeout_case = next((c for c in node.cases if c.type == "timeout"), None)
        timeout = None
        if timeout_case:
            timeout = self.eval_expression(timeout_case.timeout_value, env)

        for case in node.cases:
            if case.type == "condition":
                if hasattr(case, "condition"):
                    condition_value = self.eval_expression(case.condition, env)
                    if condition_value:
                        case_env = env.create_child()
                        if case.variable:
                            case_env.set(case.variable, condition_value)
                        await self._exec_async_block(case.body, case_env)
                        return

        tasks = []

        for case in node.cases:
            if case.type == "receive":
                channel = self.eval_expression(case.channel, env)
                if isinstance(channel, Channel) or isinstance(channel, BufferedChannel):
                    task = asyncio.create_task(self._await_receive(channel, case, env))
                    tasks.append(task)

        if timeout_case:
            timeout_task = asyncio.create_task(
                self._await_timeout(timeout, timeout_case, env)
            )
            tasks.append(timeout_task)

        try:
            done, pending = await asyncio.wait(
                tasks,
                timeout=timeout if timeout_case else None,
                return_when=asyncio.FIRST_COMPLETED,
            )

            for task in pending:
                task.cancel()

            if done:
                return await next(iter(done))
            else:
                if timeout_case:
                    await self._exec_async_block(timeout_case.body, env)

        except asyncio.TimeoutError:
            if timeout_case:
                await self._exec_async_block(timeout_case.body, env)

    async def _await_receive(self, channel, case, env):
        """异步接收操作"""
        try:
            value = await channel.receive_async()
            case_env = env.create_child()
            if case.variable:
                case_env.set(case.variable, value)
            await self._exec_async_block(case.body, case_env)
            return True
        except Exception:
            return False

    async def _await_timeout(self, timeout, case, env):
        """异步超时操作"""
        await asyncio.sleep(timeout)
        await self._exec_async_block(case.body, env)
        return False

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
