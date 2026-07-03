"""
异步IO标准库
============

为道语言提供 asyncio 标准库，以简体中文 API 封装 Python asyncio 模块。

使用方式：
    导入 异步IO

    异步 函数 主程序()
        等待 异步IO.睡眠(1)
        任务 = 异步IO.创建任务(某协程())
        结果 = 等待 异步IO.等待(任务)

提供功能：
- 事件循环管理
- 协程/任务创建与管理
- 异步睡眠与等待
- 异步超时控制
- 异步队列
- 异步锁/信号量/条件/事件
- 异步子进程
- 异步流（StreamReader/StreamWriter）
- 异步上下文管理
"""

import asyncio as _asyncio
import concurrent.futures
import time

from ..builtins.callables import BuiltinFunction
from ..environment import Environment
from ..errors import 运行时错误, 类型错误


# ========================
# 事件循环管理
# ========================

def _stdlib_获取事件循环():
    """获取当前事件循环，不存在则创建"""
    try:
        loop = _asyncio.get_running_loop()
        return loop
    except RuntimeError:
        return _asyncio.new_event_loop()


def _stdlib_运行(协程):
    """运行协程并返回结果

    这是 asyncio.run() 的中文封装。
    如果已在事件循环中，使用线程池执行。
    """
    if _asyncio.iscoroutine(协程):
        try:
            loop = _asyncio.get_running_loop()
            # 已在事件循环中，使用线程池
            with concurrent.futures.ThreadPoolExecutor() as pool:
                future = pool.submit(_asyncio.run, 协程)
                return future.result(timeout=300)
        except RuntimeError:
            return _asyncio.run(协程)
    elif hasattr(协程, "is_async") and 协程.is_async:
        # 道语言异步函数
        try:
            loop = _asyncio.get_running_loop()
            with concurrent.futures.ThreadPoolExecutor() as pool:
                future = pool.submit(_asyncio.run, 协程.call([], {}))
                return future.result(timeout=300)
        except RuntimeError:
            return _asyncio.run(协程.call([], {}))
    else:
        raise 类型错误("运行期望接收协程或异步函数")


def _stdlib_获取运行中循环():
    """获取当前正在运行的事件循环"""
    try:
        return _asyncio.get_running_loop()
    except RuntimeError:
        raise 运行时错误("没有正在运行的事件循环")


# ========================
# 协程/任务创建与管理
# ========================

def _stdlib_创建任务(协程):
    """将协程包装为 Task 并调度执行

    必须在事件循环内调用。
    """
    if _asyncio.iscoroutine(协程):
        return _asyncio.create_task(协程)
    elif hasattr(协程, "is_async") and 协程.is_async:
        return _asyncio.create_task(协程.call([], {}))
    else:
        raise 类型错误("创建任务期望接收协程或异步函数")


def _stdlib_当前任务():
    """获取当前正在执行的 Task"""
    try:
        return _asyncio.current_task()
    except RuntimeError:
        return None


def _stdlib_全部任务():
    """获取事件循环中所有未完成的 Task"""
    return list(_asyncio.all_tasks())


def _stdlib_等待(可等待对象, 超时=None):
    """等待可等待对象完成

    支持 Task、协程、Future。
    返回 (结果, 是否超时) 元组。
    """
    async def _do_wait():
        if 超时 is not None:
            try:
                result = await _asyncio.wait_for(
                    _asyncio.ensure_future(可等待对象),
                    timeout=超时,
                )
                return (result, False)
            except _asyncio.TimeoutError:
                return (None, True)
        else:
            result = await 可等待对象
            return (result, False)

    return _do_wait()


