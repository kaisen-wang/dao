import calendar
import datetime
import time as _time

from ..builtins.callables import BuiltinFunction
from ..environment import Environment
from ..errors import 类型错误, 运行时错误

_FORMAT_MAP = {
    "YYYY": "%Y",
    "MM": "%m",
    "DD": "%d",
    "HH": "%H",
    "mm": "%M",
    "ss": "%S",
}


def _dao_format_to_python(fmt: str) -> str:
    """把道语言时间格式占位符转换为 Python strftime 格式。"""
    for dao_fmt, py_fmt in _FORMAT_MAP.items():
        fmt = fmt.replace(dao_fmt, py_fmt)
    return fmt


class DaoDateTime:
    """道语言日期时间对象，封装 datetime.datetime。"""

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
    """道语言时间差对象，封装 datetime.timedelta。"""

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
    """道语言计时器，用于测量毫秒级耗时。"""

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
    """返回表示当前时间的日期时间对象。"""
    return DaoDateTime()


def _stdlib_解析(文本, 格式):
    """按给定格式把文本解析为日期时间对象。"""
    if not isinstance(文本, str):
        raise 运行时错误("解析时间需要文本类型参数")
    py_fmt = _dao_format_to_python(格式)
    try:
        dt = datetime.datetime.strptime(文本, py_fmt)
        return DaoDateTime(dt)
    except ValueError:
        raise 运行时错误(f"无法解析时间: '{文本}'，格式: '{格式}'")


def _stdlib_格式化(时间, 格式):
    """按给定格式把日期时间对象格式化为文本。"""
    if not isinstance(时间, DaoDateTime):
        raise 运行时错误("格式化需要时间类型参数")
    py_fmt = _dao_format_to_python(格式)
    return 时间._dt.strftime(py_fmt)


def _stdlib_计时器():
    """创建一个计时器对象。"""
    return DaoTimer()


def _stdlib_睡眠(秒数):
    """暂停执行指定的秒数。"""
    _time.sleep(秒数)


def _校验数字(值, 名字, 整数=False):
    """校验数值参数类型。"""
    if isinstance(值, bool) or not isinstance(值, (int, float)):
        raise 类型错误(f"{名字}必须是数字")
    if 整数 and not isinstance(值, int):
        raise 类型错误(f"{名字}必须是整数")
    return 值


def _校验时间值(时间):
    """校验时间参数必须是 DaoDateTime 对象。"""
    if not isinstance(时间, DaoDateTime):
        raise 类型错误("时间必须是日期时间对象")
    return 时间


def _时区(小时偏移):
    """按小时偏移构造 datetime.timezone。"""
    _校验数字(小时偏移, "时区小时")
    if not -24 <= 小时偏移 <= 24:
        raise 运行时错误("时区偏移必须在 -24 到 24 小时之间")
    return datetime.timezone(datetime.timedelta(hours=小时偏移))


def _stdlib_时间戳():
    """返回当前的 Unix 时间戳（自 1970-01-01 起的秒数，含小数）。"""
    return _time.time()


def _stdlib_从时间戳(秒, 时区小时=None):
    """把 Unix 时间戳转换为日期时间对象，省略时区时按本地时区解析。"""
    _校验数字(秒, "时间戳")
    if 时区小时 is None:
        本地偏移 = datetime.datetime.now().astimezone().utcoffset()
        时区小时 = 本地偏移.total_seconds() / 3600 if 本地偏移 is not None else 0.0
    时区 = _时区(时区小时)
    if not -86400000000000 <= 秒 <= 86400000000000:
        raise 运行时错误("时间戳超出可表示范围")
    结果 = datetime.datetime.fromtimestamp(秒, tz=时区)
    return DaoDateTime(结果.replace(tzinfo=None))


def _stdlib_到时间戳(时间):
    """把日期时间对象按其本地墙上时间转换为 Unix 时间戳。"""
    _校验时间值(时间)
    return 时间._dt.timestamp()


