"""
异步IO标准库测试
================

测试道语言 asyncio 标准库模块的所有功能。
"""

import asyncio
import unittest

from dao.stdlib.asyncio import (
    DaoAsyncBarrier,
    DaoAsyncCondition,
    DaoAsyncEvent,
    DaoAsyncLock,
    DaoAsyncQueue,
    DaoAsyncSemaphore,
    DaoAsyncProcess,
    DaoStreamReader,
    DaoStreamWriter,
    create_module_env,
    _stdlib_获取事件循环,
    _stdlib_运行,
    _stdlib_创建任务,
    _stdlib_当前任务,
    _stdlib_全部任务,
    _stdlib_睡眠,
    _stdlib_创建队列,
    _stdlib_创建锁,
    _stdlib_创建信号量,
    _stdlib_创建条件,
    _stdlib_创建事件,
    _stdlib_创建屏障,
    _stdlib_是否协程,
    _stdlib_是否协程函数,
    _stdlib_是否为Task,
    _stdlib_在线程中执行,
    _stdlib_异步读取文件,
    _stdlib_异步写入文件,
    _stdlib_创建子进程,
    _stdlib_打开连接,
)
from dao.stdlib.registry import STDLIB_REGISTRY


class TestAsyncIORegistry(unittest.TestCase):
    """测试异步IO模块注册"""

    def test_module_registered(self):
        """异步IO模块应已注册到标准库"""
        self.assertIn("异步IO", STDLIB_REGISTRY)

    def test_create_module_env(self):
        """create_module_env 应返回有效的环境"""
        env = create_module_env()
        self.assertIsNotNone(env)

    def test_module_exports(self):
        """模块应导出所有定义的函数"""
        env = create_module_env()
        self.assertIn("获取事件循环", env.values)
        self.assertIn("运行", env.values)
        self.assertIn("创建任务", env.values)
        self.assertIn("睡眠", env.values)
        self.assertIn("创建队列", env.values)
        self.assertIn("创建锁", env.values)
        self.assertIn("创建信号量", env.values)
        self.assertIn("创建条件", env.values)
        self.assertIn("创建事件", env.values)
        self.assertIn("创建屏障", env.values)
        self.assertIn("是否协程", env.values)
        self.assertIn("在线程中执行", env.values)
        self.assertIn("异步读取文件", env.values)
        self.assertIn("异步写入文件", env.values)


class TestEventLoopManagement(unittest.TestCase):
    """测试事件循环管理"""

    def test_获取事件循环(self):
        """获取事件循环应返回有效的事件循环"""
        loop = _stdlib_获取事件循环()
        self.assertIsNotNone(loop)
        self.assertTrue(hasattr(loop, "run_until_complete"))

    def test_运行协程(self):
        """运行应能执行协程并返回结果"""
        async def coro():
            return 42

        result = _stdlib_运行(coro())
        self.assertEqual(result, 42)

    def test_运行在事件循环中(self):
        """在已有事件循环中运行应使用线程池"""
        async def test():
            async def inner():
                return 99

            result = _stdlib_运行(inner())
            return result

        result = asyncio.run(test())
        self.assertEqual(result, 99)


class TestTaskManagement(unittest.TestCase):
    """测试任务管理"""

    def test_创建任务(self):
        """创建任务应返回 Task 对象"""
        async def test():
            async def coro():
                await asyncio.sleep(0.01)
                return "完成"

            task = _stdlib_创建任务(coro())
            self.assertIsInstance(task, asyncio.Task)
            result = await task
            self.assertEqual(result, "完成")

        asyncio.run(test())

    def test_当前任务(self):
        """当前任务应返回正在执行的 Task"""
        async def test():
            task = _stdlib_当前任务()
            self.assertIsInstance(task, asyncio.Task)

        asyncio.run(test())

    def test_全部任务(self):
        """全部任务应返回任务列表"""
        async def test():
            tasks = _stdlib_全部任务()
            self.assertIsInstance(tasks, list)
            self.assertGreater(len(tasks), 0)

        asyncio.run(test())


class TestAsyncSleep(unittest.TestCase):
    """测试异步睡眠"""

    def test_睡眠(self):
        """睡眠应返回协程"""
        coro = _stdlib_睡眠(0.01)
        self.assertTrue(asyncio.iscoroutine(coro))
        asyncio.run(coro)

    def test_睡眠时间准确(self):
        """睡眠时间应大致准确"""
        import time

        async def test():
            start = time.perf_counter()
            await _stdlib_睡眠(0.1)
            elapsed = time.perf_counter() - start
            self.assertGreaterEqual(elapsed, 0.09)
            self.assertLess(elapsed, 0.2)

        asyncio.run(test())