def _stdlib_等待全部(任务列表, 超时=None):
    """等待所有任务完成

    返回结果列表，超时则抛出异常。
    """
    async def _do():
        tasks = []
        for t in 任务列表:
            if _asyncio.iscoroutine(t):
                tasks.append(_asyncio.create_task(t))
            elif isinstance(t, _asyncio.Task):
                tasks.append(t)
            else:
                tasks.append(_asyncio.create_task(_asyncio.coroutine(lambda: t)()))

        if 超时 is not None:
            results = await _asyncio.wait_for(
                _asyncio.gather(*tasks, return_exceptions=True),
                timeout=超时,
            )
        else:
            results = await _asyncio.gather(*tasks, return_exceptions=True)

        return [
            r if not isinstance(r, Exception) else {"错误": str(r)}
            for r in results
        ]

    return _do()


def _stdlib_等待竞速(任务列表):
    """竞速等待，返回最先完成的结果"""
    async def _do():
        tasks = []
        for t in 任务列表:
            if _asyncio.iscoroutine(t):
                tasks.append(_asyncio.create_task(t))
            elif isinstance(t, _asyncio.Task):
                tasks.append(t)

        if not tasks:
            raise 运行时错误("竞速等待需要至少一个任务")

        done, pending = await _asyncio.wait(
            tasks, return_when=_asyncio.FIRST_COMPLETED
        )

        # 取消未完成的任务
        for task in pending:
            task.cancel()
            try:
                await task
            except _asyncio.CancelledError:
                pass

        if done:
            return next(iter(done)).result()
        return None

    return _do()


def _stdlib_取消任务(任务):
    """取消一个任务"""
    if isinstance(任务, _asyncio.Task):
        任务.cancel()
    else:
        raise 类型错误("取消任务期望接收 Task 对象")


# ========================
# 异步睡眠与等待
# ========================

def _stdlib_睡眠(秒数):
    """异步睡眠指定秒数

    返回协程对象，需要用 等待 调用。
    """
    return _asyncio.sleep(秒数)


# ========================
# 异步超时控制
# ========================

def _stdlib_超时等待(协程, 秒数):
    """带超时的等待协程

    超时抛出 TimeoutError。
    """
    async def _do():
        return await _asyncio.wait_for(
            _asyncio.ensure_future(协程),
            timeout=秒数,
        )
    return _do()


def _stdlib_超时上下文(秒数):
    """创建异步超时上下文

    用法：
        异步 函数 示例()
            异步 与 异步IO.超时上下文(5) 为 限时
                等待 某操作()
    """
    return _asyncio.timeout(秒数)


# ========================
# 异步队列
# ========================

class DaoAsyncQueue:
    """道语言异步队列

    封装 asyncio.Queue，提供中文 API。
    """

    def __init__(self, 最大容量=0):
        self._queue = _asyncio.Queue(maxsize=最大容量)
        self.最大容量 = 最大容量

    async def 放入(self, 项目):
        """放入项目（缓冲区满时阻塞）"""
        await self._queue.put(项目)

    async def 取出(self):
        """取出项目（缓冲区空时阻塞）"""
        return await self._queue.get()

    def 放入立即(self, 项目):
        """立即放入项目（缓冲区满时抛出异常）"""
        self._queue.put_nowait(项目)

    def 取出立即(self):
        """立即取出项目（缓冲区空时抛出异常）"""
        return self._queue.get_nowait()

    async def 等待完成(self):
        """等待队列中所有项目被处理"""
        await self._queue.join()

    def 任务完成(self):
        """标记一个项目处理完成"""
        self._queue.task_done()

    @property
    def 长度(self):
        """队列中项目数"""
        return self._queue.qsize()

    @property
    def 为空(self):
        """队列是否为空"""
        return self._queue.empty()

    @property
    def 为满(self):
        """队列是否已满"""
        return self._queue.full()

    def __repr__(self):
        return f"<异步队列 长度={self.长度} 最大容量={self.最大容量}>"


def _stdlib_创建队列(最大容量=0):
    """创建异步队列"""
    return DaoAsyncQueue(最大容量)


# ========================
# 异步锁
# ========================

