import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from dao.stdlib.time import (
    _stdlib_现在, _stdlib_解析, _stdlib_格式化, _stdlib_计时器,
    DaoDateTime, DaoTimeDelta, DaoTimer,
    create_module_env,
)
from dao.errors import 运行时错误


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