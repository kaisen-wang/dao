from __future__ import annotations

import os

from .config import PackageConfig, resolve_entry_path
from .packer import install_package
from .resolver import PackageResolver


class PackageManager:
    def __init__(self, project_dir: str | None = None):
        self.project_dir = project_dir or os.getcwd()
        self._config: PackageConfig | None = None
        self._resolver: PackageResolver | None = None

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
        archive_path: str,
        global_install: bool = False,
        force: bool = False,
    ) -> str:
        """安装一个 ``.道包`` 归档，返回安装后的包目录。

        安装成功后会清空配置与解析器缓存，使新依赖立即对当前解释器生效。
        """
        target = install_package(
            archive_path,
            project_dir=self.project_dir,
            global_install=global_install,
            force=force,
        )
        self.invalidate_cache()
        return target

    def invalidate_cache(self) -> None:
        self._config = None
        self._resolver = None