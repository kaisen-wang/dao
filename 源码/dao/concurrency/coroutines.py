"""
协程调度模块
============

为道语言提供协程调度支持：
- CoroutineScheduler：基于 asyncio 的轻量级协程调度器
- CoroutinePool：协程池，限制并发协程数量
"""

import asyncio
from concurrent.futures import ThreadPoolExecutor


class CoroutineScheduler:
    """基于 asyncio 的轻量级协程调度器

    支持协程创建、挂起、恢复、取消，以及协程间通信。
    """

    def __init__(self, max_concurrent=None):
        self._tasks = {}
        self._task_counter = 0
        self._max_concurrent = max_concurrent
        self._semaphore = asyncio.Semaphore(max_concurrent) if max_concurrent else None

    async def spawn(self, coro, name=None):
        """创建并启动一个协程

        Args:
            coro: 协程对象
            name: 可选的协程名称

        Returns:
            任务ID
        """
        if self._semaphore:
            await self._semaphore.acquire()

        self._task_counter += 1
        task_id = self._task_counter

        if name is None:
            name = f"coroutine-{task_id}"

        task = asyncio.create_task(self._run_task(coro, task_id))
        self._tasks[task_id] = {
            "task": task,
            "name": name,
            "status": "running",
        }
        return task_id

    async def _run_task(self, coro, task_id):
        """运行任务内部方法"""
        try:
            result = await coro
            self._tasks[task_id]["status"] = "completed"
            self._tasks[task_id]["result"] = result
            return result
        except asyncio.CancelledError:
            self._tasks[task_id]["status"] = "cancelled"
            raise
        except Exception as e:
            self._tasks[task_id]["status"] = "failed"
            self._tasks[task_id]["error"] = e
            raise
        finally:
            if self._semaphore:
                self._semaphore.release()

    async def cancel(self, task_id):
        """取消一个协程"""
        if task_id in self._tasks:
            task = self._tasks[task_id]["task"]
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass

    def status(self, task_id):
        """获取协程状态"""
        if task_id in self._tasks:
            return self._tasks[task_id]["status"]
        return "unknown"

    def get_result(self, task_id):
        """获取协程结果"""
        if task_id in self._tasks:
            info = self._tasks[task_id]
            if info["status"] == "completed":
                return info.get("result")
            elif info["status"] == "failed":
                raise info.get("error")
        return None

    async def wait_all(self):
        """等待所有协程完成"""
        tasks = [info["task"] for info in self._tasks.values()
                 if info["status"] == "running"]
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)

    async def wait_any(self):
        """等待任意一个协程完成"""
        tasks = [info["task"] for info in self._tasks.values()
                 if info["status"] == "running"]
        if tasks:
            done, _ = await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
            return done

    @property
    def active_count(self):
        """当前活跃协程数量"""
        return sum(1 for info in self._tasks.values()
                   if info["status"] == "running")

    @property
    def task_count(self):
        """总协程数量"""
        return len(self._tasks)


class CoroutinePool:
    """协程池

    限制并发协程数量，复用协程资源。
    """

    def __init__(self, max_workers=10):
        self._max_workers = max_workers
        self._semaphore = asyncio.Semaphore(max_workers)
        self._tasks = set()

    async def submit(self, coro):
        """提交协程到池中执行"""
        await self._semaphore.acquire()
        task = asyncio.create_task(self._run_with_semaphore(coro))
        self._tasks.add(task)
        task.add_done_callback(self._tasks.discard)
        return task

    async def _run_with_semaphore(self, coro):
        """带信号量控制的协程执行"""
        try:
            return await coro
        finally:
            self._semaphore.release()

    async def wait_all(self):
        """等待所有任务完成"""
        if self._tasks:
            await asyncio.gather(*self._tasks, return_exceptions=True)

    @property
    def active_count(self):
        """当前活跃任务数量"""
        return len(self._tasks)

    @property
    def max_workers(self):
        """最大工作协程数"""
        return self._max_workers