class DaoAsyncLock:
    """道语言异步锁

    封装 asyncio.Lock，提供中文 API。
    """

    def __init__(self):
        self._lock = _asyncio.Lock()

    async def 获取(self):
        """获取锁"""
        await self._lock.acquire()

    def 释放(self):
        """释放锁"""
        self._lock.release()

    @property
    def 已锁定(self):
        """是否已锁定"""
        return self._lock.locked()

    async def __aenter__(self):
        await self.获取()

    async def __aexit__(self, *args):
        self.释放()

    def __repr__(self):
        return f"<异步锁 已锁定={self.已锁定}>"


def _stdlib_创建锁():
    """创建异步锁"""
    return DaoAsyncLock()


# ========================
# 异步信号量
# ========================

class DaoAsyncSemaphore:
    """道语言异步信号量

    封装 asyncio.Semaphore，提供中文 API。
    """

    def __init__(self, 值=1):
        self._sem = _asyncio.Semaphore(值)
        self.初始值 = 值

    async def 获取(self):
        """获取信号量"""
        await self._sem.acquire()

    def 释放(self):
        """释放信号量"""
        self._sem.release()

    @property
    def 当前值(self):
        """当前信号量值"""
        return self._sem._value

    async def __aenter__(self):
        await self.获取()

    async def __aexit__(self, *args):
        self.释放()

    def __repr__(self):
        return f"<异步信号量 当前值={self.当前值}>"


def _stdlib_创建信号量(值=1):
    """创建异步信号量"""
    return DaoAsyncSemaphore(值)


# ========================
# 异步条件变量
# ========================

class DaoAsyncCondition:
    """道语言异步条件变量

    封装 asyncio.Condition，提供中文 API。
    """

    def __init__(self, 锁=None):
        if 锁 is not None:
            self._cond = _asyncio.Condition(锁._lock if isinstance(锁, DaoAsyncLock) else 锁)
        else:
            self._cond = _asyncio.Condition()

    async def 获取(self):
        """获取底层锁"""
        await self._cond.acquire()

    def 释放(self):
        """释放底层锁"""
        self._cond.release()

    async def 等待(self):
        """等待通知"""
        await self._cond.wait()

    async def 等待条件(self, 谓词):
        """等待条件成立"""
        await self._cond.wait_for(谓词)

    def 通知(self, 数量=1):
        """通知指定数量的等待者"""
        self._cond.notify(n=数量)

    def 通知全部(self):
        """通知所有等待者"""
        self._cond.notify_all()

    async def __aenter__(self):
        await self.获取()

    async def __aexit__(self, *args):
        self.释放()

    def __repr__(self):
        return "<异步条件变量>"


def _stdlib_创建条件(锁=None):
    """创建异步条件变量"""
    return DaoAsyncCondition(锁)


# ========================
# 异步事件
# ========================

class DaoAsyncEvent:
    """道语言异步事件

    封装 asyncio.Event，提供中文 API。
    """

    def __init__(self):
        self._event = _asyncio.Event()

    def 设置(self):
        """设置事件（通知所有等待者）"""
        self._event.set()

    def 清除(self):
        """清除事件"""
        self._event.clear()

    async def 等待(self):
        """等待事件被设置"""
        await self._event.wait()

    @property
    def 已设置(self):
        """事件是否已设置"""
        return self._event.is_set()

    def __repr__(self):
        return f"<异步事件 已设置={self.已设置}>"


def _stdlib_创建事件():
    """创建异步事件"""
    return DaoAsyncEvent()


# ========================
# 异步屏障
# ========================

class DaoAsyncBarrier:
    """道语言异步屏障

    基于 asyncio.Condition 实现，让多个协程在某个点同步等待。
    """

    def __init__(self, 参与者数):
        self._参与者数 = 参与者数
        self._等待数 = 0
        self._代数 = 0
        self._cond = _asyncio.Condition()

    async def 等待(self):
        """等待所有参与者到达"""
        async with self._cond:
            代 = self._代数
            self._等待数 += 1
            if self._等待数 == self._参与者数:
                self._等待数 = 0
                self._代数 += 1
                self._cond.notify_all()
                return 代
            else:
                while 代 == self._代数:
                    await self._cond.wait()
                return 代

    @property
    def 参与者数(self):
        return self._参与者数

    @property
    def 等待中数(self):
        return self._等待数

    def __repr__(self):
        return f"<异步屏障 参与者={self._参与者数} 等待中={self._等待数}>"


