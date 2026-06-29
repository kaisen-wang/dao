import datetime
import time as _time

from ..builtins.callables import BuiltinFunction
from ..environment import Environment
from ..errors import 运行时错误

_FORMAT_MAP = {
    "YYYY": "%Y",
    "MM": "%m",
    "DD": "%d",
    "HH": "%H",
    "mm": "%M",
    "ss": "%S",
}


def _dao_format_to_python(fmt: str) -> str:
    for dao_fmt, py_fmt in _FORMAT_MAP.items():
        fmt = fmt.replace(dao_fmt, py_fmt)
    return fmt


class DaoDateTime:
    def __init__(self, dt: datetime.datetime = None):
        self._dt = dt or datetime.datetime.now()

    @property
    def 年份(self):
        return self._dt.year

    @property
    def 月份(self):
        return self._dt.month

    @property
    def 日(self):
        return self._dt.day

    @property
    def 小时(self):
        return self._dt.hour

    @property
    def 分钟(self):
        return self._dt.minute

    @property
    def 秒(self):
        return self._dt.second

    @property
    def 微秒(self):
        return self._dt.microsecond

    def __sub__(self, other):
        if isinstance(other, DaoDateTime):
            delta = self._dt - other._dt
            return DaoTimeDelta(delta)
        return NotImplemented

    def __repr__(self):
        return f"<时间 {self._dt.strftime('%Y-%m-%d %H:%M:%S')}>"


class DaoTimeDelta:
    def __init__(self, td: datetime.timedelta = None):
        self._td = td or datetime.timedelta()

    @property
    def 总秒数(self):
        return self._td.total_seconds()

    @property
    def 天数(self):
        return self._td.days

    def __repr__(self):
        return f"<时间差 {self._td}>"


class DaoTimer:
    def __init__(self):
        self._start = None
        self._end = None

    def 开始(self):
        self._start = _time.perf_counter()
        self._end = None

    def 停止(self):
        if self._start is None:
            raise 运行时错误("计时器尚未开始")
        self._end = _time.perf_counter()
        return (self._end - self._start) * 1000


def _stdlib_现在():
    return DaoDateTime()


def _stdlib_解析(文本, 格式):
    if not isinstance(文本, str):
        raise 运行时错误("解析时间需要文本类型参数")
    py_fmt = _dao_format_to_python(格式)
    try:
        dt = datetime.datetime.strptime(文本, py_fmt)
        return DaoDateTime(dt)
    except ValueError:
        raise 运行时错误(f"无法解析时间: '{文本}'，格式: '{格式}'")


def _stdlib_格式化(时间, 格式):
    if not isinstance(时间, DaoDateTime):
        raise 运行时错误("格式化需要时间类型参数")
    py_fmt = _dao_format_to_python(格式)
    return 时间._dt.strftime(py_fmt)


def _stdlib_计时器():
    return DaoTimer()


def _stdlib_睡眠(秒数):
    _time.sleep(秒数)


def create_module_env(interpreter=None) -> Environment:
    env = Environment()
    env.define("现在", BuiltinFunction("现在", _stdlib_现在, 0))
    env.define("解析", BuiltinFunction("解析", _stdlib_解析, 2))
    env.define("格式化", BuiltinFunction("格式化", _stdlib_格式化, 2))
    env.define("计时器", BuiltinFunction("计时器", _stdlib_计时器, 0))
    env.define("睡眠", BuiltinFunction("睡眠", _stdlib_睡眠, 1))
    env.exports = list(env.values.keys())
    return env