"""发布 API 测试：写入本地仓库、远端钩子预留、版本校验与错误路径。"""

import os
import sys
from pathlib import Path

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from dao.package.packer import CONFIG_FILENAME
from dao.package.publish import LocalOnlyPublisher, PublishResult, publish
from dao.package.repository import RepositoryIndex
from dao.package.version import Version


def make_project(root: Path, name: str, version: str, dao_version: str = "") -> Path:
    project = root / f"项目-{name}-{version}"
    project.mkdir(parents=True, exist_ok=True)
    dao_line = f"道版本 {dao_version}\n" if dao_version else ""
    (project / CONFIG_FILENAME).write_text(
        f"名称 {name}\n版本 {version}\n{dao_line}入口 主程序\n", encoding="utf-8"
    )
    (project / "主程序.道").write_text("导出 函数 测试()\n    返回 1\n", encoding="utf-8")
    return project


class TestPublish:
    def test_发布后写入本地仓库索引(self, tmp_path):
        project = make_project(tmp_path, "数学库", "1.2.0")
        repository = RepositoryIndex(root=tmp_path / "仓库")

        result = publish(str(project), repository=repository)

        assert isinstance(result, PublishResult)
        assert result.name == "数学库"
        assert result.version == Version.parse("1.2.0")
        assert Path(result.archive_path).is_file()
        assert result.entry.path == str(Path(repository.root / "包" / "数学库" / Path(result.archive_path).name))
        assert result.remote_ref == ""
        assert len(repository.query("数学库")) == 1

    def test_远端发布器被调用并保留引用(self, tmp_path):
        project = make_project(tmp_path, "数学库", "1.2.0")
        repository = RepositoryIndex(root=tmp_path / "仓库")

        class FakeRemote:
            def __init__(self):
                self.calls = []

            def publish(self, archive_path, entry):
                self.calls.append((archive_path, entry))
                return "https://example.invalid/数学库.道包"

        remote = FakeRemote()
        result = publish(str(project), repository=repository, remote=remote)

        assert len(remote.calls) == 1
        assert remote.calls[0][0] == result.archive_path
        assert remote.calls[0][1].name == "数学库"
        assert result.remote_ref == "https://example.invalid/数学库.道包"

    def test_缺省远端实现不联网(self, tmp_path):
        project = make_project(tmp_path, "数学库", "1.0.0")
        repository = RepositoryIndex(root=tmp_path / "仓库")

        result = publish(str(project), repository=repository, remote=LocalOnlyPublisher())

        assert result.remote_ref == ""

    def test_道版本不兼容时拒绝发布(self, tmp_path):
        project = make_project(tmp_path, "未来库", "1.0.0", dao_version=">=999.0.0")
        repository = RepositoryIndex(root=tmp_path / "仓库")

        with pytest.raises(ValueError, match="需要道语言版本"):
            publish(str(project), repository=repository)
        assert len(repository) == 0

    def test_可跳过道版本检查(self, tmp_path):
        project = make_project(tmp_path, "未来库", "1.0.0", dao_version=">=999.0.0")
        repository = RepositoryIndex(root=tmp_path / "仓库")

        result = publish(str(project), repository=repository, check_version=False)

        assert result.entry.version == Version.parse("1.0.0")

    def test_缺少配置时报中文错误(self, tmp_path):
        with pytest.raises(ValueError, match="道.配置"):
            publish(str(tmp_path), repository=RepositoryIndex(root=tmp_path / "仓库"))
