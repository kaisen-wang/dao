"""路径模块测试：覆盖拼接、拆分、判断、遍历与匹配的正误路径。"""

import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from dao.errors import 类型错误, 运行时错误
from dao.stdlib.path import (
    _stdlib_存在,
    _stdlib_取主名,
    _stdlib_取父目录,
    _stdlib_取文件名,
    _stdlib_取扩展名,
    _stdlib_匹配,
    _stdlib_拼接,
    _stdlib_列出,
    _stdlib_相对路径,
    _stdlib_规范化,
    _stdlib_绝对路径,
    _stdlib_是文件,
    _stdlib_是目录,
    _stdlib_遍历,
    _stdlib_分割,
    create_module_env,
)


class Test拼接:
    def test_拼接多个片段(self):
        结果 = _stdlib_拼接("数据", "日志", "2026.txt")
        assert 结果 == os.path.join("数据", "日志", "2026.txt")

    def test_绝对路径片段覆盖相对片段(self):
        结果 = _stdlib_拼接("数据", "/等/配置.json")
        assert 结果 == "/等/配置.json"

    def test_拼接无参数抛异常(self):
        with pytest.raises(运行时错误):
            _stdlib_拼接()

    def test_拼接非文本抛异常(self):
        with pytest.raises(类型错误):
            _stdlib_拼接("数据", 123)


class Test拆分:
    def test_取文件名(self):
        assert _stdlib_取文件名("/数据/日志/app.log") == "app.log"

    def test_取主名与扩展名(self):
        路径 = "/数据/归档.tar.gz"
        assert _stdlib_取主名(路径) == "归档.tar"
        assert _stdlib_取扩展名(路径) == ".gz"

    def test_无扩展名(self):
        assert _stdlib_取扩展名("README") == ""

    def test_取父目录与分割(self):
        路径 = os.path.join("数据", "日志", "app.log")
        assert _stdlib_取父目录(路径) == os.path.join("数据", "日志")
        assert _stdlib_分割(路径) == [os.path.join("数据", "日志"), "app.log"]

    def test_拆分非文本抛异常(self):
        with pytest.raises(类型错误):
            _stdlib_取扩展名(123)


class Test路径转换:
    def test_绝对路径(self):
        结果 = _stdlib_绝对路径(".")
        assert os.path.isabs(结果)

    def test_规范化(self):
        assert _stdlib_规范化("数据//日志/../app.log") == os.path.join("数据", "app.log")

    def test_相对路径(self):
        结果 = _stdlib_相对路径("/数据/日志/app.log", "/数据")
        assert 结果 == os.path.join("日志", "app.log")

    def test_相对路径非文本抛异常(self):
        with pytest.raises(类型错误):
            _stdlib_相对路径("/数据", 123)


class Test存在性判断:
    def test_存在与文件目录判断(self, tmp_path):
        文件 = tmp_path / "a.txt"
        文件.write_text("你好", encoding="utf-8")
        assert _stdlib_存在(str(文件)) is True
        assert _stdlib_是文件(str(文件)) is True
        assert _stdlib_是目录(str(文件)) is False
        assert _stdlib_是目录(str(tmp_path)) is True
        assert _stdlib_存在(str(tmp_path / "不存在")) is False

    def test_判断非文本抛异常(self):
        with pytest.raises(类型错误):
            _stdlib_存在(123)


class Test遍历与匹配:
    def test_列出(self, tmp_path):
        (tmp_path / "b.txt").write_text("b", encoding="utf-8")
        (tmp_path / "a.txt").write_text("a", encoding="utf-8")
        assert _stdlib_列出(str(tmp_path)) == ["a.txt", "b.txt"]

    def test_列出不存在目录抛异常(self):
        with pytest.raises(运行时错误):
            _stdlib_列出("/不存在的目录/xyz")

    def test_遍历(self, tmp_path):
        子目录 = tmp_path / "子目录"
        子目录.mkdir()
        (子目录 / "深层.txt").write_text("x", encoding="utf-8")
        (tmp_path / "顶层.txt").write_text("y", encoding="utf-8")
        结果 = _stdlib_遍历(str(tmp_path))
        assert str(子目录) in 结果
        assert os.path.join(str(子目录), "深层.txt") in 结果
        assert os.path.join(str(tmp_path), "顶层.txt") in 结果

    def test_遍历不存在目录抛异常(self):
        with pytest.raises(运行时错误):
            _stdlib_遍历("/不存在的目录/xyz")

    def test_匹配(self, tmp_path):
        (tmp_path / "a.txt").write_text("a", encoding="utf-8")
        (tmp_path / "b.log").write_text("b", encoding="utf-8")
        结果 = _stdlib_匹配(str(tmp_path / "*.txt"))
        assert 结果 == [str(tmp_path / "a.txt")]

    def test_递归匹配(self, tmp_path):
        子目录 = tmp_path / "子"
        子目录.mkdir()
        (子目录 / "深层.txt").write_text("x", encoding="utf-8")
        结果 = _stdlib_匹配(str(tmp_path / "**" / "*.txt"), True)
        assert str(子目录 / "深层.txt") in 结果

    def test_匹配非布尔递归抛异常(self):
        with pytest.raises(类型错误):
            _stdlib_匹配("*.txt", "真")


class Test路径模块环境:
    def test_导出集合(self):
        env = create_module_env()
        assert "拼接" in env.values
        assert "匹配" in env.values
        assert set(env.exports) == set(env.values)
