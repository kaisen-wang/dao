"""
并发运行时补测
==============

针对并发解释执行路径、通道异步接口、协程调度器与选择器的分支补测。
所有异步测试使用 asyncio.run 驱动，不依赖真实网络或长时间等待。

运行：
    pytest tests/test_concurrency_runtime.py -q
"""

import asyncio
import os
import sys
import threading
import time

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

import pytest

from dao.ast_nodes import (
    Assignment,
    AwaitAllExpr,
    AwaitExpr,
    AwaitRaceExpr,
    BooleanLiteral,
    ChannelExpr,
    ExpressionStmt,
    Identifier,
    NumberLiteral,
    ParallelStmt,
    ReceiveExpr,
    SelectCase,
    SelectStmt,
    SendStmt,
    StringLiteral,
    SyncStmt,
    VariableDecl,
)
from dao.builtins.callables import DaoAsyncFunction
from dao.concurrency import (
    AsyncBufferedChannel,
    AsyncChannel,
    BufferedChannel,
    Channel,
    CoroutinePool,
    CoroutineScheduler,
    Mutex,
    Semaphore,
)
from dao.concurrency.async_await import AsyncContext, run_async
from dao.concurrency.selectors import select_receive, select_receive_sync
from dao.environment import Environment
from dao.errors import 类型错误, 运行时错误
from dao.interpreter import Interpreter
from dao.interpreter.concurrency import ConcurrencyEvaluator


# ============================================================
# 辅助
# ============================================================

def fresh_interpreter():
    """创建解释器，并确保其异步上下文持有可用的事件循环"""
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    interp = Interpreter()
    # Interpreter.__init__ 未调用超类构造函数，这里补齐并发上下文与 source
    interp.async_context = AsyncContext()
    interp.async_context.loop = loop
    interp.source = ""
    return interp


def fresh_context():
    """创建 AsyncContext，先确保当前线程有可用的事件循环"""
    asyncio.set_event_loop(asyncio.new_event_loop())
    return AsyncContext()


async def _coro(value, delay=0):
    if delay:
        await asyncio.sleep(delay)
    return value


async def _coro_raise():
    await asyncio.sleep(0)
    raise ValueError("协程异常")


def _async_fn(value):
    async def fn():
        await asyncio.sleep(0)
        return value
    return fn


# ============================================================
# 解释器：等待表达式
# ============================================================

