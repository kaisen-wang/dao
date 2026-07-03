"""
同步原语模块
============

为道语言提供同步原语：
- 互斥锁（Mutex）
- 可重入锁（RLock）
- 信号量（Semaphore）
- 等待组（WaitGroup）
- 屏障（Barrier）
- 条件变量（Condition）
- 单次执行（Once）
- 原子整数（AtomicInt）
- 原子布尔（AtomicBool）
"""

import threading
from threading import Condition as _Condition
from threading import Lock, RLock as _RLock
from threading import Semaphore as _Semaphore


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


class RLock:
    """可重入锁

    同一线程/协程可以多次获取同一把锁，需要相同次数的释放。
    """

    def __init__(self):
        self._lock = _RLock()

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


class Semaphore:
    """信号量

    限制并发访问数量。内部计数器控制同时可以获取信号量的线程数。
    """

    def __init__(self, value=1):
        self._semaphore = _Semaphore(value)
        self._initial_value = value

    def acquire(self):
        """获取信号量（计数器减1，为0时阻塞）"""
        self._semaphore.acquire()

    def release(self):
        """释放信号量（计数器加1）"""
        self._semaphore.release()

    def __enter__(self):
        """上下文管理器入口"""
        self.acquire()

    def __exit__(self, exc_type, exc_val, exc_tb):
        """上下文管理器出口"""
        self.release()

    @property
    def value(self):
        """当前信号量值（近似值）"""
        return self._semaphore._value


class WaitGroup:
    """等待组

    类似 Go 语言的 sync.WaitGroup，用于等待一组协程/线程完成。
    - add(delta): 增加计数器
    - done(): 减少计数器（等价于 add(-1)）
    - wait(): 阻塞直到计数器归零
    """

    def __init__(self):
        self._count = 0
        self._lock = Lock()
        self._condition = _Condition(self._lock)

    def add(self, delta=1):
        """增加计数器"""
        with self._lock:
            self._count += delta
            if self._count < 0:
                raise ValueError("WaitGroup 计数器不能为负数")
            if self._count == 0:
                self._condition.notify_all()

    def done(self):
        """完成一个任务（计数器减1）"""
        self.add(-1)

    def wait(self):
        """等待计数器归零"""
        with self._lock:
            while self._count > 0:
                self._condition.wait()

    @property
    def count(self):
        """当前计数器值"""
        with self._lock:
            return self._count


class Barrier:
    """屏障

    让多个线程/协程在某个点同步等待，直到所有参与者都到达后才继续执行。
    """

    def __init__(self, parties):
        self._barrier = threading.Barrier(parties)
        self._parties = parties

    def wait(self):
        """等待所有参与者到达屏障点"""
        return self._barrier.wait()

    def abort(self):
        """中止屏障，让所有等待的线程抛出 BrokenBarrierError"""
        self._barrier.abort()

    @property
    def parties(self):
        """参与者总数"""
        return self._parties

    @property
    def n_waiting(self):
        """当前等待的线程数"""
        return self._barrier.n_waiting

    @property
    def broken(self):
        """屏障是否已损坏"""
        return self._barrier.broken


class Condition:
    """条件变量

    实现等待/通知模式。线程可以等待某个条件成立，其他线程在条件成立时通知。
    """

    def __init__(self, lock=None):
        if lock is None:
            lock = Lock()
        self._condition = _Condition(lock)

    def acquire(self):
        """获取底层锁"""
        self._condition.acquire()

    def release(self):
        """释放底层锁"""
        self._condition.release()

    def wait(self, timeout=None):
        """等待通知"""
        return self._condition.wait(timeout=timeout)

    def notify(self, n=1):
        """通知 n 个等待的线程"""
        self._condition.notify(n=n)

    def notify_all(self):
        """通知所有等待的线程"""
        self._condition.notify_all()

    def wait_for(self, predicate, timeout=None):
        """等待条件成立"""
        return self._condition.wait_for(predicate, timeout=timeout)

    def __enter__(self):
        """上下文管理器入口"""
        self.acquire()

    def __exit__(self, exc_type, exc_val, exc_tb):
        """上下文管理器出口"""
        self.release()


class Once:
    """单次执行

    确保某个初始化函数只被执行一次，即使多个线程同时调用。
    """

    def __init__(self):
        self._done = False
        self._lock = Lock()

    def do(self, func):
        """执行函数（仅第一次调用时真正执行）

        Args:
            func: 要执行的函数

        Returns:
            函数的返回值，如果已经执行过则返回 None
        """
        if self._done:
            return None

        with self._lock:
            if self._done:
                return None
            result = func()
            self._done = True
            return result

    @property
    def done(self):
        """是否已经执行过"""
        return self._done

    def reset(self):
        """重置状态，允许再次执行"""
        with self._lock:
            self._done = False


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
