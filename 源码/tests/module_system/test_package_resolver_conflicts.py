"""依赖冲突求解测试：多约束求交、传递冲突、中文错误与索引候选。"""

import os
import sys
from pathlib import Path

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from dao.package.config import PackageConfig
from dao.package.packer import pack_project
from dao.package.repository import RepositoryIndex
from dao.package.resolver import (
    DependencyConflictError,
    DependencyNotFoundError,
    PackageResolver,
)
from dao.package.version import Version, VersionConstraint


def make_package(root: Path, name: str, version: str, deps: list[str] | None = None) -> Path:
    directory = root / name
    directory.mkdir(parents=True, exist_ok=True)
    lines = [f"名称 {name}", f"版本 {version}", "入口 主程序"]
    if deps:
        lines.append("依赖")
        lines.extend(f"    {dep}" for dep in deps)
    (directory / "道.配置").write_text("\n".join(lines) + "\n", encoding="utf-8")
    (directory / "主程序.道").write_text("导出 函数 测试()\n    返回 1\n", encoding="utf-8")
    return directory


def make_archive(root: Path, name: str, version: str) -> str:
    project = root / f"源码-{name}-{version}"
    project.mkdir(parents=True, exist_ok=True)
    (project / "道.配置").write_text(f"名称 {name}\n版本 {version}\n入口 主程序\n", encoding="utf-8")
    (project / "主程序.道").write_text("导出 函数 测试()\n    返回 1\n", encoding="utf-8")
    return pack_project(str(project))


class TestConstraintIntersection:
    def test_两条精确约束冲突并指出双方(self, tmp_path):
        make_package(tmp_path, "日志库", "1.0.0")
        resolver = PackageResolver(search_paths=[str(tmp_path)])
        first = VersionConstraint.parse("1.0.0")
        second = VersionConstraint.parse("2.0.0")

        with pytest.raises(DependencyConflictError) as exc_info:
            resolver.resolve_best("日志库", [first, second])

        message = str(exc_info.value)
        assert "依赖冲突" in message
        assert "日志库" in message
        assert "1.0.0" in message and "2.0.0" in message
        assert exc_info.value.first == first and exc_info.value.second == second

    def test_caret与下界约束冲突(self, tmp_path):
        make_package(tmp_path, "数据库", "1.5.0")
        resolver = PackageResolver(search_paths=[str(tmp_path)])

        with pytest.raises(DependencyConflictError, match="依赖冲突"):
            resolver.resolve_best(
                "数据库",
                [VersionConstraint.parse("^1.5.0"), VersionConstraint.parse(">=2.0.0")],
            )

    def test_多条约束求交后取最高匹配版本(self, tmp_path):
        search_paths = []
        for number, version in enumerate(("1.4.0", "1.5.0", "1.6.0")):
            root = tmp_path / f"源{number}"
            root.mkdir()
            make_package(root, "网络库", version)
            search_paths.append(str(root))
        resolver = PackageResolver(search_paths=search_paths)

        resolved = resolver.resolve_best(
            "网络库",
            [VersionConstraint.parse(">=1.4.0"), VersionConstraint.parse("<1.6.0")],
        )

        assert resolved is not None
        assert resolved.version == Version.parse("1.5.0")

    def test_无匹配版本报找不到而非冲突(self, tmp_path):
        make_package(tmp_path, "工具库", "0.9.0")
        resolver = PackageResolver(search_paths=[str(tmp_path)])

        with pytest.raises(DependencyNotFoundError, match="无法解析依赖"):
            resolver.resolve_all(
                PackageConfig.parse("名称 应用\n版本 1.0.0\n依赖\n    工具库 >=1.0.0\n")
            )


class TestTransitiveConflicts:
    def test_传递依赖上的冲突可被发现(self, tmp_path):
        make_package(tmp_path, "甲", "1.0.0", deps=["公共库 >=2.0.0"])
        make_package(tmp_path, "乙", "1.0.0", deps=["公共库 <2.0.0"])
        make_package(tmp_path, "公共库", "1.5.0")
        resolver = PackageResolver(search_paths=[str(tmp_path)])
        config = PackageConfig.parse(
            "名称 应用\n版本 1.0.0\n依赖\n    甲 ^1.0.0\n    乙 ^1.0.0\n"
        )

        with pytest.raises(DependencyConflictError) as exc_info:
            resolver.resolve_all(config)

        assert "公共库" in str(exc_info.value)
        assert "依赖冲突" in str(exc_info.value)

    def test_无冲突的依赖图解析出全部包(self, tmp_path):
        make_package(tmp_path, "甲", "1.0.0", deps=["公共库 ^1.0.0"])
        make_package(tmp_path, "公共库", "1.3.0")
        resolver = PackageResolver(search_paths=[str(tmp_path)])
        config = PackageConfig.parse("名称 应用\n版本 1.0.0\n依赖\n    甲 ^1.0.0\n")

        resolved = resolver.resolve_all(config)

        assert {item.name for item in resolved} == {"甲", "公共库"}
        assert all(item.version is not None for item in resolved)


class TestRepositoryCandidates:
    def test_索引提供多版本候选并参与求交(self, tmp_path):
        repo_root = tmp_path / "仓库"
        repository = RepositoryIndex(root=repo_root)
        for version in ("1.0.0", "1.1.0", "2.0.0"):
            repository.add(make_archive(tmp_path, "缓存库", version))
        resolver = PackageResolver(index=repository)

        resolved = resolver.resolve_best(
            "缓存库", [VersionConstraint.parse(">=1.0.0"), VersionConstraint.parse("^1.0.0")]
        )

        assert resolved is not None
        assert resolved.version == Version.parse("1.1.0")
        assert resolved.source

    def test_索引与本地目录的候选合并去重(self, tmp_path):
        make_package(tmp_path, "本地库", "1.0.0")
        repository = RepositoryIndex(root=tmp_path / "仓库")
        repository.add(make_archive(tmp_path, "本地库", "1.0.0"))
        resolver = PackageResolver(search_paths=[str(tmp_path)], index=repository)

        candidates = resolver.candidates("本地库")

        assert len(candidates) == 1