def _stdlib_创建屏障(参与者数):
    """创建异步屏障"""
    return DaoAsyncBarrier(参与者数)


# ========================
# 异步子进程
# ========================

class DaoAsyncProcess:
    """道语言异步子进程

    封装 asyncio.subprocess，提供中文 API。
    """

    def __init__(self, proc):
        self._proc = proc

    async def 等待(self):
        """等待进程结束，返回退出码"""
        return await self._proc.wait()

    @property
    def 退出码(self):
        """进程退出码"""
        return self._proc.returncode

    @property
    def 进程ID(self):
        """进程ID"""
        return self._proc.pid

    def 终止(self):
        """终止进程"""
        self._proc.terminate()

    def 杀死(self):
        """强制杀死进程"""
        self._proc.kill()

    async def 通信(self, 输入=None):
        """与进程通信，返回 (标准输出, 标准错误)"""
        stdout, stderr = await self._proc.communicate(
            input=输入.encode() if isinstance(输入, str) else 输入
        )
        return (
            stdout.decode() if stdout else "",
            stderr.decode() if stderr else "",
        )

    def __repr__(self):
        return f"<异步进程 PID={self.进程ID}>"


def _stdlib_创建子进程(命令, 参数列表=None, 合并输出=False):
    """创建异步子进程

    返回协程对象，需要用 等待 调用。
    """
    async def _do():
        if isinstance(命令, str) and 参数列表 is None:
            # 单个命令字符串
            proc = await _asyncio.create_subprocess_shell(
                命令,
                stdout=_asyncio.subprocess.PIPE,
                stderr=_asyncio.subprocess.PIPE if not 合并输出 else _asyncio.subprocess.STDOUT,
            )
        elif isinstance(命令, str):
            args = [命令] + (参数列表 or [])
            proc = await _asyncio.create_subprocess_exec(
                *args,
                stdout=_asyncio.subprocess.PIPE,
                stderr=_asyncio.subprocess.PIPE if not 合并输出 else _asyncio.subprocess.STDOUT,
            )
        elif isinstance(命令, list):
            proc = await _asyncio.create_subprocess_exec(
                *命令,
                stdout=_asyncio.subprocess.PIPE,
                stderr=_asyncio.subprocess.PIPE if not 合并输出 else _asyncio.subprocess.STDOUT,
            )
        else:
            raise 类型错误("创建子进程期望接收命令字符串或列表")
        return DaoAsyncProcess(proc)

    return _do()


# ========================
# 异步流（网络连接）
# ========================

class DaoStreamReader:
    """道语言异步流读取器"""

    def __init__(self, reader):
        self._reader = reader

    async def 读取(self, 字节数=-1):
        """读取指定字节数"""
        data = await self._reader.read(字节数 if 字节数 > 0 else -1)
        return data

    async def 读取一行(self):
        """读取一行"""
        data = await self._reader.readline()
        return data

    async def 读取全部(self):
        """读取全部内容"""
        data = await self._reader.read()
        return data

    async def 读取至(self, 分隔符=b"\n"):
        """读取直到遇到分隔符"""
        data = await self._reader.readuntil(分隔符)
        return data

    @property
    def 已结束(self):
        """是否已到达末尾"""
        return self._reader.at_eof()

    def __repr__(self):
        return "<异步流读取器>"


