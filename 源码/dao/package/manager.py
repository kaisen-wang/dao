"""包管理层：配置读取、依赖解析、安装与锁文件维护。"""

from __future__ import annotations

import os
from pathlib import Path

from .config import PackageConfig, resolve_entry_path
from .lockfile import LockDriftError, LockFile, sha256_file  # noqa: F401 - 便于调用方从 manager 导入
from .packer import inspect_package, install_package
from .repository import IndexEntry, RepositoryIndex
from .resolver import PackageResolver
from .version import VersionConstraint


class PackageManager:
    def __init__(self, project_dir: str | None = None):
        self.project_dir = project_dir or os.getcwd()
        self._config: PackageConfig | None = None
        self._resolver: PackageResolver | None = None
        self._lock: LockFile | None = None

    @property
    def config(self) -> PackageConfig | None:
        if self._config is None:
            self._config = self._load_config()
        return self._config

    @property
    def resolver(self) -> PackageResolver:
        if self._resolver is None:
            self._resolver = self._build_resolver()
        return self._resolver

    @property
    def lock(self) -> LockFile:
        if self._lock is None:
            self._lock = LockFile(self.project_dir)
        return self._lock

    def _load_config(self) -> PackageConfig | None:
        config_path = os.path.join(self.project_dir, "道.配置")
        if not os.path.exists(config_path):
            return None
        return PackageConfig.from_file(config_path)

    def _build_resolver(self) -> PackageResolver:
        search_paths = []

        local_packages = os.path.join(self.project_dir, "道包")
        if os.path.isdir(local_packages):
            search_paths.append(local_packages)

        global_packages = os.path.join(os.path.expanduser("~"), ".道", "包")
        if os.path.isdir(global_packages):
            search_paths.append(global_packages)

        return PackageResolver(search_paths=search_paths)

    def get_dependency_paths(self) -> list[str]:
        if self.config is None:
            return []
        return self.resolver.get_module_paths(self.config)

    def resolve_module(self, module_path: str) -> str | None:
        parts = module_path.split(".")
        top_level = parts[0]

        if self.config and top_level in {dep.name for dep in self.config.dependencies}:
            resolved = self.resolver.resolve(top_level)
            if resolved:
                if len(parts) == 1:
                    entry = resolved.config.entry if resolved.config else None
                    if entry:
                        entry_path = resolve_entry_path(resolved.path, entry)
                        if os.path.isfile(entry_path):
                            return entry_path
                    return resolved.path
                else:
                    sub_path = os.path.join(resolved.path, *parts[1:]) + ".道"
                    if os.path.exists(sub_path):
                        return sub_path
                    dir_path = os.path.join(resolved.path, *parts[1:])
                    if os.path.isdir(dir_path):
                        return dir_path

        return None

    def install(
        self,
        archive_path: str | None = None,
        global_install: bool = False,
        force: bool = False,
        check_version: bool = True,
        *,
        use_lock: bool = True,
        update_lock: bool = False,
        name: str | None = None,
    ) -> str:
        """安装 ``.道包`` 归档，返回安装后的包目录。

        安装前按锁文件校验精确版本；版本漂移时抛 :class:`LockDriftError`
        并提示使用 ``--update-lock``。安装成功后把精确版本与来源写入
        ``道.锁``，使后续安装可锁定同一版本。

        ``archive_path`` 省略时可传 ``name``，从锁文件记录的来源安装。
        """
        if archive_path is None:
            if not name:
                raise ValueError("请提供 .道包 路径，或提供包名以从锁文件安装")
            return self.install_from_lock(
                name,
                global_install=global_install,
                force=force,
                check_version=check_version,
            )

        config = inspect_package(archive_path)
        if use_lock and not update_lock and config.name:
            self.lock.check(config.name, config.version)

        target = install_package(
            archive_path,
            project_dir=self.project_dir,
            global_install=global_install,
            force=force,
            check_version=check_version,
        )

        if config.name:
            source = str(Path(archive_path).expanduser().resolve())
            checksum = ""
            try:
                checksum = sha256_file(source)
            except OSError:
                pass
            self.lock.set(config.name, config.version, source=source, checksum=checksum)
            self.lock.save()

        self.invalidate_cache()
        return target

    def install_from_lock(
        self,
        name: str,
        global_install: bool = False,
        force: bool = False,
        check_version: bool = True,
    ) -> str:
        """优先按 ``道.锁`` 记录的来源与版本安装。"""
        locked = self.lock.get(name)
        if locked is None:
            raise ValueError(
                f"锁文件 道.锁 中没有 '{name}' 的记录，"
                f"请先解析依赖或执行更新锁文件（--update-lock）"
            )
        if not os.path.isfile(locked.source):
            raise ValueError(
                f"锁文件中 '{name}' 的来源不存在：{locked.source}，请更新锁文件"
            )
        if locked.checksum:
            try:
                actual = sha256_file(locked.source)
            except OSError as exc:
                raise ValueError(f"无法校验锁文件中的来源：{locked.source}（{exc}）") from exc
            if actual != locked.checksum:
                raise ValueError(
                    f"锁文件中 '{name}' 的来源校验失败：{locked.source} 已被修改，"
                    f"请更新锁文件"
                )
        return self.install(
            locked.source,
            global_install=global_install,
            force=force,
            check_version=check_version,
            use_lock=False,
        )

    def install_all(
        self,
        use_lock: bool = True,
        update_lock: bool = False,
        global_install: bool = False,
        force: bool = False,
        check_version: bool = True,
    ) -> list[str]:
        """安装项目声明的全部依赖；已有锁记录时优先按锁文件安装。

        没有锁记录时，先查询本地仓库索引取最高匹配版本；索引也没有时
        回退到搜索路径中已存在的包目录。
        """
        if self.config is None:
            return []
        repository = RepositoryIndex()
        installed: list[str] = []
        for dependency in self.config.dependencies:
            if use_lock and not update_lock and self.lock.get(dependency.name) is not None:
                target = self.install_from_lock(
                    dependency.name,
                    global_install=global_install,
                    force=force,
                    check_version=check_version,
                )
            else:
                entries = repository.query(dependency.name, dependency.constraint)
                if entries:
                    target = self.install(
                        entries[0].path,
                        global_install=global_install,
                        force=force,
                        check_version=check_version,
                        update_lock=update_lock,
                    )
                else:
                    resolved = self.resolver.resolve(dependency.name, dependency.constraint)
                    if resolved is None:
                        raise ValueError(
                            f"无法解析依赖 '{dependency.name}'："
                            f"本地仓库与搜索路径中均没有匹配的版本"
                        )
                    # 包目录已在搜索路径中，视为已安装。
                    target = resolved.path
                    if self.lock.get(dependency.name) is None:
                        self.lock.set(
                            dependency.name,
                            resolved.version,
                            source=resolved.source or resolved.path,
                        )
                        self.lock.save()
            installed.append(target)
        return installed

    def update_lock(self, repository: RepositoryIndex | None = None) -> LockFile:
        """重新解析全部依赖并刷新 ``道.锁``（含精确版本与来源）。"""
        config = self.config
        if config is None:
            raise ValueError("当前目录没有 道.配置，无法更新锁文件")
        repo = repository if repository is not None else RepositoryIndex()
        resolver = PackageResolver(search_paths=self.resolver.search_paths, index=repo)
        for resolved in resolver.resolve_all(config):
            source = resolved.source
            exact = repo.query(resolved.name, VersionConstraint("==", resolved.version))
            if exact:
                source = exact[0].path
            checksum = ""
            if source and os.path.isfile(source):
                try:
                    checksum = sha256_file(source)
                except OSError:
                    pass
            self.lock.set(resolved.name, resolved.version, source=source, checksum=checksum)
        self.lock.save()
        return self.lock

    def sync_repository(self, repository: RepositoryIndex | None = None) -> list[IndexEntry]:
        """从已安装包自动建立/更新本地仓库索引。"""
        repo = repository if repository is not None else RepositoryIndex()
        return repo.sync_installed(project_dir=self.project_dir)

    def invalidate_cache(self) -> None:
        """安装后清空配置与解析器缓存，使新依赖立即对当前解释器生效。"""
        self._config = None
        self._resolver = None