class TestAwaitExpressionBranches:
    """覆盖 ConcurrencyEvaluator 等待表达式的四种取值分支"""

    def test_eval_await_expr_plain_value(self):
        interp = fresh_interpreter()
        env = Environment()
        node = AwaitExpr(expression=NumberLiteral(value=7))
        assert asyncio.run(interp.eval_await_expr(node, env)) == 7

    def test_eval_await_expr_coroutine_object(self):
        interp = fresh_interpreter()
        env = Environment()
        env.define("co", _coro(11))
        node = AwaitExpr(expression=Identifier(name="co"))
        assert asyncio.run(interp.eval_await_expr(node, env)) == 11

    def test_eval_await_expr_coroutine_function(self):
        interp = fresh_interpreter()
        env = Environment()
        env.define("cf", _async_fn(13))
        node = AwaitExpr(expression=Identifier(name="cf"))
        assert asyncio.run(interp.eval_await_expr(node, env)) == 13

    def test_eval_await_expr_async_function_object(self):
        interp = fresh_interpreter()
        env = Environment()
        af = DaoAsyncFunction(
            "异步取值", [], [VariableDecl(name="结果", value=NumberLiteral(value=17))], env
        )
        env.define("af", af)
        node = AwaitExpr(expression=Identifier(name="af"))
        assert asyncio.run(interp.eval_await_expr(node, env)) is None

    def test_eval_async_function_call_and_block(self):
        interp = fresh_interpreter()
        env = Environment()
        af = DaoAsyncFunction(
            "异步取值", [], [VariableDecl(name="结果", value=NumberLiteral(value=19))], env
        )

        async def run():
            return await interp.eval_async_function_call(af, [], {})

        # _exec_async_block 不返回最后一条语句的值，故返回 None
        assert asyncio.run(run()) is None

    def test_exec_statement_async_handler_and_fallback(self):
        interp = fresh_interpreter()
        env = Environment()
        env.define("标记", 0)
        calls = []

        async def async_handler(stmt, e):
            calls.append("async")

        interp.exec_NumberLiteral = async_handler

        async def run():
            await interp._exec_statement(NumberLiteral(value=1), env)
            # 没设置专用 handler 的语句类型走同步回退分支
            await interp._exec_statement(ExpressionStmt(NumberLiteral(value=2)), env)

        asyncio.run(run())
        assert calls == ["async"]

    def test_eval_await_all_expr_all_branches(self):
        interp = fresh_interpreter()
        env = Environment()
        env.define("cf", _async_fn(2))
        env.define("co", _coro(3))
        af = DaoAsyncFunction(
            "异步取值", [], [VariableDecl(name="结果", value=NumberLiteral(value=4))], env
        )
        env.define("af", af)
        node = AwaitAllExpr(
            expressions=[
                NumberLiteral(value=1),
                Identifier(name="cf"),
                Identifier(name="co"),
                Identifier(name="af"),
            ]
        )
        results = asyncio.run(interp.eval_await_all_expr(node, env))
        assert len(results) == 4
        assert 1 in results and 2 in results and 3 in results

    def test_eval_await_race_expr_returns_fastest(self):
        interp = fresh_interpreter()
        env = Environment()
        env.define("slow", _coro(1, delay=0.05))
        env.define("fast", _coro(2, delay=0.001))
        node = AwaitRaceExpr(
            expressions=[Identifier(name="slow"), Identifier(name="fast")]
        )
        assert asyncio.run(interp.eval_await_race_expr(node, env)) == 2

    def test_eval_await_race_expr_all_value_branches(self):
        """四种取值分支（普通值/协程函数/协程对象/异步函数）均应被接受"""
        interp = fresh_interpreter()
        env = Environment()
        env.define("cf", _async_fn(5))
        env.define("co", _coro(6))
        af = DaoAsyncFunction(
            "异步取值", [], [VariableDecl(name="结果", value=NumberLiteral(value=7))], env
        )
        env.define("af", af)
        node = AwaitRaceExpr(
            expressions=[
                NumberLiteral(value=4),
                Identifier(name="cf"),
                Identifier(name="co"),
                Identifier(name="af"),
            ]
        )
        # 竞速结果取决于完成顺序，只断言不抛异常
        asyncio.run(interp.eval_await_race_expr(node, env))


# ============================================================
# 解释器：并行块
# ============================================================

class TestParallelBranches:
    """覆盖并行块的同步入口、协程调度与语句分派分支"""

    def test_exec_parallel_stmt_without_running_loop(self):
        interp = fresh_interpreter()
        env = Environment()
        env.define("结果", 0)
        node = ParallelStmt(body=[])
        # 无运行中的事件循环 -> asyncio.run 分支
        interp.exec_parallel_stmt(node, env)

    def test_exec_parallel_stmt_with_running_loop(self):
        interp = fresh_interpreter()
        env = Environment()
        node = ParallelStmt(body=[])

        async def outer():
            # 已有运行中的事件循环 -> 线程池分支
            interp.exec_parallel_stmt(node, env)

        asyncio.run(outer())

    def test_parallel_coroutine_handler_branches(self):
        interp = fresh_interpreter()
        env = Environment()
        called = []

        interp.exec_NumberLiteral = lambda stmt, e: called.append("sync")

        async def async_handler(stmt, e):
            called.append("async")

        interp.exec_StringLiteral = async_handler

        async def run():
            await interp._exec_parallel_coroutine(NumberLiteral(value=1), env)
            await interp._exec_parallel_coroutine(StringLiteral(value="x"), env)
            # 无对应 handler -> 回退 exec_statement
            await interp._exec_parallel_coroutine(VariableDecl(name="a"), env)

        asyncio.run(run())
        assert called == ["sync", "async"]


# ============================================================
# 解释器：通道、发送、接收、同步块
# ============================================================

