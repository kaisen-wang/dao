from __future__ import annotations

import os
from dataclasses import dataclass

from .config import PackageConfig
from .version import Version


@dataclass
class ResolvedPackage:
    name: str
    version: Version
    path: str
    config: PackageConfig | None = None


class PackageResolver:
    def __init__(self, search_paths: list[str] | None = None):
        self.search_paths = search_paths or []
        self._resolved: dict[str, ResolvedPackage] = {}

    def resolve(self, name: str, constraint=None) -> ResolvedPackage | None:
        if name in self._resolved:
            return self._resolved[name]

        for search_path in self.search_paths:
            pkg_dir = os.path.join(search_path, name)
            if not os.path.isdir(pkg_dir):
                continue

            config_path = os.path.join(pkg_dir, "道.配置")
            if not os.path.exists(config_path):
                continue

            config = PackageConfig.from_file(config_path)
            if config.version is None:
                continue

            if constraint and not constraint.matches(config.version):
                continue

            resolved = ResolvedPackage(
                name=name,
                version=config.version,
                path=pkg_dir,
                config=config,
            )
            self._resolved[name] = resolved
            return resolved

        return None

    def resolve_all(self, config: PackageConfig) -> list[ResolvedPackage]:
        results = []
        for dep in config.dependencies:
            resolved = self.resolve(dep.name, dep.constraint)
            if resolved is None:
                raise RuntimeError(
                    f"无法解析依赖 '{dep}'，在搜索路径中未找到匹配的包"
                )
            results.append(resolved)

            if resolved.config:
                sub_results = self.resolve_all(resolved.config)
                for sr in sub_results:
                    if sr.name not in {r.name for r in results}:
                        results.append(sr)

        return results

    def get_module_paths(self, config: PackageConfig) -> list[str]:
        resolved = self.resolve_all(config)
        return [r.path for r in resolved]