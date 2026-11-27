"""依赖解析与冲突求解。

在原有「按搜索路径查找并去重」的基础上，增加了：

* 同一包的多条版本约束求交（``^ ~ >= <= > < ==``，遵循 SemVer 预发布规则）；
* 从本地仓库索引发现多个候选版本，选取同时满足全部约束的最高版本；
* 无法同时满足时抛出中文 :class:`DependencyConflictError`，并明确指出
  互相冲突的两个约束。
"""

from __future__ import annotations

import os
from dataclasses import dataclass

from .config import PackageConfig
from .version import Version, VersionConstraint

CONFIG_FILENAME = "道.配置"


class DependencyConflictError(RuntimeError):
    """同一依赖存在互相矛盾的版本约束。"""

    def __init__(
        self,
        name: str,
        first: VersionConstraint,
        second: VersionConstraint,
        detail: str = "",
    ):
        self.name = name
        self.first = first
        self.second = second
        message = (
            f"依赖冲突：包 '{name}' 同时要求 {first} 与 {second}，"
            f"没有版本能同时满足这两个约束"
        )
        if detail:
            message += f"（{detail}）"
        super().__init__(message)


class DependencyNotFoundError(RuntimeError):
    """在搜索路径与本地仓库中都找不到满足约束的版本。"""

    def __init__(self, name: str, constraints: list[VersionConstraint]):
        self.name = name
        self.constraints = constraints
        described = "、".join(str(item) for item in constraints) if constraints else "任意版本"
        super().__init__(
            f"无法解析依赖 '{name}'：要求 {described}，"
            f"但搜索路径与本地仓库中均未找到匹配的版本"
        )


@dataclass
class ResolvedPackage:
    name: str
    version: Version
    path: str
    config: PackageConfig | None = None
    source: str = ""

    def __str__(self) -> str:
        suffix = f"（来源 {self.source}）" if self.source else ""
        return f"{self.name} {self.version}{suffix}"