def _stdlib_日期加减(时间, 天数=0, 秒数=0):
    """对日期时间对象加减指定的天数与秒数，返回新的日期时间对象。"""
    _校验时间值(时间)
    _校验数字(天数, "天数")
    _校验数字(秒数, "秒数")
    return DaoDateTime(时间._dt + datetime.timedelta(days=天数, seconds=秒数))


def _stdlib_创建时间(年, 月, 日, 小时=0, 分钟=0, 秒=0):
    """按年月日时分秒构造一个日期时间对象。"""
    for 名字, 值 in (("年", 年), ("月", 月), ("日", 日), ("小时", 小时), ("分钟", 分钟), ("秒", 秒)):
        _校验数字(值, 名字, 整数=True)
    try:
        return DaoDateTime(datetime.datetime(年, 月, 日, 小时, 分钟, 秒))
    except ValueError as 错误:
        raise 运行时错误(f"无效的日期时间: {错误}")


def _stdlib_日历(年, 月):
    """返回指定年月的日历，按周分组，每月以外的日期用 0 表示。"""
    _校验数字(年, "年", 整数=True)
    _校验数字(月, "月", 整数=True)
    if not 1 <= 月 <= 12:
        raise 运行时错误("月份必须在 1 到 12 之间")
    try:
        return calendar.monthcalendar(年, 月)
    except (ValueError, calendar.IllegalMonthError) as 错误:
        raise 运行时错误(f"无法生成日历: {错误}")


def _stdlib_UTC现在():
    """返回以 UTC 墙上时间表示的当前日期时间对象。"""
    return DaoDateTime(datetime.datetime.now(datetime.timezone.utc).replace(tzinfo=None))


def _stdlib_当前时区():
    """返回本地时区信息列表，依次为时区名称与 UTC 偏移小时数。"""
    现在 = datetime.datetime.now().astimezone()
    偏移 = 现在.utcoffset()
    偏移小时 = 偏移.total_seconds() / 3600 if 偏移 is not None else 0.0
    return [现在.tzname(), 偏移小时]


def _stdlib_转换时区(时间, 源时区小时, 目标时区小时):
    """按源时区与目标时区的小时偏移转换日期时间的墙上时间。"""
    _校验时间值(时间)
    源时区 = _时区(源时区小时)
    目标时区 = _时区(目标时区小时)
    带时区 = 时间._dt.replace(tzinfo=源时区)
    return DaoDateTime(带时区.astimezone(目标时区).replace(tzinfo=None))


def create_module_env(interpreter=None) -> Environment:
    """创建时间模块的导出环境。"""
    env = Environment()
    env.define("现在", BuiltinFunction("现在", _stdlib_现在, 0))
    env.define("解析", BuiltinFunction("解析", _stdlib_解析, 2))
    env.define("格式化", BuiltinFunction("格式化", _stdlib_格式化, 2))
    env.define("计时器", BuiltinFunction("计时器", _stdlib_计时器, 0))
    env.define("睡眠", BuiltinFunction("睡眠", _stdlib_睡眠, 1))
    扩展导出表 = (
        ("时间戳", _stdlib_时间戳, 0),
        ("从时间戳", _stdlib_从时间戳, -1),
        ("到时间戳", _stdlib_到时间戳, 1),
        ("日期加减", _stdlib_日期加减, -1),
        ("创建时间", _stdlib_创建时间, -1),
        ("日历", _stdlib_日历, 2),
        ("UTC现在", _stdlib_UTC现在, 0),
        ("当前时区", _stdlib_当前时区, 0),
        ("转换时区", _stdlib_转换时区, 3),
    )
    for 名字, func, 参数个数 in 扩展导出表:
        env.define(名字, BuiltinFunction(名字, func, 参数个数))
    env.exports = list(env.values.keys())
    return env
