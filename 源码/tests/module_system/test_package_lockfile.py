"""锁文件测试：精确版本/来源持久化、安装优先、漂移检测与校验和。"""

import os
import shutil
import sys
from pathlib import Path

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from dao.package.lockfile import LOCK_FILENAME, LockDriftError, LockFile, sha256_file
from dao.package.manager import PackageManager
from dao.package.packer import pack_project
from dao.package.version import Version


def make_library(root: Path, name: str, version: str) -> str:
    project = root / f"库源码-{name}-{version}"
    project.mkdir(parents=True, exist_ok=True)
    (project / "道.配置").write_text(
        f"名称 {name}\n版本 {version}\n入口 主程序\n", encoding="utf-8"
    )
    (project / "主程序.道").write_text("导出 函数 测试()\n    返回 1\n", encoding="utf-8")
    return pack_project(str(project))


class TestLockFileFormat:
    def test_写入并读回精确版本与来源(self, tmp_path):
        path = tmp_path / LOCK_FILENAME
        lock = LockFile(path=path)
        lock.set("数学库", Version.parse("1.2.3+build.7"), source="/仓库/数学库.道包", checksum="sha256:abc")

        reloaded = LockFile(path=path)
        entry = reloaded.get("数学库")

        assert entry is not None
        assert entry.version == Version.parse("1.2.3+build.7")
        assert entry.source == "/仓库/数学库.道包"
        assert entry.checksum == "sha256:abc"
        assert reloaded.entries()["数学库"].version.patch == 3

    def test_增删与空锁判断(self, tmp_path):
        lock = LockFile(path=tmp_path / LOCK_FILENAME)
        assert lock.is_empty()
        lock.set("甲", Version.parse("1.0.0"))
        assert not lock.is_empty()
        assert lock.remove("甲") is True
        assert lock.remove("甲") is False
        assert lock.is_empty()

    def test_损坏的锁文件报中文错误(self, tmp_path):
        (tmp_path / LOCK_FILENAME).write_text("{不是 JSON", encoding="utf-8")
        with pytest.raises(ValueError, match="锁文件.*损坏|读取失败"):
            LockFile(path=tmp_path / LOCK_FILENAME).entries()


class TestInstallWithLock:
    def test_安装后记录精确版本与来源(self, tmp_path):
        archive = make_library(tmp_path, "数学库", "1.2.0")
        app = tmp_path / "应用"
        app.mkdir()

        manager = PackageManager(project_dir=str(app))
        target = manager.install(archive)

        assert Path(target).is_dir()
        locked = LockFile(project_dir=str(app)).get("数学库")
        assert locked is not None
        assert locked.version == Version.parse("1.2.0")
        assert locked.source == str(Path(archive).resolve())
        assert locked.checksum.startswith("sha256:")

    def test_按锁文件来源重新安装(self, tmp_path):
        archive = make_library(tmp_path, "数学库", "1.2.0")
        app = tmp_path / "应用"
        app.mkdir()
        manager = PackageManager(project_dir=str(app))
        target = manager.install(archive)
        shutil.rmtree(target)

        restored = manager.install_from_lock("数学库")

        assert Path(restored).is_dir()
        assert (Path(restored) / "主程序.道").is_file()

    def test_版本漂移时拒绝安装并提示更新(self, tmp_path):
        first = make_library(tmp_path, "数学库", "1.2.0")
        second = make_library(tmp_path, "数学库", "2.0.0")
        app = tmp_path / "应用"
        app.mkdir()
        manager = PackageManager(project_dir=str(app))
        manager.install(first)

        with pytest.raises(LockDriftError) as exc_info:
            manager.install(second)

        message = str(exc_info.value)
        assert "版本漂移" in message
        assert "1.2.0" in message and "2.0.0" in message
        assert "update-lock" in message

    def test_update_lock后允许升级(self, tmp_path):
        first = make_library(tmp_path, "数学库", "1.2.0")
        second = make_library(tmp_path, "数学库", "2.0.0")
        app = tmp_path / "应用"
        app.mkdir()
        manager = PackageManager(project_dir=str(app))
        manager.install(first)

        manager.install(second, force=True, update_lock=True)

        assert LockFile(project_dir=str(app)).get("数学库").version == Version.parse("2.0.0")

    def test_来源被篡改时校验失败(self, tmp_path):
        archive = Path(make_library(tmp_path, "数学库", "1.2.0"))
        app = tmp_path / "应用"
        app.mkdir()
        manager = PackageManager(project_dir=str(app))
        target = manager.install(str(archive))
        shutil.rmtree(target)
        archive.write_bytes("被篡改的内容".encode())

        with pytest.raises(ValueError, match="校验失败"):
            manager.install_from_lock("数学库")

    def test_unknown包名给出中文提示(self, tmp_path):
        app = tmp_path / "应用"
        app.mkdir()
        with pytest.raises(ValueError, match="锁文件"):
            PackageManager(project_dir=str(app)).install_from_lock("不存在的包")

    def test_sha256工具返回稳定格式(self, tmp_path):
        sample = tmp_path / "文件.道"
        sample.write_text("打印(1)", encoding="utf-8")
        assert sha256_file(sample) == sha256_file(sample)
        assert sha256_file(sample).startswith("sha256:")