class DaoStreamWriter:
    """道语言异步流写入器"""

    def __init__(self, writer):
        self._writer = writer

    def 写入(self, 数据):
        """写入数据"""
        if isinstance(数据, str):
            数据 = 数据.encode("utf-8")
        self._writer.write(数据)

    async def 排空(self):
        """排空写入缓冲区"""
        await self._writer.drain()

    async def 等待关闭(self):
        """等待写入器关闭"""
        self._writer.close()
        await self._writer.wait_closed()

    @property
    def 已关闭(self):
        return self._writer.is_closing()

    def __repr__(self):
        return "<异步流写入器>"


def _stdlib_打开连接(主机, 端口, 超时=None):
    """打开异步网络连接

    返回协程对象，需要用 等待 调用。
    等待后返回 (读取器, 写入器)。
    """
    async def _do():
        reader, writer = await _asyncio.open_connection(
            主机, 端口, limit=2**16
        )
        return (DaoStreamReader(reader), DaoStreamWriter(writer))

    return _do()


def _stdlib_启动服务器(回调, 主机="127.0.0.1", 端口=8888):
    """启动异步TCP服务器

    返回协程对象，需要用 等待 调用。
    """
    async def _do():
        async def handle_client(reader, writer):
            dao_reader = DaoStreamReader(reader)
            dao_writer = DaoStreamWriter(writer)
            if isinstance(回调, BuiltinFunction):
                await 回调.call([dao_reader, dao_writer], {})
            elif _asyncio.iscoroutinefunction(回调):
                await 回调(dao_reader, dao_writer)
            elif callable(回调):
                回调(dao_reader, dao_writer)

        server = await _asyncio.start_server(
            handle_client, 主机, 端口
        )
        return server

    return _do()


# ========================
# 异步文件操作
# ========================

def _stdlib_异步读取文件(路径, 编码="utf-8"):
    """异步读取文件内容

    返回协程对象，需要用 等待 调用。
    """
    async def _do():
        loop = _asyncio.get_running_loop()
        with open(路径, "r", encoding=编码) as f:
            return await loop.run_in_executor(None, f.read)

    return _do()


def _stdlib_异步写入文件(路径, 内容, 编码="utf-8"):
    """异步写入文件内容

    返回协程对象，需要用 等待 调用。
    """
    async def _do():
        loop = _asyncio.get_running_loop()
        with open(路径, "w", encoding=编码) as f:
            if isinstance(内容, str):
                await loop.run_in_executor(None, f.write, 内容)
            else:
                await loop.run_in_executor(None, f.write, str(内容))

    return _do()


# ========================
# 工具函数
# ========================

def _stdlib_是否协程(对象):
    """判断对象是否为协程"""
    return _asyncio.iscoroutine(对象)


def _stdlib_是否协程函数(对象):
    """判断对象是否为协程函数"""
    return _asyncio.iscoroutinefunction(对象)


def _stdlib_是否为Future(对象):
    """判断对象是否为 Future"""
    return isinstance(对象, _asyncio.Future)


def _stdlib_是否为Task(对象):
    """判断对象是否为 Task"""
    return isinstance(对象, _asyncio.Task)


def _stdlib_确保Future(对象):
    """将对象包装为 Future"""
    if _asyncio.iscoroutine(对象):
        return _asyncio.ensure_future(对象)
    elif isinstance(对象, _asyncio.Future):
        return 对象
    else:
        raise 类型错误("确保Future期望接收协程或Future对象")


def _stdlib_在线程中执行(函数, *参数):
    """在线程池中执行同步函数

    返回协程对象，需要用 等待 调用。
    """
    async def _do():
        loop = _asyncio.get_running_loop()
        return await loop.run_in_executor(None, 函数, *参数)

    return _do()


def _stdlib_屏蔽取消(协程):
    """屏蔽取消操作

    返回协程对象，需要用 等待 调用。
    """
    return _asyncio.shield(协程)


def _stdlib_组合等待(*可等待对象):
    """组合多个可等待对象

    返回协程对象，需要用 等待 调用。
    等待后返回结果列表。
    """
    async def _do():
        results = await _asyncio.gather(*可等待对象, return_exceptions=True)
        return [
            r if not isinstance(r, Exception) else {"错误": str(r)}
            for r in results
        ]

    return _do()