class TestChannelStatementBranches:
    def test_eval_channel_expr(self):
        interp = fresh_interpreter()
        env = Environment()
        assert isinstance(interp.eval_channel_expr(ChannelExpr(), env), Channel)
        buffered = interp.eval_channel_expr(ChannelExpr(capacity=3), env)
        assert isinstance(buffered, BufferedChannel)

    def test_exec_send_stmt_valid_and_invalid(self):
        interp = fresh_interpreter()
        env = Environment()
        ch = Channel()
        env.define("ch", ch)
        interp.exec_send_stmt(
            SendStmt(channel=Identifier(name="ch"), value=NumberLiteral(value=9)), env
        )
        assert ch.receive() == 9

        env.define("non_ch", 42)
        with pytest.raises(类型错误):
            interp.exec_send_stmt(
                SendStmt(channel=Identifier(name="non_ch"), value=NumberLiteral(value=1)), env
            )

    def test_eval_receive_expr_valid_and_invalid(self):
        interp = fresh_interpreter()
        env = Environment()
        ch = BufferedChannel(1)
        ch.send(12)
        env.define("ch", ch)
        assert interp.eval_receive_expr(ReceiveExpr(channel=Identifier(name="ch")), env) == 12

        env.define("non_ch", 42)
        with pytest.raises(类型错误):
            interp.eval_receive_expr(
                ReceiveExpr(channel=Identifier(name="non_ch")), env
            )

    def test_exec_sync_stmt_valid_and_invalid(self):
        interp = fresh_interpreter()
        env = Environment()
        mutex = Mutex()
        env.define("m", mutex)
        env.define("结果", 0)
        interp.exec_sync_stmt(
            SyncStmt(
                mutex=Identifier(name="m"),
                body=[VariableDecl(name="结果", value=NumberLiteral(value=1))],
            ),
            env.create_child(),
        )

        env.define("non_mutex", 1)
        with pytest.raises(类型错误):
            interp.exec_sync_stmt(
                SyncStmt(mutex=Identifier(name="non_mutex"), body=[]), env
            )


# ============================================================
# 解释器：选择语句（同步）
# ============================================================

class TestSelectStatementSync:
    def _env_with_result(self):
        env = Environment()
        env.define("结果", 0)
        return env

    @staticmethod
    def _set_result_body():
        return [Assignment(target=Identifier(name="结果"), value=NumberLiteral(value=1))]

    def test_condition_case(self):
        interp = fresh_interpreter()
        env = self._env_with_result()
        case = SelectCase(type="condition", body=self._set_result_body())
        case.condition = BooleanLiteral(value=True)
        interp.exec_select_stmt(SelectStmt(cases=[case]), env)
        # 分支体在子环境中执行，Assignment 沿作用域链修改父变量
        assert env.get("结果") == 1

    def test_condition_case_with_variable(self):
        interp = fresh_interpreter()
        env = self._env_with_result()
        case = SelectCase(type="condition", variable="绑定", body=[])
        case.condition = BooleanLiteral(value=True)
        interp.exec_select_stmt(SelectStmt(cases=[case]), env)

    def test_nonblocking_receive_case(self):
        interp = fresh_interpreter()
        env = self._env_with_result()
        ch = BufferedChannel(1)
        ch.send(99)
        env.define("ch", ch)
        case = SelectCase(
            type="receive", channel=Identifier(name="ch"), variable="值", body=[]
        )
        interp.exec_select_stmt(SelectStmt(cases=[case]), env)

    def test_timeout_case(self):
        interp = fresh_interpreter()
        env = self._env_with_result()
        case = SelectCase(
            type="timeout", timeout_value=NumberLiteral(value=0.01), body=[]
        )
        interp.exec_select_stmt(SelectStmt(cases=[case]), env)

    def test_blocking_receive_without_timeout(self):
        interp = fresh_interpreter()
        env = self._env_with_result()
        ch = Channel()
        env.define("ch", ch)
        case = SelectCase(
            type="receive", channel=Identifier(name="ch"), variable="值", body=[]
        )

        def delayed_send():
            time.sleep(0.02)
            ch.send(31)

        t = threading.Thread(target=delayed_send)
        t.start()
        interp.exec_select_stmt(SelectStmt(cases=[case]), env)
        t.join()
        assert ch.queue.empty()

    def test_no_cases_does_nothing(self):
        interp = fresh_interpreter()
        env = self._env_with_result()
        interp.exec_select_stmt(SelectStmt(cases=[]), env)


# ============================================================
# 解释器：选择语句（异步）及事件循环管理
# ============================================================

class _CancellableChannel(Channel):
    """可被立即取消的通道，避免测试卡在线程池的阻塞接收上"""

    async def receive_async(self):
        await asyncio.Event().wait()