class TestAsyncQueue(unittest.TestCase):
    """测试异步队列"""

    def test_创建队列(self):
        """创建队列应返回 DaoAsyncQueue"""
        queue = _stdlib_创建队列(10)
        self.assertIsInstance(queue, DaoAsyncQueue)
        self.assertEqual(queue.最大容量, 10)

    def test_放入取出(self):
        """放入和取出应正常工作"""
        async def test():
            queue = DaoAsyncQueue()
            await queue.放入("你好")
            await queue.放入("世界")
            self.assertEqual(await queue.取出(), "你好")
            self.assertEqual(await queue.取出(), "世界")

        asyncio.run(test())

    def test_立即操作(self):
        """立即放入和取出应正常工作"""
        queue = DaoAsyncQueue(5)
        queue.放入立即(1)
        queue.放入立即(2)
        self.assertEqual(queue.取出立即(), 1)
        self.assertEqual(queue.取出立即(), 2)

    def test_队列属性(self):
        """队列属性应正确反映状态"""
        queue = DaoAsyncQueue(2)
        self.assertTrue(queue.为空)
        self.assertFalse(queue.为满)

        queue.放入立即(1)
        self.assertFalse(queue.为空)

        queue.放入立即(2)
        self.assertTrue(queue.为满)

    def test_等待完成(self):
        """等待完成应阻塞直到所有项目被处理"""
        async def test():
            queue = DaoAsyncQueue()
            await queue.放入(1)
            await queue.放入(2)

            value = await queue.取出()
            queue.任务完成()
            value = await queue.取出()
            queue.任务完成()

            await queue.等待完成()

        asyncio.run(test())


class TestAsyncLock(unittest.TestCase):
    """测试异步锁"""

    def test_创建锁(self):
        """创建锁应返回 DaoAsyncLock"""
        lock = _stdlib_创建锁()
        self.assertIsInstance(lock, DaoAsyncLock)
        self.assertFalse(lock.已锁定)

    def test_获取释放(self):
        """获取和释放锁应正常工作"""
        async def test():
            lock = DaoAsyncLock()
            await lock.获取()
            self.assertTrue(lock.已锁定)
            lock.释放()
            self.assertFalse(lock.已锁定)

        asyncio.run(test())

    def test_互斥访问(self):
        """锁应保证互斥访问"""
        async def test():
            lock = DaoAsyncLock()
            counter = [0]

            async def increment():
                for _ in range(100):
                    await lock.获取()
                    val = counter[0]
                    await asyncio.sleep(0)
                    counter[0] = val + 1
                    lock.释放()

            await asyncio.gather(increment(), increment())
            self.assertEqual(counter[0], 200)

        asyncio.run(test())


class TestAsyncSemaphore(unittest.TestCase):
    """测试异步信号量"""

    def test_创建信号量(self):
        """创建信号量应返回 DaoAsyncSemaphore"""
        sem = _stdlib_创建信号量(3)
        self.assertIsInstance(sem, DaoAsyncSemaphore)
        self.assertEqual(sem.初始值, 3)

    def test_获取释放(self):
        """获取和释放信号量应正常工作"""
        async def test():
            sem = DaoAsyncSemaphore(2)
            await sem.获取()
            self.assertEqual(sem.当前值, 1)
            await sem.获取()
            self.assertEqual(sem.当前值, 0)
            sem.释放()
            self.assertEqual(sem.当前值, 1)

        asyncio.run(test())

    def test_限制并发(self):
        """信号量应限制并发数量"""
        async def test():
            sem = DaoAsyncSemaphore(2)
            concurrent = [0]
            max_concurrent = [0]

            async def worker():
                await sem.获取()
                concurrent[0] += 1
                max_concurrent[0] = max(max_concurrent[0], concurrent[0])
                await asyncio.sleep(0.05)
                concurrent[0] -= 1
                sem.释放()

            await asyncio.gather(worker(), worker(), worker(), worker())
            self.assertLessEqual(max_concurrent[0], 2)

        asyncio.run(test())


class TestAsyncCondition(unittest.TestCase):
    """测试异步条件变量"""

    def test_创建条件(self):
        """创建条件应返回 DaoAsyncCondition"""
        cond = _stdlib_创建条件()
        self.assertIsInstance(cond, DaoAsyncCondition)

    def test_等待通知(self):
        """等待和通知应正常工作"""
        async def test():
            cond = DaoAsyncCondition()
            result = []

            async def waiter():
                async with cond:
                    await cond.等待()
                    result.append("已通知")

            async def notifier():
                await asyncio.sleep(0.05)
                async with cond:
                    cond.通知()

            await asyncio.gather(waiter(), notifier())
            self.assertEqual(result, ["已通知"])

        asyncio.run(test())


