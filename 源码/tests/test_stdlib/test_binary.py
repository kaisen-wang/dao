"""二进制模块测试：定长打包、字节互转、安全序列化与 pickle 安全策略。"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest

from dao.errors import 类型错误, 运行时错误
from dao.stdlib import binary as 二进制模块
from dao.stdlib.binary import (
    _stdlib_安全反序列化,
    _stdlib_安全序列化,
    _stdlib_字节转整数,
    _stdlib_字节转浮点,
    _stdlib_定长打包,
    _stdlib_定长解包,
    _stdlib_读取字节,
    _stdlib_Pickle打包,
    _stdlib_Pickle解包,
    _stdlib_写入字节,
    _stdlib_浮点转字节,
    _stdlib_计算大小,
    _stdlib_整数转字节,
)


class 可序列化对象:
    """用于验证 pickle 白名单拦截的模块级类。"""

    def __init__(self):
        self.值 = 1


class Test定长打包:
    def test_单值与列表打包(self):
        assert _stdlib_定长打包(">i", 42) == b"\x00\x00\x00\x2a"
        assert _stdlib_定长打包(">2i", [1, 2]) == b"\x00\x00\x00\x01\x00\x00\x00\x02"

    def test_打包解包往返(self):
        assert _stdlib_定长解包(">2if", _stdlib_定长打包(">2if", [1, 2, 3.5])) == [1, 2, 3.5]

    def test_格式与取值不匹配(self):
        with pytest.raises(运行时错误):
            _stdlib_定长打包(">i", [1, 2])

    def test_空格式或非法数据类型(self):
        with pytest.raises(运行时错误):
            _stdlib_定长打包("", 1)
        with pytest.raises(类型错误):
            _stdlib_定长打包(123, 1)

    def test_解包长度不符(self):
        with pytest.raises(运行时错误):
            _stdlib_定长解包(">2i", b"\x00\x00\x00\x01")
        with pytest.raises(类型错误):
            _stdlib_定长解包(">i", "不是字节")

    def test_计算大小(self):
        assert _stdlib_计算大小(">2id") == 16
        with pytest.raises(运行时错误):
            _stdlib_计算大小("不存在的格式")


class Test字节互转:
    def test_整数大端小端(self):
        assert _stdlib_整数转字节(258, 2) == b"\x01\x02"
        assert _stdlib_整数转字节(258, 2, 字节序="小端") == b"\x02\x01"
        assert _stdlib_字节转整数(b"\x01\x02") == 258
        assert _stdlib_字节转整数(b"\x01\x02", 字节序="小端") == 513

    def test_有符号整数(self):
        assert _stdlib_整数转字节(-1, 1, 有符号=True) == b"\xff"
        assert _stdlib_字节转整数(b"\xff", 有符号=True) == -1

    def test_整数参数错误(self):
        with pytest.raises(类型错误):
            _stdlib_整数转字节("1")
        with pytest.raises(运行时错误):
            _stdlib_整数转字节(1, 0)
        with pytest.raises(运行时错误):
            _stdlib_整数转字节(256, 1)

    def test_浮点往返(self):
        assert _stdlib_浮点转字节(1.5) == b"\x3f\xf8\x00\x00\x00\x00\x00\x00"
        assert _stdlib_字节转浮点(_stdlib_浮点转字节(3.25)) == 3.25
        assert _stdlib_字节转浮点(_stdlib_浮点转字节(-2.5, "小端"), "小端") == -2.5

    def test_浮点错误路径(self):
        with pytest.raises(类型错误):
            _stdlib_浮点转字节("1.5")
        with pytest.raises(运行时错误):
            _stdlib_字节转浮点(b"\x00\x00\x00\x01")
        with pytest.raises(运行时错误):
            _stdlib_整数转字节(1, 字节序="未知")


class Test安全序列化:
    def test_基础类型往返(self):
        数据 = {
            "空": None,
            "真": True,
            "假": False,
            "整数": 12345678901234567890,
            "浮点": 3.25,
            "文本": "你好，世界",
            "字节": b"\x00\xff",
            "列表": [1, "二", None],
            "元组": (1, "二"),
        }
        assert _stdlib_安全反序列化(_stdlib_安全序列化(数据)) == 数据

    def test_大整数精度保持(self):
        数值 = 2 ** 100 + 7
        assert _stdlib_安全反序列化(_stdlib_安全序列化(数值)) == 数值

    def test_自定义类型被拒绝(self):
        class 自定义:
            pass

        with pytest.raises(类型错误):
            _stdlib_安全序列化(自定义())

    def test_未知标签被拒绝(self):
        数据 = b'{"t": "object", "v": {}}'
        with pytest.raises(运行时错误):
            _stdlib_安全反序列化(数据)

    def test_无效数据被拒绝(self):
        with pytest.raises(运行时错误):
            _stdlib_安全反序列化(b"not json")
        with pytest.raises(类型错误):
            _stdlib_安全反序列化("不是字节")


class Test字节文件:
    def test_写入读取往返(self, tmp_path):
        路径 = tmp_path / "数据.bin"
        assert _stdlib_写入字节(str(路径), b"\x01\x02\x03") == 3
        assert _stdlib_读取字节(str(路径)) == b"\x01\x02\x03"

    def test_读取不存在的文件(self, tmp_path):
        with pytest.raises(运行时错误):
            _stdlib_读取字节(str(tmp_path / "不存在.bin"))

    def test_写入类型错误(self, tmp_path):
        with pytest.raises(类型错误):
            _stdlib_写入字节(str(tmp_path / "x.bin"), "文本")

    def test_序列化到文件往返(self, tmp_path):
        路径 = tmp_path / "安全.bin"
        数据 = {"姓名": "张三", "编号": 7}
        assert 二进制模块._stdlib_序列化到文件(数据, str(路径)) > 0
        assert 二进制模块._stdlib_反序列化自文件(str(路径)) == 数据


class TestPickle安全策略:
    def test_默认拒绝不可信数据(self):
        with pytest.raises(运行时错误, match="拒绝"):
            _stdlib_Pickle解包(_stdlib_Pickle打包({"a": 1}))

    def test_白名单内类型可加载(self):
        数据 = _stdlib_Pickle打包({"a": 1})
        assert _stdlib_Pickle解包(数据, 白名单=["builtins.dict"]) == {"a": 1}

    def test_白名单外类型被拒绝(self):
        数据 = _stdlib_Pickle打包(可序列化对象())
        with pytest.raises(运行时错误, match="白名单"):
            _stdlib_Pickle解包(数据, 白名单=["builtins.dict"])

    def test_白名单参数类型校验(self):
        数据 = _stdlib_Pickle打包({"a": 1})
        with pytest.raises(类型错误):
            _stdlib_Pickle解包(数据, 白名单="builtins.dict")
        with pytest.raises(运行时错误):
            _stdlib_Pickle解包(b"invalid pickle", 白名单=[])


class Test二进制模块环境:
    def test_导出集合与工厂幂等(self):
        环境 = 二进制模块.create_module_env()
        再次 = 二进制模块.create_module_env()
        assert set(环境.exports) == set(再次.exports)
        assert len(环境.exports) == 15
        assert 环境.values["定长打包"].param_count == 2
        assert "Pickle解包" in 环境.exports
