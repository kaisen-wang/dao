"""
异步/等待模块
=============

为道语言提供异步执行辅助函数：
- AsyncContext：异步执行上下文，管理事件循环和任务
- run_async：运行协程的辅助函数
- run_all：并发运行多个协程，返回列表
- run_race：竞速运行，返回最先完成的结果
"""

import asyncio
from concurrent.futures import ThreadPoolExecutor


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

    async def run_all(self, coros, timeout=None):
        """并发运行多个协程，等待所有完成

        Args:
            coros: 协程列表
            timeout: 可选超时时间（秒）

        Returns:
            列表，包含所有协程的返回值（按输入顺序）
        """
        if timeout is not None:
            results = await asyncio.wait_for(
                asyncio.gather(*coros, return_exceptions=True),
                timeout=timeout,
            )
        else:
            results = await asyncio.gather(*coros, return_exceptions=True)

        # 将异常转换为错误信息，保持列表结构
        return [
            r if not isinstance(r, Exception) else {"错误": str(r)}
            for r in results
        ]

    async def run_race(self, coros, timeout=None):
        """竞速运行，返回最快完成的结果

        Args:
            coros: 协程列表
            timeout: 可选超时时间（秒）

        Returns:
            最先完成的协程的返回值
            超时返回 None
        """
        tasks = [asyncio.ensure_future(c) for c in coros]

        try:
            if timeout is not None:
                done, pending = await asyncio.wait(
                    tasks,
                    timeout=timeout,
                    return_when=asyncio.FIRST_COMPLETED,
                )
            else:
                done, pending = await asyncio.wait(
                    tasks,
                    return_when=asyncio.FIRST_COMPLETED,
                )

            # 取消所有未完成的任务
            for task in pending:
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass

            if done:
                result = next(iter(done)).result()
                return result
            return None

        except asyncio.TimeoutError:
            for task in tasks:
                task.cancel()
            return None

    def stop(self):
        """停止事件循环"""
        self.loop.stop()

    def close(self):
        """关闭执行上下文"""
        self.executor.shutdown()
        self.loop.close()


def run_async(coro, loop=None):
    """运行协程的辅助函数

    在指定或当前事件循环中运行协程。
    如果已在事件循环中，则使用 ThreadPoolExecutor 避免阻塞。
    """
    if loop is None:
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = None

    if loop and loop.is_running():
        import concurrent.futures
        with concurrent.futures.ThreadPoolExecutor() as pool:
            future = pool.submit(asyncio.run, coro)
            return future.result(timeout=60)
    else:
        return asyncio.run(coro)