class TestSelectStatementAsync:
    def test_async_condition_case(self):
        interp = fresh_interpreter()
        env = Environment()
        case = SelectCase(type="condition", body=[])
        case.condition = BooleanLiteral(value=True)
        asyncio.run(interp.exec_select_stmt_async(SelectStmt(cases=[case]), env))

    def test_async_timeout_only(self):
        interp = fresh_interpreter()
        env = Environment()
        case = SelectCase(type="timeout", timeout_value=NumberLiteral(value=0.01), body=[])
        asyncio.run(interp.exec_select_stmt_async(SelectStmt(cases=[case]), env))

    def test_async_receive_and_timeout_with_cleanup(self):
        interp = fresh_interpreter()
        env = Environment()
        env.define("v", 0)
        fast = BufferedChannel(1)
        fast.send(55)
        env.define("fast", fast)
        slow = _CancellableChannel()
        env.define("slow", slow)

        cases = [
            SelectCase(type="receive", channel=Identifier(name="fast"), variable="v", body=[]),
            SelectCase(type="receive", channel=Identifier(name="slow"), variable="v", body=[]),
            SelectCase(type="timeout", timeout_value=NumberLiteral(value=0.2), body=[]),
        ]
        result = asyncio.run(
            interp.exec_select_stmt_async(SelectStmt(cases=cases), env)
        )
        assert result is True

    def test_async_receive_failure_returns_false(self):
        interp = fresh_interpreter()
        env = Environment()
        ch = _CancellableChannel()
        env.define("ch", ch)
        case = SelectCase(type="receive", channel=Identifier(name="ch"), variable="v", body=[])
        # 超时任务先完成，接收任务被取消后 `_await_receive` 捕获异常返回 False
        result = asyncio.run(
            interp.exec_select_stmt_async(
                SelectStmt(
                    cases=[
                        case,
                        SelectCase(
                            type="timeout", timeout_value=NumberLiteral(value=0.01), body=[]
                        ),
                    ]
                ),
                env,
            )
        )
        assert result is False

    def test_async_outer_cancellation_cleans_up(self):
        interp = fresh_interpreter()
        env = Environment()
        ch = _CancellableChannel()
        env.define("ch", ch)
        node = SelectStmt(cases=[SelectCase(
            type="receive", channel=Identifier(name="ch"), variable="v", body=[]
        )])

        async def outer():
            task = asyncio.create_task(interp.exec_select_stmt_async(node, env))
            await asyncio.sleep(0)
            task.cancel()
            with pytest.raises(asyncio.CancelledError):
                await task

        asyncio.run(outer())

    def test_await_receive_and_timeout_helpers(self):
        interp = fresh_interpreter()
        env = Environment()
        env.define("v", 0)

        async def run():
            ch = BufferedChannel(1)
            ch.send(77)
            case = SelectCase(type="receive", variable="v", body=[])
            assert await interp._await_receive(ch, case, env) is True
            assert await interp._await_timeout(0.01, SelectCase(body=[]), env) is False

        asyncio.run(run())

    def test_run_async_and_event_loop_lifecycle(self):
        interp = fresh_interpreter()
        loop = asyncio.new_event_loop()
        interp.async_context.loop = loop
        try:
            assert interp.run_async(_coro(23)) == 23
            interp.start_event_loop()
            time.sleep(0.02)
            interp.stop_event_loop()
            time.sleep(0.02)
        finally:
            if not loop.is_closed():
                loop.close()


# ============================================================
# AsyncContext / run_async 辅助函数
# ============================================================

class TestAsyncContextHelpers:
    def test_run(self):
        ctx = fresh_context()
        try:
            assert asyncio.run(ctx.run(_coro(3))) == 3
        finally:
            ctx.close()

    def test_run_all_normal_and_exceptions(self):
        ctx = fresh_context()
        try:
            async def run():
                return await ctx.run_all([_coro(1), _coro_raise(), _coro(3)])

            results = asyncio.run(run())
            assert results[0] == 1
            assert isinstance(results[1], dict) and "错误" in results[1]
            assert results[2] == 3
        finally:
            ctx.close()

    def test_run_all_timeout(self):
        ctx = fresh_context()
        try:
            async def run():
                return await ctx.run_all([_coro(1, delay=0.2)], timeout=0.01)

            with pytest.raises(asyncio.TimeoutError):
                asyncio.run(run())
        finally:
            ctx.close()

    def test_run_race_fastest_and_empty(self):
        ctx = fresh_context()
        try:
            assert asyncio.run(ctx.run_race([_coro(1, 0.2), _coro(2)])) == 2
            assert asyncio.run(ctx.run_race([])) is None
        finally:
            ctx.close()

    def test_run_race_timeout_and_exception(self):
        ctx = fresh_context()
        try:
            assert (
                asyncio.run(ctx.run_race([_coro(1, 0.2)], timeout=0.01)) is None
            )
            with pytest.raises(ValueError):
                asyncio.run(ctx.run_race([_coro_raise()]))
        finally:
            ctx.close()

    def test_run_async_helper_without_running_loop(self):
        assert run_async(_coro(29)) == 29

    def test_run_async_helper_with_running_loop(self):
        async def outer():
            return run_async(_coro(31))

        assert asyncio.run(outer()) == 31

    def test_stop_on_fresh_context(self):
        ctx = fresh_context()
        ctx.stop()
        ctx.close()


