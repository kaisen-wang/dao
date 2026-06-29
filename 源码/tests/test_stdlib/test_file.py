import sys
import os
import tempfile

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from dao.stdlib.file import (
    _stdlib_读取, _stdlib_写入, _stdlib_追加, _stdlib_存在,
    _stdlib_列出目录, _stdlib_逐行读取, _stdlib_复制, _stdlib_移动,
    _stdlib_删除, _stdlib_创建目录, _stdlib_文件信息,
    create_module_env,
)
from dao.errors import 运行时错误


class TestFileRead:
    def test_read_normal(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False, encoding="utf-8") as f:
            f.write("你好，世界！")
            path = f.name
        try:
            assert _stdlib_读取(path) == "你好，世界！"
        finally:
            os.unlink(path)

    def test_read_not_exist(self):
        try:
            _stdlib_读取("/不存在的文件.txt")
            assert False, "应抛出运行时错误"
        except 运行时错误:
            pass


class TestFileWrite:
    def test_write_normal(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False, encoding="utf-8") as f:
            path = f.name
        try:
            _stdlib_写入(path, "测试内容")
            assert _stdlib_读取(path) == "测试内容"
        finally:
            os.unlink(path)


class TestFileAppend:
    def test_append(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False, encoding="utf-8") as f:
            f.write("第一行")
            path = f.name
        try:
            _stdlib_追加(path, "第二行")
            assert _stdlib_读取(path) == "第一行第二行"
        finally:
            os.unlink(path)


class TestFileExists:
    def test_exists_true(self):
        with tempfile.NamedTemporaryFile(suffix=".txt", delete=False) as f:
            path = f.name
        try:
            assert _stdlib_存在(path) is True
        finally:
            os.unlink(path)

    def test_exists_false(self):
        assert _stdlib_存在("/不存在的文件.txt") is False


class TestFileListDir:
    def test_list_dir(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            open(os.path.join(tmpdir, "a.txt"), "w").close()
            result = _stdlib_列出目录(tmpdir)
            assert "a.txt" in result

    def test_list_dir_not_exist(self):
        try:
            _stdlib_列出目录("/不存在的目录")
            assert False, "应抛出运行时错误"
        except 运行时错误:
            pass


class TestFileLineIterator:
    def test_line_iterator(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False, encoding="utf-8") as f:
            f.write("第一行\n第二行\n第三行")
            path = f.name
        try:
            lines = list(_stdlib_逐行读取(path))
            assert lines == ["第一行", "第二行", "第三行"]
        finally:
            os.unlink(path)


class TestFileOps:
    def test_copy(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False, encoding="utf-8") as f:
            f.write("内容")
            src = f.name
        dst = src + ".copy"
        try:
            _stdlib_复制(src, dst)
            assert _stdlib_存在(dst)
        finally:
            os.unlink(src)
            if os.path.exists(dst):
                os.unlink(dst)

    def test_delete(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
            path = f.name
        _stdlib_删除(path)
        assert not os.path.exists(path)

    def test_delete_not_exist(self):
        try:
            _stdlib_删除("/不存在的文件.txt")
            assert False, "应抛出运行时错误"
        except 运行时错误:
            pass

    def test_create_dir(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, "a", "b", "c")
            _stdlib_创建目录(path)
            assert os.path.isdir(path)

    def test_file_info(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False, encoding="utf-8") as f:
            f.write("内容")
            path = f.name
        try:
            info = _stdlib_文件信息(path)
            assert info["是否文件"] is True
            assert info["是否目录"] is False
            assert info["大小"] > 0
        finally:
            os.unlink(path)


class TestFileModuleEnv:
    def test_create_module_env(self):
        env = create_module_env()
        assert "读取" in env.values
        assert "写入" in env.values