class TestAsyncEvent(unittest.TestCase):
    """测试异步事件"""

    def test_创建事件(self):
        """创建事件应返回 DaoAsyncEvent"""
        event = _stdlib_创建事件()
        self.assertIsInstance(event, DaoAsyncEvent)
        self.assertFalse(event.已设置)

    def test_设置等待(self):
        """设置和等待事件应正常工作"""
        async def test():
            event = DaoAsyncEvent()
            result = []

            async def waiter():
                await event.等待()
                result.append("事件触发")

            async def setter():
                await asyncio.sleep(0.05)
                event.设置()

            await asyncio.gather(waiter(), setter())
            self.assertTrue(event.已设置)
            self.assertEqual(result, ["事件触发"])

        asyncio.run(test())

    def test_清除事件(self):
        """清除事件应重置状态"""
        event = DaoAsyncEvent()
        event.设置()
        self.assertTrue(event.已设置)
        event.清除()
        self.assertFalse(event.已设置)


class TestAsyncBarrier(unittest.TestCase):
    """测试异步屏障"""

    def test_创建屏障(self):
        """创建屏障应返回 DaoAsyncBarrier"""
        barrier = _stdlib_创建屏障(3)
        self.assertIsInstance(barrier, DaoAsyncBarrier)
        self.assertEqual(barrier.参与者数, 3)

    def test_屏障同步(self):
        """屏障应同步多个协程"""
        async def test():
            barrier = DaoAsyncBarrier(3)
            order = []

            async def worker(name):
                order.append(f"{name}-到达")
                await barrier.等待()
                order.append(f"{name}-通过")

            await asyncio.gather(
                worker("A"), worker("B"), worker("C")
            )

            # 所有"到达"应在所有"通过"之前
            到达索引 = [i for i, x in enumerate(order) if "到达" in x]
            通过索引 = [i for i, x in enumerate(order) if "通过" in x]
            self.assertTrue(max(到达索引) < min(通过索引))

        asyncio.run(test())


class TestUtilityFunctions(unittest.TestCase):
    """测试工具函数"""

    def test_是否协程(self):
        """是否协程应正确判断"""
        async def coro():
            pass

        self.assertTrue(_stdlib_是否协程(coro()))
        self.assertFalse(_stdlib_是否协程(42))
        self.assertFalse(_stdlib_是否协程("hello"))

    def test_是否协程函数(self):
        """是否协程函数应正确判断"""
        async def coro():
            pass

        def sync_func():
            pass

        self.assertTrue(_stdlib_是否协程函数(coro))
        self.assertFalse(_stdlib_是否协程函数(sync_func))

    def test_是否为Task(self):
        """是否为Task应正确判断"""
        async def test():
            task = asyncio.create_task(asyncio.sleep(0))
            self.assertTrue(_stdlib_是否为Task(task))
            self.assertFalse(_stdlib_是否为Task(42))

        asyncio.run(test())

    def test_在线程中执行(self):
        """在线程中执行应返回协程"""
        def sync_func(x):
            return x * 2

        coro = _stdlib_在线程中执行(sync_func, 21)
        self.assertTrue(asyncio.iscoroutine(coro))

        result = asyncio.run(coro)
        self.assertEqual(result, 42)


class TestAsyncFileOperations(unittest.TestCase):
    """测试异步文件操作"""

    def test_异步写入和读取(self):
        """异步写入和读取文件应正常工作"""
        import tempfile
        import os

        async def test():
            with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
                path = f.name

            try:
                # 写入
                await _stdlib_异步写入文件(path, "你好，道语言！")

                # 读取
                content = await _stdlib_异步读取文件(path)
                self.assertEqual(content, "你好，道语言！")
            finally:
                os.unlink(path)

        asyncio.run(test())


class TestAsyncSubprocess(unittest.TestCase):
    """测试异步子进程"""

    def test_创建子进程(self):
        """创建子进程应返回协程"""
        coro = _stdlib_创建子进程("echo hello")
        self.assertTrue(asyncio.iscoroutine(coro))

    def test_执行简单命令(self):
        """执行简单命令应返回正确结果"""
        async def test():
            proc = await _stdlib_创建子进程("echo hello")
            stdout, stderr = await proc.通信()
            self.assertIn("hello", stdout)
            self.assertIsInstance(proc.退出码, int)

        asyncio.run(test())


class TestAsyncNetwork(unittest.TestCase):
    """测试异步网络"""

    def test_打开连接返回协程(self):
        """打开连接应返回协程"""
        coro = _stdlib_打开连接("example.com", 80)
        self.assertTrue(asyncio.iscoroutine(coro))


if __name__ == "__main__":
    unittest.main(verbosity=2)
