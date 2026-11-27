"""本地包仓库索引（``~/.道/仓库/``）。

索引是一个 UTF-8 JSON 文件 ``索引.json``，归档副本存放在 ``仓库/包/<名称>/``
下，条目契约如下（中文键名）::

    {
      "版本": 1,
      "包": {
        "数学库": [
          {
            "名称": "数学库",
            "版本": "1.2.0",
            "路径": "/home/.../.道/仓库/包/数学库/数学库-1.2.0.道包",
            "来源": "/原/项目/数学库-1.2.0.道包",
            "道版本": ">=1.2.0",
            "入口": "主程序",
            "依赖": ["工具库 >=1.0.0"],
            "发布时间": "2026-11-27T10:00:00"
          }
        ]
      }
    }

索引由 :meth:`RepositoryIndex.add` / :meth:`RepositoryIndex.add_installed`
写入，可由 :meth:`RepositoryIndex.sync_installed` 从已安装包自动建立；
:meth:`RepositoryIndex.query` 支持按名称与版本范围（字符串或
:class:`~dao.package.version.VersionConstraint`）查询。
"""

from __future__ import annotations

import json
import os
import shutil
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

from .config import Dependency, PackageConfig
from .packer import CONFIG_FILENAME, inspect_package
from .version import Version, VersionConstraint

INDEX_FILENAME = "索引.json"
STORE_DIR = "包"
INDEX_VERSION = 1


@dataclass
class IndexEntry:
    """仓库索引中的一条包记录。"""

    name: str
    version: Version
    path: str
    source: str = ""
    dao_version: VersionConstraint | None = None
    entry: str = ""
    dependencies: list[str] = field(default_factory=list)
    published_at: str = ""

    def to_dict(self) -> dict:
        return {
            "名称": self.name,
            "版本": str(self.version),
            "路径": self.path,
            "来源": self.source,
            "道版本": str(self.dao_version) if self.dao_version else "",
            "入口": self.entry,
            "依赖": list(self.dependencies),
            "发布时间": self.published_at,
        }

    @classmethod
    def from_dict(cls, data: dict) -> IndexEntry:
        name = str(data.get("名称", ""))
        version_text = str(data.get("版本", ""))
        if not name or not version_text:
            raise ValueError("仓库索引条目缺少「名称」或「版本」")
        dao_version_text = str(data.get("道版本", ""))
        return cls(
            name=name,
            version=Version.parse(version_text),
            path=str(data.get("路径", "")),
            source=str(data.get("来源", "")),
            dao_version=VersionConstraint.parse(dao_version_text) if dao_version_text else None,
            entry=str(data.get("入口", "")),
            dependencies=[str(item) for item in data.get("依赖", [])],
            published_at=str(data.get("发布时间", "")),
        )

    def to_config(self) -> PackageConfig:
        """按索引契约还原包元数据，供依赖求解使用。"""
        return PackageConfig(
            name=self.name,
            version=self.version,
            entry=self.entry,
            dao_version=self.dao_version,
            dependencies=[Dependency.parse(text) for text in self.dependencies],
        )

    def __str__(self) -> str:
        return f"{self.name} {self.version}"


