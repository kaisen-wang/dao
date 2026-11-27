import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from dao.stdlib.time import (
    _stdlib_现在, _stdlib_解析, _stdlib_格式化, _stdlib_计时器,
    _stdlib_时间戳, _stdlib_从时间戳, _stdlib_到时间戳, _stdlib_日期加减,
    _stdlib_创建时间, _stdlib_日历, _stdlib_UTC现在, _stdlib_当前时区,
    _stdlib_转换时区,
    DaoDateTime, DaoTimeDelta, DaoTimer,
    create_module_env,
)
from dao.errors import 类型错误, 运行时错误


class TestTimeNow:
    def test_now(self):
        dt = _stdlib_现在()
        assert isinstance(dt, DaoDateTime)
        assert dt.年份 > 2000

    def test_datetime_properties(self):
        dt = _stdlib_现在()
        assert 1 <= dt.月份 <= 12
        assert 1 <= dt.日 <= 31
        assert 0 <= dt.小时 <= 23


class TestTimeParse:
    def test_parse_normal(self):
        dt = _stdlib_解析("2000-01-15", "YYYY-MM-DD")
        assert dt.年份 == 2000
        assert dt.月份 == 1
        assert dt.日 == 15

    def test_parse_invalid(self):
        try:
            _stdlib_解析("不是日期", "YYYY-MM-DD")
            assert False, "应抛出运行时错误"
        except 运行时错误:
            pass


class TestTimeFormat:
    def test_format_normal(self):
        dt = _stdlib_解析("2026-02-09", "YYYY-MM-DD")
        result = _stdlib_格式化(dt, "YYYY年MM月DD日")
        assert result == "2026年02月09日"

    def test_format_non_datetime(self):
        try:
            _stdlib_格式化("不是时间", "YYYY")
            assert False, "应抛出运行时错误"
        except 运行时错误:
            pass


class TestTimeSub:
    def test_sub_datetimes(self):
        dt1 = _stdlib_解析("2026-06-01", "YYYY-MM-DD")
        dt2 = _stdlib_解析("2026-05-01", "YYYY-MM-DD")
        delta = dt1 - dt2
        assert isinstance(delta, DaoTimeDelta)
        assert delta.天数 == 31


class TestTimer:
    def test_timer(self):
        timer = _stdlib_计时器()
        assert isinstance(timer, DaoTimer)
        timer.开始()
        import time
        time.sleep(0.01)
        ms = timer.停止()
        assert ms > 0

    def test_timer_not_started(self):
        timer = DaoTimer()
        try:
            timer.停止()
            assert False, "应抛出运行时错误"
        except 运行时错误:
            pass


class TestTimeModuleEnv:
    def test_create_module_env(self):
        env = create_module_env()
        assert "现在" in env.values
        assert "解析" in env.values


class TestTimeStamp:
    def test_时间戳为数字且接近当前(self):
        import time
        前 = time.time()
        结果 = _stdlib_时间戳()
        后 = time.time()
        assert isinstance(结果, float)
        assert 前 <= 结果 <= 后

    def test_从时间戳带时区(self):
        结果 = _stdlib_从时间戳(0, 8)
        assert isinstance(结果, DaoDateTime)
        assert 结果.年份 == 1970 and 结果.小时 == 8

    def test_时间戳互转(self):
        原时间 = _stdlib_创建时间(2026, 6, 1, 12, 0, 0)
        戳 = _stdlib_到时间戳(原时间)
        还原 = _stdlib_从时间戳(戳)
        assert 还原.年份 == 2026 and 还原.月份 == 6 and 还原.日 == 1
        assert 还原.小时 == 12

    def test_从时间戳参数错误(self):
        try:
            _stdlib_从时间戳("不是数字")
            assert False, "应抛出类型错误"
        except 类型错误:
            pass
        try:
            _stdlib_从时间戳(0, 100)
            assert False, "应抛出运行时错误"
        except 运行时错误:
            pass


class Test日期计算:
    def test_日期加减(self):
        原时间 = _stdlib_创建时间(2026, 1, 1)
        结果 = _stdlib_日期加减(原时间, 天数=1, 秒数=60)
        assert 结果.日 == 2
        assert 结果.小时 == 0 and 结果.分钟 == 1

    def test_日期加减负数(self):
        原时间 = _stdlib_创建时间(2026, 1, 1)
        结果 = _stdlib_日期加减(原时间, 天数=-1)
        assert 结果.年份 == 2025 and 结果.日 == 31

    def test_日期加减参数错误(self):
        try:
            _stdlib_日期加减("不是时间", 天数=1)
            assert False, "应抛出类型错误"
        except 类型错误:
            pass

    def test_创建时间(self):
        结果 = _stdlib_创建时间(2026, 2, 9, 15, 30, 45)
        assert 结果.年份 == 2026 and 结果.分钟 == 30 and 结果.秒 == 45

    def test_创建无效日期抛异常(self):
        try:
            _stdlib_创建时间(2026, 2, 30)
            assert False, "应抛出运行时错误"
        except 运行时错误:
            pass

    def test_日历(self):
        结果 = _stdlib_日历(2026, 2)
        assert isinstance(结果, list) and len(结果) >= 4
        assert all(isinstance(周, list) and len(周) == 7 for 周 in 结果)

    def test_日历月份越界抛异常(self):
        try:
            _stdlib_日历(2026, 13)
            assert False, "应抛出运行时错误"
        except 运行时错误:
            pass


class Test时区:
    def test_UTC现在(self):
        结果 = _stdlib_UTC现在()
        assert isinstance(结果, DaoDateTime)
        assert 0 <= 结果.小时 <= 23

    def test_当前时区(self):
        结果 = _stdlib_当前时区()
        assert isinstance(结果, list) and len(结果) == 2
        assert isinstance(结果[0], str)
        assert isinstance(结果[1], (int, float))

    def test_转换时区(self):
        北京时间 = _stdlib_创建时间(2026, 1, 1, 8)
        结果 = _stdlib_转换时区(北京时间, 8, 0)
        assert 结果.年份 == 2026 and 结果.日 == 1 and 结果.小时 == 0

    def test_转换时区参数错误(self):
        try:
            _stdlib_转换时区("不是时间", 8, 0)
            assert False, "应抛出类型错误"
        except 类型错误:
            pass