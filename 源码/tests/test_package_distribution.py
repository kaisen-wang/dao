"""包分发闭环端到端测试：发布 → 本地仓库 → 按锁安装 → 版本漂移。

放在 tests/ 顶层，便于 ``pytest tests/test_package*.py`` 直接命中。
"""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from dao.package.manager import PackageManager
from dao.package.packer import CONFIG_FILENAME
from dao.package.publish import publish
from dao.package.repository import RepositoryIndex
from dao.package.resolver import DependencyConflictError, PackageResolver
from dao.package.version import VersionConstraint


def make_library(root: Path, name: str, version: str) -> Path:
    project = root / f"源码-{name}-{version}"
    project.mkdir(parents=True, exist_ok=True)
    (project / CONFIG_FILENAME).write_text(
        f"名称 {name}\n版本 {version}\n入口 主程序\n", encoding="utf-8"
    )
    (project / "主程序.道").write_text("导出 函数 测试()\n    返回 1\n", encoding="utf-8")
    return project


def prepare_home(tmp_path: Path, monkeypatch):
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: tmp_path))
    monkeypatch.setenv("HOME", str(tmp_path))


class TestDistributionLoop:
    def test_发布后从本地仓库安装并写入锁文件(self, tmp_path, monkeypatch):
        prepare_home(tmp_path, monkeypatch)
        library = make_library(tmp_path, "数学库", "1.2.0")
        published = publish(str(library))
        assert RepositoryIndex().query("数学库")

        app = tmp_path / "应用"
        app.mkdir()
        (app / CONFIG_FILENAME).write_text(
            "名称 应用\n版本 1.0.0\n入口 主程序\n依赖\n    数学库 >=1.2.0\n",
            encoding="utf-8",
        )
        (app / "主程序.道").write_text("从 数学库 导入 测试\n打印(测试())\n", encoding="utf-8")

        manager = PackageManager(project_dir=str(app))
        installed = manager.install_all()

        assert len(installed) == 1
        assert Path(installed[0]) == app / "道包" / "数学库"
        assert (Path(installed[0]) / "主程序.道").is_file()
        locked = manager.lock.get("数学库")
        assert locked is not None
        assert str(locked.version) == "1.2.0"
        assert Path(locked.source).is_file()
        assert published.entry.name == "数学库"

    def test_锁文件来源丢失后给出中文提示(self, tmp_path, monkeypatch):
        prepare_home(tmp_path, monkeypatch)
        publish(str(make_library(tmp_path, "数学库", "1.2.0")))
        app = tmp_path / "应用"
        app.mkdir()
        (app / CONFIG_FILENAME).write_text(
            "名称 应用\n版本 1.0.0\n依赖\n    数学库 >=1.2.0\n", encoding="utf-8"
        )
        manager = PackageManager(project_dir=str(app))
        manager.install_all()
        source = Path(manager.lock.get("数学库").source)
        source.unlink()

        with pytest.raises(ValueError, match="来源不存在|更新锁文件"):
            manager.install_from_lock("数学库")

    def test_冲突错误明确指出两个约束(self, tmp_path, monkeypatch):
        prepare_home(tmp_path, monkeypatch)
        repository = RepositoryIndex()
        repository.add(publish(str(make_library(tmp_path, "数学库", "1.0.0"))).archive_path)

        resolver = PackageResolver(index=repository)
        with pytest.raises(DependencyConflictError) as exc_info:
            resolver.resolve_best(
                "数学库",
                [VersionConstraint.parse("^1.0.0"), VersionConstraint.parse(">=2.0.0")],
            )

        message = str(exc_info.value)
        assert "依赖冲突" in message
        assert "^1.0.0" in message
        assert ">=2.0.0" in message
