"""定时调度原语
============

为常驻 Agent 提供基于后台线程的定时能力：

- 延迟执行(毫秒, 回调) -> int : 一次性定时，返回调度 ID
- 周期执行(毫秒, 回调) -> int : 周期重复，返回调度 ID
- 取消调度(调度ID) -> bool     : 取消成功返回 True，否则 False
- 取消全部() -> None           : 取消所有待触发 / 运行中的任务
- 等待全部() -> None           : 阻塞直到所有一次性任务完成

实现只依赖标准库 threading。回调若为道语言函数（DaoCallable），
通过 Interpreter.call_function 调用；普通 Python callable 直接调用。
"""

import sys
import threading

from ..builtins.callables import DaoCallable, InterpreterBuiltin
from ..environment import Environment
from ..errors import 类型错误, 运行时错误


class _调度任务:
    """单个调度任务的内部状态。"""

    def __init__(self, ident, 毫秒, 回调, 解释器, 周期):
        self.ident = ident
        self.毫秒 = 毫秒
        self.回调 = 回调
        self.解释器 = 解释器
        self.周期 = 周期
        self.timer = None
        self.取消标志 = False
        self.已结束 = False


class _调度器:
    """全局调度器：用 RLock 保护任务字典、ID 计数器与活跃计数。"""

    def __init__(self):
        self._锁 = threading.RLock()
        self._条件 = threading.Condition(self._锁)
        self._任务: dict[int, _调度任务] = {}
        self._下一个ID = 1
        self._活跃 = 0

    def _分配ID(self):
        with self._锁:
            ident = self._下一个ID
            self._下一个ID += 1
            return ident

    def 调度(self, 毫秒, 回调, 解释器, 周期):
        ident = self._分配ID()
        任务 = _调度任务(ident, 毫秒, 回调, 解释器, 周期)
        with self._锁:
            self._任务[ident] = 任务
            self._活跃 += 1
        self._装载(任务)
        return ident

    def _装载(self, 任务):
        """装载一个 threading.Timer；周期任务在回调结束后再次装载。"""
        timer = threading.Timer(任务.毫秒 / 1000, self._触发, args=(任务,))
        timer.daemon = True
        with self._锁:
            if 任务.ident not in self._任务 or 任务.取消标志:
                return
            任务.timer = timer
        timer.start()

    def _触发(self, 任务):
        try:
            self._调用回调(任务)
        except Exception as e:  # noqa: BLE001 - 后台线程不能因回调异常而静默死掉
            错误 = 运行时错误(f"定时调度回调执行异常: {e}")
            print(str(错误), file=sys.stderr, flush=True)
        finally:
            with self._锁:
                if 任务.周期 and not 任务.取消标志 and 任务.ident in self._任务:
                    self._装载(任务)
                else:
                    # 一次性任务结束后从字典移除，避免无限增长
                    self._任务.pop(任务.ident, None)
                    self._结束(任务)

    @staticmethod
    def _调用回调(任务):
        回调 = 任务.回调
        if isinstance(回调, DaoCallable):
            if 任务.解释器 is None:
                raise 运行时错误("定时调度回调需要解释器上下文")
            任务.解释器.call_function(回调, [])
        else:
            回调()

    def _结束(self, 任务):
        """幂等地把任务从活跃计数中移除并唤醒等待者。"""
        with self._锁:
            if 任务.已结束:
                return
            任务.已结束 = True
            self._活跃 -= 1
            self._条件.notify_all()

    def 取消(self, ident):
        with self._锁:
            任务 = self._任务.pop(ident, None)
            if 任务 is None:
                return False
            任务.取消标志 = True
            if 任务.timer is not None:
                任务.timer.cancel()
            self._结束(任务)
            return True

    def 取消全部(self):
        with self._锁:
            任务列表 = list(self._任务.values())
            self._任务.clear()
            for 任务 in 任务列表:
                任务.取消标志 = True
                if 任务.timer is not None:
                    任务.timer.cancel()
                self._结束(任务)

    def 等待全部(self):
        with self._条件:
            while self._活跃 > 0:
                self._条件.wait(0.05)


_全局调度器 = _调度器()


def _检查毫秒(毫秒):
    if isinstance(毫秒, bool) or not isinstance(毫秒, int) or 毫秒 < 0:
        raise 类型错误("毫秒必须是非负整数")


def _检查回调(回调):
    if not (isinstance(回调, DaoCallable) or callable(回调)):
        raise 类型错误("回调必须是可调用的函数")


# 模块级中文函数：既供 Python 测试直接调用，也作为道语言内置的底层实现。
# interpreter 为可选参数：普通 Python callable 回调无需解释器；道语言函数
# 作为回调时必须传入解释器，以便走 call_function 路径。


def 延迟执行(毫秒, 回调, interpreter=None):
    """一次性定时执行回调，返回正整数调度 ID。"""
    _检查毫秒(毫秒)
    _检查回调(回调)
    return _全局调度器.调度(毫秒, 回调, interpreter, False)


def 周期执行(毫秒, 回调, interpreter=None):
    """周期重复执行回调，返回正整数调度 ID。"""
    _检查毫秒(毫秒)
    _检查回调(回调)
    return _全局调度器.调度(毫秒, 回调, interpreter, True)


def 取消调度(调度ID):
    """存在并成功取消返回 True，否则 False。"""
    return _全局调度器.取消(调度ID)


def 取消全部():
    """取消所有任务。"""
    _全局调度器.取消全部()


def 等待全部():
    """阻塞直到所有一次性任务完成；周期任务须先取消。"""
    _全局调度器.等待全部()


# InterpreterBuiltin 的 func 调用约定是 func(interpreter, *args)
# （参照 network.py）。这 5 个模块级适配器把解释器转发给上面的中文函数；
# 每个适配器都带中文 docstring，供 docgen 提取为函数描述。
# 工厂每次复用同一批模块级函数对象，保证元数据稳定（docgen 幂等约束）。


def _延迟执行实现(interpreter, 毫秒, 回调):
    """一次性定时执行道语言回调，到达指定毫秒数后触发一次，返回调度 ID。"""
    return 延迟执行(毫秒, 回调, interpreter)


def _周期执行实现(interpreter, 毫秒, 回调):
    """按指定毫秒数周期重复执行道语言回调，直到该调度被取消为止。"""
    return 周期执行(毫秒, 回调, interpreter)


def _取消调度实现(interpreter, 调度ID):
    """取消指定调度 ID 对应的任务，成功返回真，不存在则返回假。"""
    return 取消调度(调度ID)


def _取消全部实现(interpreter):
    """取消当前所有待触发或运行中的定时调度任务。"""
    取消全部()


def _等待全部实现(interpreter):
    """阻塞等待，直到所有一次性调度任务执行完毕。"""
    等待全部()


def create_module_env(interpreter=None) -> Environment:
    """创建调度模块的导出环境。"""
    env = Environment()

    导出表 = (
        ("延迟执行", _延迟执行实现, 2),
        ("周期执行", _周期执行实现, 2),
        ("取消调度", _取消调度实现, 1),
        ("取消全部", _取消全部实现, 0),
        ("等待全部", _等待全部实现, 0),
    )
    for 名字, func, 参数个数 in 导出表:
        内置 = InterpreterBuiltin(名字, func, 参数个数)
        if interpreter is not None:
            内置.set_interpreter(interpreter)
        env.define(名字, 内置)
    env.exports = list(env.values.keys())
    return env
