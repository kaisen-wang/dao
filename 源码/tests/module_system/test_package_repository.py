"""本地仓库索引测试：登记、按名/版本范围查询、自动建索引与维护。"""

import os
import sys
from pathlib import Path

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from dao.package.packer import CONFIG_FILENAME, pack_project
from dao.package.repository import INDEX_FILENAME, IndexEntry, RepositoryIndex
from dao.package.version import Version, VersionConstraint


def make_archive(root: Path, name: str, version: str, deps: str = "") -> str:
    project = root / f"源-{name}-{version}"
    project.mkdir(parents=True, exist_ok=True)
    (project / CONFIG_FILENAME).write_text(
        f"名称 {name}\n版本 {version}\n入口 主程序\n{deps}", encoding="utf-8"
    )
    (project / "主程序.道").write_text("导出 函数 测试()\n    返回 1\n", encoding="utf-8")
    return pack_project(str(project))


class TestIndexAdd:
    def test_登记归档后可按名查询(self, tmp_path):
        repository = RepositoryIndex(root=tmp_path / "仓库")
        archive = make_archive(tmp_path, "数学库", "1.2.0", deps="依赖\n    工具库 >=1.0.0\n")

        entry = repository.add(archive, source="本地构建")
        found = repository.query("数学库")

        assert entry.name == "数学库"
        assert entry.version == Version.parse("1.2.0")
        assert Path(entry.path).is_file()
        assert entry.source == "本地构建"
        assert entry.dependencies == ["工具库 >=1.0.0"]
        assert len(found) == 1
        assert found[0].path == entry.path

    def test_按版本范围查询并按版本降序(self, tmp_path):
        repository = RepositoryIndex(root=tmp_path / "仓库")
        for version in ("1.0.0", "1.1.0", "2.0.0"):
            repository.add(make_archive(tmp_path, "缓存库", version))

        caret = repository.query("缓存库", "^1.0.0")
        bounded = repository.query("缓存库", VersionConstraint.parse("<2.0.0"))

        assert [str(item.version) for item in caret] == ["1.1.0", "1.0.0"]
        assert [str(item.version) for item in bounded] == ["1.1.0", "1.0.0"]
        assert repository.versions("缓存库") == [
            Version.parse("2.0.0"), Version.parse("1.1.0"), Version.parse("1.0.0")
        ]

    def test_同名同版本重复登记只保留一条(self, tmp_path):
        repository = RepositoryIndex(root=tmp_path / "仓库")
        first = make_archive(tmp_path, "数学库", "1.2.0")
        second = make_archive(tmp_path / "副本", "数学库", "1.2.0")

        repository.add(first)
        repository.add(second, source="第二次")

        assert len(repository.query("数学库")) == 1
        assert repository.query("数学库")[0].source == "第二次"

    def test_索引条目可还原为包配置(self, tmp_path):
        repository = RepositoryIndex(root=tmp_path / "仓库")
        repository.add(make_archive(tmp_path, "数学库", "1.2.0", deps="依赖\n    工具库 ^1.0.0\n"))

        config = repository.query("数学库")[0].to_config()

        assert config.name == "数学库"
        assert config.version == Version.parse("1.2.0")
        assert [str(dep) for dep in config.dependencies] == ["工具库 ^1.0.0"]


class TestSyncInstalled:
    def test_从已安装包自动建立索引(self, tmp_path, monkeypatch):
        monkeypatch.setattr(Path, "home", classmethod(lambda cls: tmp_path))
        project = tmp_path / "应用"
        installed = project / "道包" / "数学库"
        installed.mkdir(parents=True)
        (installed / CONFIG_FILENAME).write_text(
            "名称 数学库\n版本 1.2.0\n入口 主程序\n道版本 >=1.2.0\n", encoding="utf-8"
        )
        repository = RepositoryIndex(root=tmp_path / "仓库")

        added = repository.sync_installed(project_dir=str(project), global_install=False)

        assert len(added) == 1
        assert added[0].name == "数学库"
        assert str(added[0].dao_version) == ">=1.2.0"
        assert len(repository.query("数学库")) == 1

    def test_无已安装包时索引为空(self, tmp_path, monkeypatch):
        monkeypatch.setattr(Path, "home", classmethod(lambda cls: tmp_path))
        repository = RepositoryIndex(root=tmp_path / "仓库")

        assert repository.sync_installed(project_dir=str(tmp_path / "空项目")) == []
        assert len(repository) == 0


class TestIndexMaintenance:
    def test_删除与清空索引(self, tmp_path):
        repository = RepositoryIndex(root=tmp_path / "仓库")
        repository.add(make_archive(tmp_path, "数学库", "1.0.0"))
        repository.add(make_archive(tmp_path, "数学库", "2.0.0"))

        assert repository.remove("数学库", "1.0.0") is True
        assert repository.remove("数学库", "1.0.0") is False
        repository.clear()
        assert len(repository) == 0
        assert (tmp_path / "仓库" / INDEX_FILENAME).is_file()

    def test_索引文件持久化后可重新加载(self, tmp_path):
        root = tmp_path / "仓库"
        RepositoryIndex(root=root).add(make_archive(tmp_path, "数学库", "1.2.0"))

        reloaded = RepositoryIndex(root=root)
        entries = reloaded.query("数学库")

        assert len(entries) == 1
        assert isinstance(entries[0], IndexEntry)
        assert entries[0].version == Version.parse("1.2.0")

    def test_损坏索引报中文错误(self, tmp_path):
        root = tmp_path / "仓库"
        root.mkdir()
        (root / INDEX_FILENAME).write_text("不是 JSON", encoding="utf-8")
        with pytest.raises(ValueError, match="索引"):
            RepositoryIndex(root=root).query()