# ========================
# 模块环境创建
# ========================

def create_module_env(interpreter=None) -> Environment:
    env = Environment()

    # 事件循环管理
    env.define("获取事件循环", BuiltinFunction("获取事件循环", _stdlib_获取事件循环, 0))
    env.define("运行", BuiltinFunction("运行", _stdlib_运行, 1))
    env.define("获取运行中循环", BuiltinFunction("获取运行中循环", _stdlib_获取运行中循环, 0))

    # 协程/任务管理
    env.define("创建任务", BuiltinFunction("创建任务", _stdlib_创建任务, 1))
    env.define("当前任务", BuiltinFunction("当前任务", _stdlib_当前任务, 0))
    env.define("全部任务", BuiltinFunction("全部任务", _stdlib_全部任务, 0))
    env.define("等待", BuiltinFunction("等待", _stdlib_等待, -1))
    env.define("等待全部", BuiltinFunction("等待全部", _stdlib_等待全部, -1))
    env.define("等待竞速", BuiltinFunction("等待竞速", _stdlib_等待竞速, 1))
    env.define("取消任务", BuiltinFunction("取消任务", _stdlib_取消任务, 1))

    # 异步睡眠
    env.define("睡眠", BuiltinFunction("睡眠", _stdlib_睡眠, 1))

    # 超时控制
    env.define("超时等待", BuiltinFunction("超时等待", _stdlib_超时等待, 2))
    env.define("超时上下文", BuiltinFunction("超时上下文", _stdlib_超时上下文, 1))

    # 异步队列
    env.define("创建队列", BuiltinFunction("创建队列", _stdlib_创建队列, -1))

    # 异步同步原语
    env.define("创建锁", BuiltinFunction("创建锁", _stdlib_创建锁, 0))
    env.define("创建信号量", BuiltinFunction("创建信号量", _stdlib_创建信号量, -1))
    env.define("创建条件", BuiltinFunction("创建条件", _stdlib_创建条件, -1))
    env.define("创建事件", BuiltinFunction("创建事件", _stdlib_创建事件, 0))
    env.define("创建屏障", BuiltinFunction("创建屏障", _stdlib_创建屏障, 1))

    # 异步子进程
    env.define("创建子进程", BuiltinFunction("创建子进程", _stdlib_创建子进程, -1))

    # 异步流
    env.define("打开连接", BuiltinFunction("打开连接", _stdlib_打开连接, 2))
    env.define("启动服务器", BuiltinFunction("启动服务器", _stdlib_启动服务器, -1))

    # 异步文件
    env.define("异步读取文件", BuiltinFunction("异步读取文件", _stdlib_异步读取文件, -1))
    env.define("异步写入文件", BuiltinFunction("异步写入文件", _stdlib_异步写入文件, -1))

    # 工具函数
    env.define("是否协程", BuiltinFunction("是否协程", _stdlib_是否协程, 1))
    env.define("是否协程函数", BuiltinFunction("是否协程函数", _stdlib_是否协程函数, 1))
    env.define("是否为Future", BuiltinFunction("是否为Future", _stdlib_是否为Future, 1))
    env.define("是否为Task", BuiltinFunction("是否为Task", _stdlib_是否为Task, 1))
    env.define("确保Future", BuiltinFunction("确保Future", _stdlib_确保Future, 1))
    env.define("在线程中执行", BuiltinFunction("在线程中执行", _stdlib_在线程中执行, -1))
    env.define("屏蔽取消", BuiltinFunction("屏蔽取消", _stdlib_屏蔽取消, 1))
    env.define("组合等待", BuiltinFunction("组合等待", _stdlib_组合等待, -1))

    # 常量
    env.define("默认超时", 300)

    env.exports = list(env.values.keys())
    return env