# ============================================================
# 通道异步接口
# ============================================================

class TestChannelAsyncInterfaces:
    def test_channel_send_async_receive_async(self):
        ch = Channel()

        async def run():
            await ch.send_async(41)
            return await ch.receive_async()

        assert asyncio.run(run()) == 41

    def test_channel_async_closed_errors(self):
        ch = Channel()
        ch.close()
        with pytest.raises(运行时错误):
            asyncio.run(ch.send_async(1))
        # 协程中抛出的 StopIteration 会被 PEP 479 转换为 RuntimeError
        with pytest.raises(RuntimeError):
            asyncio.run(ch.receive_async())

    def test_channel_timeout_error_paths(self):
        ch = Channel()

        def fake_put(*args, **kwargs):
            raise TimeoutError("模拟发送超时")

        def fake_get(*args, **kwargs):
            raise TimeoutError("模拟接收超时")

        ch._queue.put = fake_put
        with pytest.raises(运行时错误):
            ch.send(1)
        ch._queue.get = fake_get
        with pytest.raises(运行时错误):
            ch.receive()

    def test_buffered_channel_async_and_error_paths(self):
        ch = BufferedChannel(1)

        async def run():
            await ch.send_async(43)
            return await ch.receive_async()

        assert asyncio.run(run()) == 43

        ch.close()
        with pytest.raises(运行时错误):
            asyncio.run(ch.send_async(1))
        # 协程中抛出的 StopIteration 会被 PEP 479 转换为 RuntimeError
        with pytest.raises(RuntimeError):
            asyncio.run(ch.receive_async())

    def test_buffered_channel_send_error(self):
        ch = BufferedChannel(1)

        def fake_put(*args, **kwargs):
            raise ValueError("模拟缓冲区错误")

        ch.queue.put = fake_put
        with pytest.raises(运行时错误):
            ch.send(1)

    def test_buffered_channel_receive_timeout(self):
        from queue import Empty

        ch = BufferedChannel(1)

        def fake_get(*args, **kwargs):
            raise Empty()

        ch.queue.get = fake_get
        with pytest.raises(运行时错误):
            ch.receive()

    def test_async_channel_roundtrip(self):
        ch = AsyncChannel()

        async def run():
            await ch.send_async(45)
            return await ch.receive_async()

        assert asyncio.run(run()) == 45

    def test_async_channel_sync_wrappers_and_closed(self):
        ch = AsyncChannel()
        ch.send(47)
        assert ch.receive() == 47
        ch.close()
        with pytest.raises(运行时错误):
            ch.send(1)
        with pytest.raises(StopIteration):
            ch.receive()
        with pytest.raises(运行时错误):
            asyncio.run(ch.send_async(1))
        # 协程中抛出的 StopIteration 会被 PEP 479 转换为 RuntimeError
        with pytest.raises(RuntimeError):
            asyncio.run(ch.receive_async())

    def test_async_channel_timeout_paths(self):
        ch = AsyncChannel()

        async def fake_put(value):
            raise asyncio.TimeoutError()

        async def fake_get():
            raise asyncio.TimeoutError()

        ch._queue.put = fake_put
        with pytest.raises(运行时错误):
            asyncio.run(ch.send_async(1))

        ch2 = AsyncChannel()
        ch2._queue.get = fake_get
        with pytest.raises(运行时错误):
            asyncio.run(ch2.receive_async())

        ch3 = AsyncChannel()
        ch3.close()
        # 协程中抛出的 StopIteration 会被 PEP 479 转换为 RuntimeError
        with pytest.raises(RuntimeError):
            asyncio.run(ch3.receive_async())

    def test_async_buffered_channel_roundtrip(self):
        ch = AsyncBufferedChannel(2)
        ch.send(49)
        assert ch.receive() == 49

        async def run():
            await ch.send_async(50)
            return await ch.receive_async()

        assert asyncio.run(run()) == 50

    def test_async_buffered_channel_closed_and_timeout(self):
        ch = AsyncBufferedChannel(1)
        ch.close()
        with pytest.raises(运行时错误):
            ch.send(1)
        with pytest.raises(StopIteration):
            ch.receive()
        with pytest.raises(运行时错误):
            asyncio.run(ch.send_async(1))
        # 协程中抛出的 StopIteration 会被 PEP 479 转换为 RuntimeError
        with pytest.raises(RuntimeError):
            asyncio.run(ch.receive_async())

        ch2 = AsyncBufferedChannel(1)

        async def fake_put(value):
            raise asyncio.TimeoutError()

        async def fake_get():
            raise asyncio.TimeoutError()

        ch2._queue.put = fake_put
        with pytest.raises(运行时错误):
            asyncio.run(ch2.send_async(1))

        ch3 = AsyncBufferedChannel(1)
        ch3._queue.get = fake_get
        with pytest.raises(运行时错误):
            asyncio.run(ch3.receive_async())

    def test_select_helpers(self):
        ch = BufferedChannel(1)
        ch.send(51)

        async def run():
            result = await select_receive([(ch, "v")])
            return result

        channel, var, value = asyncio.run(run())
        assert value == 51 and var == "v"

        # 同步版本
        ch2 = BufferedChannel(1)
        ch2.send(52)
        result = select_receive_sync([(ch2, "v")], timeout=0.1)
        assert result[2] == 52

        # 超时分支
        called = []
        result = select_receive_sync(
            [], timeout=0.01, timeout_handler=lambda: called.append(1)
        )
        assert result is None and called == [1]

    def test_select_receive_timeout_async(self):
        async def timeout_handler():
            return None

        result = asyncio.run(
            select_receive([], timeout=0.01, timeout_handler=timeout_handler)
        )
        assert result is None