class RepositoryIndex:
    """可查询的本地包仓库索引。

    :param root: 仓库根目录；省略时使用 ``~/.道/仓库/``
    """

    def __init__(self, root: str | os.PathLike[str] | None = None):
        self.root = (
            Path(root).expanduser().resolve()
            if root is not None
            else Path.home() / ".道" / "仓库"
        )
        self.index_path = self.root / INDEX_FILENAME
        self._data: dict | None = None

    @property
    def data(self) -> dict:
        if self._data is None:
            self._data = self._load()
        return self._data

    def _load(self) -> dict:
        if not self.index_path.is_file():
            return {"版本": INDEX_VERSION, "包": {}}
        try:
            data = json.loads(self.index_path.read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise ValueError(f"本地仓库索引 {self.index_path} 读取失败或格式损坏：{exc}") from exc
        if not isinstance(data, dict):
            raise TypeError(f"本地仓库索引 {self.index_path} 格式错误：顶层必须是对象")
        if data.get("版本") != INDEX_VERSION:
            raise ValueError(
                f"本地仓库索引版本 {data.get('版本')} 不兼容，"
                f"当前支持版本 {INDEX_VERSION}"
            )
        if not isinstance(data.get("包"), dict):
            raise TypeError(f"本地仓库索引 {self.index_path} 格式错误：「包」必须是对象")
        return data

    def reload(self) -> None:
        """丢弃缓存并重新读取索引文件。"""
        self._data = None

    def save(self) -> str:
        self.root.mkdir(parents=True, exist_ok=True)
        text = json.dumps(self.data, ensure_ascii=False, indent=2) + "\n"
        self.index_path.write_text(text, encoding="utf-8")
        return str(self.index_path)

    def _put(self, entry: IndexEntry) -> IndexEntry:
        bucket = self.data["包"].setdefault(entry.name, [])
        for position, old in enumerate(bucket):
            if Version.parse(str(old.get("版本", ""))) == entry.version:
                bucket[position] = entry.to_dict()
                break
        else:
            bucket.append(entry.to_dict())
        self.save()
        return entry

    def add(self, archive_path: str, source: str = "") -> IndexEntry:
        """把一个 ``.道包`` 归档登记进索引，并把归档副本存入仓库。

        :raises ValueError: 归档无效或元数据不完整
        """
        config = inspect_package(archive_path)
        archive = Path(archive_path).expanduser().resolve()
        stored = self.root / STORE_DIR / config.name / archive.name
        if stored.resolve() != archive:
            stored.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(archive, stored)
        entry = IndexEntry(
            name=config.name,
            version=config.version,
            path=str(stored),
            source=source or str(archive),
            dao_version=config.dao_version,
            entry=config.entry,
            dependencies=[str(dep) for dep in config.dependencies],
            published_at=datetime.now().isoformat(timespec="seconds"),
        )
        return self._put(entry)

    def add_installed(self, package_dir: str, source: str = "已安装") -> IndexEntry:
        """把一个已安装包的目录登记进索引。"""
        directory = Path(package_dir).expanduser().resolve()
        config_path = directory / CONFIG_FILENAME
        if not config_path.is_file():
            raise ValueError(f"已安装包目录缺少 {CONFIG_FILENAME}：{directory}")
        config = PackageConfig.from_file(str(config_path))
        if not config.name or config.version is None:
            raise ValueError(f"已安装包元数据不完整：{directory}")
        entry = IndexEntry(
            name=config.name,
            version=config.version,
            path=str(directory),
            source=source or str(directory),
            dao_version=config.dao_version,
            entry=config.entry,
            dependencies=[str(dep) for dep in config.dependencies],
            published_at=datetime.now().isoformat(timespec="seconds"),
        )
        return self._put(entry)

    def sync_installed(
        self,
        project_dir: str | os.PathLike[str] | None = None,
        global_install: bool = True,
    ) -> list[IndexEntry]:
        """从已安装的包自动建立/更新索引，返回本次登记的条目。

        :param project_dir: 同时扫描该项目的 ``道包/`` 目录
        :param global_install: 是否扫描 ``~/.道/包/`` 全局目录
        """
        roots: list[Path] = []
        if global_install:
            roots.append(Path.home() / ".道" / "包")
        if project_dir is not None:
            roots.append(Path(project_dir).expanduser().resolve() / "道包")

        added: list[IndexEntry] = []
        seen: set[str] = set()
        for root in roots:
            if not root.is_dir():
                continue
            for child in sorted(root.iterdir(), key=lambda p: p.name):
                if not child.is_dir() or not (child / CONFIG_FILENAME).is_file():
                    continue
                marker = str(child.resolve())
                if marker in seen:
                    continue
                seen.add(marker)
                added.append(self.add_installed(str(child)))
        return added

    @staticmethod
    def _coerce_constraint(constraint) -> VersionConstraint | None:
        if constraint is None:
            return None
        if isinstance(constraint, VersionConstraint):
            return constraint
        if isinstance(constraint, Version):
            return VersionConstraint("==", constraint)
        if isinstance(constraint, str):
            return VersionConstraint.parse(constraint)
        raise TypeError(f"不支持的版本约束类型：{type(constraint).__name__}")

    def query(self, name: str | None = None, constraint=None) -> list[IndexEntry]:
        """按名称与版本范围查询，结果按版本从高到低排序。

        :param name: 包名；省略时返回所有包
        :param constraint: ``VersionConstraint`` / 版本字符串 / ``Version``
        """
        parsed = self._coerce_constraint(constraint)
        result: list[IndexEntry] = []
        for package_name, items in self.data["包"].items():
            if name is not None and package_name != name:
                continue
            for raw in items:
                entry = IndexEntry.from_dict(raw)
                if parsed is None or parsed.matches(entry.version):
                    result.append(entry)
        result.sort(key=lambda item: item.version, reverse=True)
        return result

    def versions(self, name: str) -> list[Version]:
        """返回指定包的所有已索引版本（从高到低）。"""
        return [entry.version for entry in self.query(name)]

    def get(self, name: str, version: Version | str) -> IndexEntry | None:
        target = Version.parse(version) if isinstance(version, str) else version
        for entry in self.query(name, VersionConstraint("==", target)):
            if entry.version == target:
                return entry
        return None

    def remove(self, name: str, version: Version | str) -> bool:
        """删除一个索引条目；返回是否确有删除。"""
        target = Version.parse(version) if isinstance(version, str) else version
        bucket = self.data["包"].get(name)
        if not bucket:
            return False
        kept = [raw for raw in bucket if Version.parse(str(raw.get("版本", ""))) != target]
        if len(kept) == len(bucket):
            return False
        if kept:
            self.data["包"][name] = kept
        else:
            del self.data["包"][name]
        self.save()
        return True

    def clear(self) -> None:
        """清空索引（不删除已存放的归档副本）。"""
        self._data = {"版本": INDEX_VERSION, "包": {}}
        self.save()

    def __len__(self) -> int:
        return sum(len(items) for items in self.data["包"].values())

    def __str__(self) -> str:
        return f"本地仓库 {self.root}（{len(self)} 个包版本）"


# 中文别名，便于在道语言侧按中文习惯引用。
本地仓库 = RepositoryIndex
