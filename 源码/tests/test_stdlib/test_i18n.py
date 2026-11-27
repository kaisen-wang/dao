"""国际化模块测试：区域设置、翻译表、复数形式与本地化格式。"""

import locale
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest

from dao.errors import 类型错误, 运行时错误
from dao.stdlib import i18n as 国际化模块
from dao.stdlib.i18n import (
    _stdlib_当前区域,
    _stdlib_区域别名,
    _stdlib_可用区域,
    _stdlib_复数形式,
    _stdlib_格式化日期,
    _stdlib_格式化数字,
    _stdlib_格式化货币,
    _stdlib_清除翻译,
    _stdlib_注册翻译,
    _stdlib_设置区域,
    _stdlib_翻译,
    _stdlib_翻译项数,
    _stdlib_月份名称,
    _stdlib_星期名称,
)


@pytest.fixture(autouse=True)
def 隔离翻译表():
    """每个用例使用空的翻译表，避免模块级缓存互相污染。"""
    _stdlib_清除翻译()
    yield
    _stdlib_清除翻译()


class Test区域设置:
    def test_当前区域(self):
        结果 = _stdlib_当前区域()
        assert isinstance(结果, dict)
        assert "语言" in 结果 and "编码" in 结果

    def test_区域别名(self):
        assert _stdlib_区域别名("zh_CN.UTF-8") == "zh_CN.UTF-8"
        with pytest.raises(类型错误):
            _stdlib_区域别名(123)

    def test_可用区域(self):
        列表 = _stdlib_可用区域()
        assert isinstance(列表, list)
        assert 列表 == sorted(列表)
        assert len(列表) > 0

    def test_设置区域与恢复(self):
        原始 = locale.setlocale(locale.LC_ALL)
        try:
            assert _stdlib_设置区域("C") == "C"
        finally:
            locale.setlocale(locale.LC_ALL, 原始)

    def test_设置区域非法(self):
        with pytest.raises(运行时错误):
            _stdlib_设置区域("不存在的区域.XX")


class Test翻译表:
    def test_注册查询与前缀回退(self):
        _stdlib_注册翻译("zh_CN", "hello", "你好")
        _stdlib_注册翻译("zh", "thanks", "谢谢")
        assert _stdlib_翻译("hello", "zh_CN") == "你好"
        assert _stdlib_翻译("thanks", "zh_CN") == "谢谢"

    def test_多语言互不干扰(self):
        _stdlib_注册翻译("zh_CN", "hello", "你好")
        _stdlib_注册翻译("en_US", "hello", "Hello")
        assert _stdlib_翻译("hello", "zh_CN") == "你好"
        assert _stdlib_翻译("hello", "en_US") == "Hello"

    def test_默认值与键回退(self):
        assert _stdlib_翻译("缺失", "fr_FR", 默认="缺省") == "缺省"
        assert _stdlib_翻译("缺失", "fr_FR") == "缺失"

    def test_项数与清除(self):
        _stdlib_注册翻译("zh_CN", "a", "甲")
        _stdlib_注册翻译("en_US", "b", "B")
        assert _stdlib_翻译项数() == 2
        assert _stdlib_翻译项数("zh_CN") == 1
        assert _stdlib_清除翻译("zh_CN") == 1
        assert _stdlib_翻译项数() == 1
        assert _stdlib_清除翻译() == 1
        assert _stdlib_翻译项数() == 0

    def test_参数类型错误(self):
        with pytest.raises(类型错误):
            _stdlib_注册翻译("zh", 123, "值")
        with pytest.raises(类型错误):
            _stdlib_注册翻译("zh", "键", 123)
        with pytest.raises(类型错误):
            _stdlib_翻译(123)


class Test复数形式:
    def test_中文始终单数(self):
        assert _stdlib_复数形式(2, "个", None, "zh_CN") == "个"
        assert _stdlib_复数形式(1, "个", "个", "zh") == "个"

    def test_英文单复数(self):
        assert _stdlib_复数形式(1, "item", "items", "en_US") == "item"
        assert _stdlib_复数形式(0, "item", "items", "en_US") == "items"
        assert _stdlib_复数形式(2, "item", None, "en") == "items"

    def test_参数错误(self):
        with pytest.raises(类型错误):
            _stdlib_复数形式("1", "item", "items", "en")
        with pytest.raises(类型错误):
            _stdlib_复数形式(2, 1, "items", "en")


class Test本地化格式:
    def test_数字分组与小数符(self):
        assert _stdlib_格式化数字(1234567, "zh_CN") == "1,234,567"
        assert _stdlib_格式化数字(1234567.5, "de_DE") == "1.234.567,5"
        assert _stdlib_格式化数字(1234567, "zh_CN", 分组=False) == "1234567"

    def test_数字参数错误(self):
        with pytest.raises(类型错误):
            _stdlib_格式化数字("123")
        with pytest.raises(类型错误):
            _stdlib_格式化数字(1, 分组="真")

    def test_货币格式(self):
        assert _stdlib_格式化货币(12.5, 语言="en_US") == "$12.5"
        assert _stdlib_格式化货币(12.5, 符号="€", 语言="de_DE") == "12,5 €"
        with pytest.raises(类型错误):
            _stdlib_格式化货币(1, 符号=123)

    def test_日期与星期月份(self):
        assert _stdlib_格式化日期("2026-11-27", "%Y-%m-%d") == "2026-11-27"
        assert _stdlib_格式化日期("2026-11-27", "%Y年%B%A", "zh_CN") == "2026年十一月星期五"
        assert _stdlib_星期名称("2026-11-27", "en_US") == "Friday"
        assert _stdlib_月份名称("2026-11-27", "en_US") == "November"

    def test_日期错误路径(self):
        with pytest.raises(类型错误):
            _stdlib_格式化日期("2026-11-27", 123)
        with pytest.raises(运行时错误):
            _stdlib_格式化日期("不是时间")
        with pytest.raises(类型错误):
            _stdlib_格式化日期(True)


class Test国际化模块环境:
    def test_导出集合与工厂幂等(self):
        环境 = 国际化模块.create_module_env()
        再次 = 国际化模块.create_module_env()
        assert set(环境.exports) == set(再次.exports)
        assert len(环境.exports) == 14
        assert 环境.values["注册翻译"].param_count == 3
        assert "格式化日期" in 环境.exports
