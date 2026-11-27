"""归档模块测试：覆盖 zip/tar 打包解包与路径穿越防护。"""

import os
import sys
import tarfile
import zipfile

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from dao.errors import 类型错误, 运行时错误
from dao.stdlib.archive import (
    _stdlib_打包TAR,
    _stdlib_打包ZIP,
    _stdlib_列出TAR,
    _stdlib_列出ZIP,
    _stdlib_解包TAR,
    _stdlib_解包ZIP,
    create_module_env,
)


def _建源目录(tmp_path):
    源目录 = tmp_path / "源"
    子目录 = 源目录 / "子目录"
    子目录.mkdir(parents=True)
    (源目录 / "顶层.txt").write_text("顶层", encoding="utf-8")
    (子目录 / "深层.txt").write_text("深层", encoding="utf-8")
    return 源目录


class TestZIP:
    def test_打包列出解包(self, tmp_path):
        源目录 = _建源目录(tmp_path)
        压缩包 = tmp_path / "归档.zip"
        assert _stdlib_打包ZIP(str(源目录), str(压缩包)) == str(压缩包)
        成员 = _stdlib_列出ZIP(str(压缩包))
        assert "顶层.txt" in 成员
        assert os.path.join("子目录", "深层.txt") in 成员
        目标 = tmp_path / "解包"
        assert _stdlib_解包ZIP(str(压缩包), str(目标)) == str(目标)
        assert (目标 / "顶层.txt").read_text(encoding="utf-8") == "顶层"
        assert (目标 / "子目录" / "深层.txt").read_text(encoding="utf-8") == "深层"

    def test_打包单文件(self, tmp_path):
        文件 = tmp_path / "单文件.txt"
        文件.write_text("内容", encoding="utf-8")
        压缩包 = tmp_path / "单文件.zip"
        _stdlib_打包ZIP(str(文件), str(压缩包))
        assert _stdlib_列出ZIP(str(压缩包)) == ["单文件.txt"]

    def test_源不存在抛异常(self, tmp_path):
        with pytest.raises(运行时错误):
            _stdlib_打包ZIP(str(tmp_path / "不存在"), str(tmp_path / "x.zip"))

    def test_目标非文本抛异常(self, tmp_path):
        with pytest.raises(类型错误):
            _stdlib_打包ZIP(str(_建源目录(tmp_path)), 123)

    def test_无效归档抛异常(self, tmp_path):
        坏文件 = tmp_path / "坏.zip"
        坏文件.write_text("不是 zip", encoding="utf-8")
        with pytest.raises(运行时错误):
            _stdlib_解包ZIP(str(坏文件), str(tmp_path / "解包"))
        with pytest.raises(运行时错误):
            _stdlib_列出ZIP(str(坏文件))

    def test_压缩包不存在抛异常(self, tmp_path):
        with pytest.raises(运行时错误):
            _stdlib_列出ZIP(str(tmp_path / "不存在.zip"))

    def test_路径穿越成员被拒绝(self, tmp_path):
        压缩包 = tmp_path / "恶意.zip"
        with zipfile.ZipFile(压缩包, "w") as 归档:
            归档.writestr("../越界.txt", "危险")
        with pytest.raises(运行时错误, match="越界"):
            _stdlib_解包ZIP(str(压缩包), str(tmp_path / "解包"))
        assert not (tmp_path / "越界.txt").exists()


class TestTAR:
    def test_打包列出解包(self, tmp_path):
        源目录 = _建源目录(tmp_path)
        压缩包 = tmp_path / "归档.tar"
        assert _stdlib_打包TAR(str(源目录), str(压缩包)) == str(压缩包)
        成员 = _stdlib_列出TAR(str(压缩包))
        assert "顶层.txt" in 成员
        assert os.path.join("子目录", "深层.txt") in 成员
        目标 = tmp_path / "解包"
        assert _stdlib_解包TAR(str(压缩包), str(目标)) == str(目标)
        assert (目标 / "顶层.txt").read_text(encoding="utf-8") == "顶层"

    def test_gz压缩(self, tmp_path):
        源目录 = _建源目录(tmp_path)
        压缩包 = tmp_path / "归档.tar.gz"
        _stdlib_打包TAR(str(源目录), str(压缩包), "gz")
        assert "顶层.txt" in _stdlib_列出TAR(str(压缩包))
        目标 = tmp_path / "解包"
        _stdlib_解包TAR(str(压缩包), str(目标))
        assert (目标 / "子目录" / "深层.txt").exists()

    def test_非法压缩方式抛异常(self, tmp_path):
        with pytest.raises(运行时错误):
            _stdlib_打包TAR(str(_建源目录(tmp_path)), str(tmp_path / "x.tar"), "zip")

    def test_无效归档抛异常(self, tmp_path):
        坏文件 = tmp_path / "坏.tar"
        坏文件.write_text("不是 tar", encoding="utf-8")
        with pytest.raises(运行时错误):
            _stdlib_解包TAR(str(坏文件), str(tmp_path / "解包"))
        with pytest.raises(运行时错误):
            _stdlib_列出TAR(str(坏文件))

    def test_绝对路径成员被拒绝(self, tmp_path):
        内容 = tmp_path / "载荷.txt"
        内容.write_text("危险", encoding="utf-8")
        压缩包 = tmp_path / "恶意.tar"
        with tarfile.open(压缩包, "w") as 归档:
            成员 = tarfile.TarInfo(name="/tmp/绝对越界.txt")
            成员.size = 内容.stat().st_size
            归档.addfile(成员, 内容.open("rb"))
        with pytest.raises(运行时错误):
            _stdlib_解包TAR(str(压缩包), str(tmp_path / "解包"))


class Test归档模块环境:
    def test_导出集合(self):
        env = create_module_env()
        assert "打包ZIP" in env.values
        assert "解包TAR" in env.values
        assert set(env.exports) == set(env.values)