# ============================================================
# 协程调度器与同步原语补测
# ============================================================

class TestSchedulerAndSync:
    def test_scheduler_success_failure_and_cancel(self):
        sched = CoroutineScheduler()

        async def run():
            tid_ok = await sched.spawn(_coro(1), name="成功任务")
            tid_fail = await sched.spawn(_coro_raise(), name="失败任务")
            tid_cancel = await sched.spawn(_coro(1, 0.2), name="被取消任务")
            # 让任务真正启动后再取消，避免任务未开始执行时状态未更新
            await asyncio.sleep(0)
            await sched.cancel(tid_cancel)
            await sched.wait_all()
            await sched.wait_any()
            assert sched.status(tid_ok) == "completed"
            assert sched.status(tid_fail) == "failed"
            assert sched.status(tid_cancel) == "cancelled"
            assert sched.status(999) == "unknown"
            assert sched.get_result(tid_ok) == 1
            with pytest.raises(ValueError):
                sched.get_result(tid_fail)
            assert sched.get_result(999) is None
            # 取出任务中未被 gather 消费的异常，避免 "exception was never retrieved" 日志
            for info in sched._tasks.values():
                task = info["task"]
                if task.done() and not task.cancelled():
                    task.exception()

        asyncio.run(run())
        assert sched.task_count == 3
        assert sched.active_count == 0

    def test_scheduler_max_concurrent(self):
        sched = CoroutineScheduler(max_concurrent=1)

        async def run():
            await sched.spawn(_coro(1))
            await sched.spawn(_coro(2))
            await sched.wait_all()

        asyncio.run(run())
        assert sched.active_count == 0

    def test_coroutine_pool(self):
        pool = CoroutinePool(max_workers=2)

        async def run():
            t1 = await pool.submit(_coro(1))
            t2 = await pool.submit(_coro(2))
            await asyncio.gather(t1, t2)
            await pool.wait_all()

        asyncio.run(run())
        assert pool.max_workers == 2
        assert pool.active_count == 0

    def test_semaphore_value(self):
        sem = Semaphore(2)
        assert sem.value == 2
        sem.acquire()
        assert sem.value == 1
        sem.release()
        assert sem.value == 2
        with sem:
            assert sem.value == 1
        assert sem.value == 2