class PackageResolver:
    """在搜索路径与（可选的）本地仓库索引中解析依赖。

    :param search_paths: 依次查找的目录，通常为 ``项目/道包`` 与 ``~/.道/包``
    :param index: :class:`~dao.package.repository.RepositoryIndex`，用于提供
        同一包的多个候选版本；省略时退化为原来的本地目录查找
    """

    def __init__(self, search_paths: list[str] | None = None, index=None):
        self.search_paths = list(search_paths or [])
        self.index = index
        self._resolved: dict[str, ResolvedPackage] = {}
        self._candidates_cache: dict[str, list[ResolvedPackage]] = {}

    # -- 候选版本发现 -------------------------------------------------
    def _dir_candidates(self, name: str) -> list[ResolvedPackage]:
        result: list[ResolvedPackage] = []
        for search_path in self.search_paths:
            package_dir = os.path.join(search_path, name)
            config_path = os.path.join(package_dir, CONFIG_FILENAME)
            if not os.path.isdir(package_dir) or not os.path.isfile(config_path):
                continue
            config = PackageConfig.from_file(config_path)
            if config.version is None:
                continue
            result.append(
                ResolvedPackage(
                    name=name,
                    version=config.version,
                    path=package_dir,
                    config=config,
                    source=package_dir,
                )
            )
        return result

    def _index_candidates(self, name: str) -> list[ResolvedPackage]:
        if self.index is None:
            return []
        result: list[ResolvedPackage] = []
        for entry in self.index.query(name=name):
            config = entry.to_config()
            if config.version is None:
                continue
            result.append(
                ResolvedPackage(
                    name=name,
                    version=entry.version,
                    path=entry.path,
                    config=config,
                    source=entry.source or entry.path,
                )
            )
        return result

    def candidates(self, name: str) -> list[ResolvedPackage]:
        """返回某包的所有候选版本，按版本从高到低排序并去重。"""
        if name not in self._candidates_cache:
            unique: dict[str, ResolvedPackage] = {}
            # 搜索路径中先出现的目录优先（项目 道包/ 先于全局 ~/.道/包/）。
            for candidate in self._dir_candidates(name):
                unique.setdefault(str(candidate.version), candidate)
            # 同一版本若索引里也有归档，优先用索引条目：归档可直接用于安装。
            for candidate in self._index_candidates(name):
                unique[str(candidate.version)] = candidate
            self._candidates_cache[name] = sorted(
                unique.values(), key=lambda item: item.version, reverse=True
            )
        return list(self._candidates_cache[name])

    def invalidate_cache(self) -> None:
        """索引或搜索路径变化后调用，重新发现候选版本。"""
        self._candidates_cache.clear()
        self._resolved.clear()

    # -- 约束求交与冲突检测 --------------------------------------------
    @staticmethod
    def _matches_all(version: Version, constraints: list[VersionConstraint]) -> bool:
        return all(constraint.matches(version) for constraint in constraints)

    def _probe_versions(
        self,
        constraints: list[VersionConstraint],
        candidates: list[ResolvedPackage],
    ) -> list[Version]:
        """构造用于判定约束交集是否为空的探测版本集合。"""
        probes = {constraint.version for constraint in constraints}
        probes.update(candidate.version for candidate in candidates)
        for constraint in constraints:
            version = constraint.version
            probes.add(Version(version.major, version.minor, version.patch + 1))
            probes.add(Version(version.major, version.minor + 1, 0))
            probes.add(Version(version.major + 1, 0, 0))
        return list(probes)

    def _find_conflict_pair(
        self,
        constraints: list[VersionConstraint],
        candidates: list[ResolvedPackage],
    ) -> tuple[VersionConstraint | None, VersionConstraint | None]:
        """找出一对 mutually incompatible 的约束；找不到返回 ``(None, None)``。"""
        probes = self._probe_versions(constraints, candidates)
        for i, first in enumerate(constraints):
            for second in constraints[i + 1:]:
                if not any(self._matches_all(probe, [first, second]) for probe in probes):
                    return first, second
        return None, None

    def resolve_best(
        self,
        name: str,
        constraints: list[VersionConstraint] | tuple[VersionConstraint, ...],
    ) -> ResolvedPackage | None:
        """选取同时满足所有约束的最高版本。

        :raises DependencyConflictError: 约束之间互相矛盾
        """
        active = [constraint for constraint in constraints if constraint is not None]
        candidates = self.candidates(name)
        if not active:
            return candidates[0] if candidates else None

        matched = [item for item in candidates if self._matches_all(item.version, active)]
        if matched:
            best = matched[0]
            self._resolved[name] = best
            return best

        first, second = self._find_conflict_pair(active, candidates)
        if first is not None and second is not None:
            raise DependencyConflictError(name, first, second)
        if len(active) > 1:
            raise DependencyConflictError(
                name, active[0], active[-1], detail="多条约束叠加后无可用版本"
            )
        return None

    # -- 对外解析接口 -------------------------------------------------
    def resolve(self, name: str, constraint=None) -> ResolvedPackage | None:
        """解析单个包。

        ``constraint`` 可是单个约束、约束列表或 ``None``；传入列表时使用
        冲突求交后的最高版本。
        """
        if isinstance(constraint, (list, tuple)):
            return self.resolve_best(name, constraint)

        cached = self._resolved.get(name)
        if cached is not None and (
            constraint is None or self._matches_all(cached.version, [constraint])
        ):
            return cached

        for candidate in self.candidates(name):
            if constraint is None or self._matches_all(candidate.version, [constraint]):
                self._resolved[name] = candidate
                return candidate
        return None

    def _collect_constraints(
        self, config: PackageConfig
    ) -> dict[str, list[VersionConstraint]]:
        """遍历依赖图，汇总每个包名上的全部约束。"""
        constraints: dict[str, list[VersionConstraint]] = {}
        queue: list[PackageConfig] = [config]
        visited: set[int] = set()
        while queue:
            current = queue.pop(0)
            if id(current) in visited:
                continue
            visited.add(id(current))
            for dependency in current.dependencies:
                bucket = constraints.setdefault(dependency.name, [])
                if dependency.constraint is not None:
                    bucket.append(dependency.constraint)
                for candidate in self.candidates(dependency.name):
                    if candidate.config is not None and id(candidate.config) not in visited:
                        queue.append(candidate.config)
        return constraints

    def resolve_all(self, config: PackageConfig) -> list[ResolvedPackage]:
        """解析项目声明的全部（含传递）依赖，并求解版本冲突。

        :raises DependencyConflictError: 存在互相矛盾的约束
        :raises DependencyNotFoundError: 找不到满足约束的版本
        """
        constraints = self._collect_constraints(config)
        results: list[ResolvedPackage] = []
        for name, active in constraints.items():
            resolved = self.resolve_best(name, active)
            if resolved is None:
                raise DependencyNotFoundError(name, active)
            results.append(resolved)
        return results

    def get_module_paths(self, config: PackageConfig) -> list[str]:
        """返回解析后各依赖包的目录路径。"""
        return [item.path for item in self.resolve_all(config)]
