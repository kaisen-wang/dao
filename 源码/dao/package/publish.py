"""发布 API：把项目打包并登记到本地仓库。

本模块只负责**本地仓库**分发闭环，不接入真实网络与账号；远端上传通过
:class:`RemotePublisher` 协议预留，调用方可注入自己的实现。
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from .config import PackageConfig
from .packer import CONFIG_FILENAME, check_dao_version, pack_project
from .repository import IndexEntry, RepositoryIndex
from .version import Version


class RemotePublisher(Protocol):
    """远端发布接口（预留）。

    实现方可把归档上传到自己的镜像/账号体系，并返回远端引用（如 URL）。
    """

    def publish(self, archive_path: str, entry: IndexEntry) -> str:
        """上传归档并返回远端引用；不上传时可返回空字符串。"""
        ...


class LocalOnlyPublisher:
    """默认远端实现：不联网，仅返回空引用。"""

    def publish(self, archive_path: str, entry: IndexEntry) -> str:
        return ""


@dataclass
class PublishResult:
    name: str
    version: Version
    archive_path: str
    entry: IndexEntry
    remote_ref: str = ""

    def __str__(self) -> str:
        remote = f"，远端 {self.remote_ref}" if self.remote_ref else ""
        return f"已发布 {self.name} {self.version} → {self.entry.path}{remote}"


def publish(
    project_dir: str,
    output: str | None = None,
    repository: RepositoryIndex | None = None,
    remote: RemotePublisher | None = None,
    check_version: bool = True,
) -> PublishResult:
    """打包项目并按索引契约写入本地仓库。

    :param project_dir: 项目根目录，必须含有效的 ``道.配置``
    :param output: ``.道包`` 输出路径；省略时写到项目根目录
    :param repository: 目标本地仓库；省略时使用 ``~/.道/仓库/``
    :param remote: 可选的远端发布器；缺省时不执行任何网络操作
    :param check_version: 是否校验「道版本」与当前解释器兼容
    :return: :class:`PublishResult`（归档路径、索引条目、远端引用）
    :raises ValueError: 配置缺失/无效、道版本不兼容或没有可打包的源文件
    """
    config_path = Path(project_dir).expanduser().resolve() / CONFIG_FILENAME
    if not config_path.is_file():
        raise ValueError(f"项目目录 '{project_dir}' 缺少 {CONFIG_FILENAME} 配置文件")
    config = PackageConfig.from_file(str(config_path))
    if check_version:
        check_dao_version(config)

    archive_path = pack_project(project_dir, output)
    repo = repository if repository is not None else RepositoryIndex()
    entry = repo.add(archive_path, source=str(Path(project_dir).expanduser().resolve()))
    remote_ref = remote.publish(archive_path, entry) if remote is not None else ""

    return PublishResult(
        name=config.name,
        version=config.version,
        archive_path=archive_path,
        entry=entry,
        remote_ref=remote_ref,
    )
