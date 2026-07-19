"""
并发编程解释器
===============

实现道语言的并发编程特性：
- 异步/等待
- 协程和通道
- 同步原语
"""

import asyncio
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
    AsyncContext,
    BufferedChannel,
    Channel,
    CoroutinePool,
    CoroutineScheduler,
    Mutex,
)
from ..environment import Environment
from ..errors import 类型错误


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
        """求值全部等待表达式

        返回列表，包含所有协程的返回值（按输入顺序）。
        支持超时参数。
        """
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

        # 使用封装后的 run_all，返回道语言友好的列表结构
        return await self.async_context.run_all(coros)

    async def eval_await_race_expr(self, node: AwaitRaceExpr, env: Environment):
        """求值竞速等待表达式

        返回最先完成的协程的返回值。
        支持超时参数。
        """
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

        # 使用封装后的 run_race，返回道语言友好的结果
        return await self.async_context.run_race(coros)

    # ========================
    # 协程
    # ========================

    def exec_parallel_stmt(self, node: ParallelStmt, env: Environment):
        """执行并行块（同步入口）

        优先使用基于 asyncio 的轻量级协程调度器，
        避免线程开销，支持大量轻量级协程。
        """
        try:
            loop = asyncio.get_running_loop()
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor() as pool:
                future = pool.submit(asyncio.run, self._exec_parallel_stmt(node, env))
                future.result(timeout=60)
        except RuntimeError:
            asyncio.run(self._exec_parallel_stmt(node, env))

    async def _exec_parallel_stmt(self, node: ParallelStmt, env: Environment):
        """执行并行块（基于协程调度器）"""
        scheduler = CoroutineScheduler()
        for stmt in node.body:
            await scheduler.spawn(self._exec_parallel_coroutine(stmt, env))
        await scheduler.wait_all()

    async def _exec_parallel_coroutine(self, stmt, env: Environment):
        """并行执行单个语句的协程任务"""
        token_type = type(stmt).__name__
        handler_name = f"exec_{token_type}"
        if hasattr(self, handler_name):
            handler = getattr(self, handler_name)
            if asyncio.iscoroutinefunction(handler):
                await handler(stmt, env)
            else:
                handler(stmt, env)
        else:
            self.exec_statement(stmt, env)

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
        """执行选择语句（同步版本）

        完善的超时处理：
        1. 先检查条件分支
        2. 尝试非阻塞接收
        3. 有超时时，在超时时间内轮询接收
        4. 超时后执行超时分支
        """
        import time

        timeout_case = next((c for c in node.cases if c.type == "timeout"), None)
        timeout = None
        if timeout_case:
            timeout = self.eval_expression(timeout_case.timeout_value, env)

        # 1. 先检查条件分支
        for case in node.cases:
            if case.type == "condition":
                if hasattr(case, "condition"):
                    condition_value = self.eval_expression(case.condition, env)
                    if condition_value:
                        case_env = env.create_child()
                        if case.variable:
                            case_env.define(case.variable, condition_value)
                        self._exec_block(case.body, case_env)
                        return

        # 2. 尝试非阻塞接收
        for case in node.cases:
            if case.type == "receive":
                try:
                    channel = self.eval_expression(case.channel, env)
                    if isinstance(channel, Channel) or isinstance(
                        channel, BufferedChannel
                    ):
                        value = channel.queue.get_nowait()
                        case_env = env.create_child()
                        if case.variable:
                            case_env.define(case.variable, value)
                        self._exec_block(case.body, case_env)
                        return
                except Exception:
                    continue

        # 3. 有超时时，在超时时间内轮询接收
        if timeout is not None:
            start_time = time.time()
            while True:
                elapsed = time.time() - start_time
                if elapsed >= timeout:
                    break

                for case in node.cases:
                    if case.type == "receive":
                        try:
                            channel = self.eval_expression(case.channel, env)
                            if isinstance(channel, Channel) or isinstance(
                                channel, BufferedChannel
                            ):
                                remaining = timeout - elapsed
                                value = channel.queue.get(
                                    block=True, timeout=min(remaining, 0.05)
                                )
                                case_env = env.create_child()
                                if case.variable:
                                    case_env.define(case.variable, value)
                                self._exec_block(case.body, case_env)
                                return
                        except Exception:
                            continue

            # 4. 超时后执行超时分支
            if timeout_case:
                self._exec_block(timeout_case.body, env)
        else:
            # 无超时，阻塞等待
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
                                case_env.define(case.variable, value)
                            self._exec_block(case.body, case_env)
                            return
                    except Exception:
                        continue

    async def exec_select_stmt_async(self, node: SelectStmt, env: Environment):
        """执行选择语句（异步版本）

        完善的超时处理：
        1. 先检查条件分支
        2. 创建接收任务和超时任务
        3. 竞速等待，正确清理未完成的接收操作
        4. 超时异常正确传播
        """
        timeout_case = next((c for c in node.cases if c.type == "timeout"), None)
        timeout = None
        if timeout_case:
            timeout = self.eval_expression(timeout_case.timeout_value, env)

        # 1. 先检查条件分支
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

        # 2. 创建接收任务
        receive_tasks = {}
        for case in node.cases:
            if case.type == "receive":
                channel = self.eval_expression(case.channel, env)
                if isinstance(channel, Channel) or isinstance(channel, BufferedChannel):
                    task = asyncio.create_task(self._await_receive(channel, case, env))
                    receive_tasks[task] = case

        if not receive_tasks:
            # 没有接收任务，仅有超时
            if timeout_case:
                await asyncio.sleep(timeout)
                await self._exec_async_block(timeout_case.body, env)
            return

        # 3. 创建超时任务（如果有）
        all_tasks = list(receive_tasks.keys())
        if timeout_case:
            timeout_task = asyncio.create_task(
                self._await_timeout(timeout, timeout_case, env)
            )
            all_tasks.append(timeout_task)

        try:
            done, pending = await asyncio.wait(
                all_tasks,
                return_when=asyncio.FIRST_COMPLETED,
            )

            # 4. 正确清理未完成的接收操作
            for task in pending:
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass

            # 处理完成的任务
            if done:
                for task in done:
                    if task in receive_tasks:
                        # 接收任务完成
                        result = task.result()
                        return result
                    else:
                        # 超时任务完成
                        result = task.result()
                        return result

        except asyncio.CancelledError:
            # 当前任务被取消，清理所有子任务
            for task in all_tasks:
                task.cancel()
            raise
        except Exception:
            # 其他异常，清理所有子任务
            for task in all_tasks:
                if not task.done():
                    task.cancel()
            raise

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
