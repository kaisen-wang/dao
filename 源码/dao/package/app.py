"""把道语言项目打包成可运行应用。

与 :mod:`dao.package.packer` 打出的 ``.道包``（供其他项目导入的依赖包）
不同，``.道应用`` 是**自包含的可运行应用**：除项目源码与 ``道.配置`` 外，
还会把项目 ``道包/`` 下已安装的依赖一并打进去，解压后可直接用
``dao run-app`` 运行，无需先安装依赖。

归档内部结构（解压即可运行）：

    应用.配置          （应用清单：名称、版本、入口、道版本）
    道.配置            （原项目配置）
    主程序.道          （项目源码，保持相对目录结构）
    道包/<包名>/...    （已安装的依赖，保持目录结构）
"""

from __future__ import annotations

import shutil
import zipfile
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from .config import PackageConfig, VersionConstraint, resolve_entry_path
from .packer import (
    CONFIG_FILENAME,
    ROOT_DOCS,
    _validate_config,
    check_dao_version,
    collect_source_files,
)
from .version import Version

APP_SUFFIX = ".道应用"
MANIFEST_FILENAME = "应用.配置"
DEPENDENCY_DIR = "道包"


@dataclass
class AppManifest:
    """应用清单，随归档一起分发。"""

    name: str
    version: Version
    entry: str
    dao_version: VersionConstraint | None = None
    built_at: str = ""

    @classmethod
    def parse(cls, content: str) -> AppManifest:
        values: dict[str, str] = {}
        for raw_line in content.strip().splitlines():
            line = raw_line.strip()
            if not line or line.startswith("//"):
                continue
            parts = line.split(None, 1)
            if len(parts) != 2:
                raise ValueError(f"应用清单格式错误：{line}")
            values[parts[0]] = parts[1]

        name = values.get("名称", "").strip()
        if not name:
            raise ValueError("应用清单缺少「名称」")
        version_str = values.get("版本", "").strip()
        if not version_str:
            raise ValueError("应用清单缺少「版本」")
        entry = values.get("入口", "").strip()
        if not entry:
            raise ValueError("应用清单缺少「入口」")

        dao_version = None
        if values.get("道版本"):
            dao_version = VersionConstraint.parse(values["道版本"])

        return cls(
            name=name,
            version=Version.parse(version_str),
            entry=entry,
            dao_version=dao_version,
            built_at=values.get("打包时间", ""),
        )

    def __str__(self) -> str:
        lines = [
            f"名称 {self.name}",
            f"版本 {self.version}",
            f"入口 {self.entry}",
        ]
        if self.dao_version:
            lines.append(f"道版本 {self.dao_version}")
        if self.built_at:
            lines.append(f"打包时间 {self.built_at}")
        return "\n".join(lines)


def check_app_dao_version(
    manifest: AppManifest,
    current_version: str | None = None,
) -> None:
    """校验应用声明的「道版本」与当前解释器版本是否兼容。"""
    check_dao_version(
        PackageConfig(name=manifest.name, dao_version=manifest.dao_version),
        current_version,
    )


def _safe_member(name: str) -> str:
    """校验归档成员路径，防止路径穿越。"""
    normalized = name.replace("\\", "/")
    parts = normalized.split("/")
    if not normalized or normalized.startswith("/") or ".." in parts or ":" in normalized:
        raise ValueError(f"应用包内存在不安全的路径：{name}")
    return normalized


def _app_archive_name(name: str, version: Version) -> str:
    return f"{name}-{version}{APP_SUFFIX}"


def build_app(
    project_dir: str,
    output: str | None = None,
    include_deps: bool = True,
) -> str:
    """把一个道语言项目打成 ``.道应用`` 归档。

    :param project_dir: 项目根目录，必须含有效的 ``道.配置`` 与「入口」
    :param output: 输出文件路径或目录，默认写到项目根目录
    :param include_deps: 是否把 ``道包/`` 下已安装的依赖一并打入
    :return: 生成归档的绝对路径
    :raises ValueError: 配置无效、入口缺失或没有可打包的源文件
    """
    project = Path(project_dir).resolve()
    config_path = project / CONFIG_FILENAME
    if not config_path.is_file():
        raise ValueError(f"项目目录 '{project}' 缺少 {CONFIG_FILENAME} 配置文件")

    config = PackageConfig.from_file(str(config_path))
    _validate_config(config)

    entry = (config.entry or "").strip()
    if not entry:
        raise ValueError(f"{CONFIG_FILENAME} 缺少「入口」配置")
    entry_path = Path(resolve_entry_path(str(project), entry))
    if not entry_path.is_file():
        raise ValueError(f"入口文件不存在：{entry_path}")

    files = collect_source_files(str(project))
    if not any(rel.endswith(".道") for _, rel in files):
        raise ValueError(f"项目 '{project}' 中没有可打包的 .道 源文件")

    if include_deps:
        dep_root = project / DEPENDENCY_DIR
        if dep_root.is_dir():
            for path in sorted(dep_root.rglob("*")):
                if not path.is_file():
                    continue
                if path.suffix == ".道" or path.name in (CONFIG_FILENAME, *ROOT_DOCS):
                    files.append((path, path.relative_to(project).as_posix()))

    # 同一相对路径只保留一份
    unique: list[tuple[Path, str]] = []
    seen: set[str] = set()
    for source, rel in files:
        if rel not in seen:
            seen.add(rel)
            unique.append((source, rel))

    if output:
        output_path = Path(output).expanduser().resolve()
        if output_path.is_dir() or output_path.suffix != APP_SUFFIX:
            output_path = output_path / _app_archive_name(config.name, config.version)
    else:
        output_path = project / _app_archive_name(config.name, config.version)

    manifest = AppManifest(
        name=config.name,
        version=config.version,
        entry=config.entry,
        dao_version=config.dao_version,
        built_at=datetime.now().isoformat(timespec="seconds"),
    )

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(output_path, "w", zipfile.ZIP_DEFLATED) as archive:
        for source, rel in unique:
            archive.write(source, _safe_member(rel))
        archive.writestr(MANIFEST_FILENAME, str(manifest))

    return str(output_path)


def inspect_app(archive_path: str) -> AppManifest:
    """读取并校验一个 ``.道应用`` 归档，返回应用清单。"""
    archive = Path(archive_path).expanduser().resolve()
    if not archive.is_file():
        raise ValueError(f"应用包文件不存在：{archive_path}")
    if not zipfile.is_zipfile(archive):
        raise ValueError(f"不是有效的 .道应用 归档：{archive_path}")

    with zipfile.ZipFile(archive) as zf:
        members = zf.namelist()
        for member in members:
            _safe_member(member)
        if MANIFEST_FILENAME not in members:
            raise ValueError(f"应用包内缺少 {MANIFEST_FILENAME} 清单文件")
        if CONFIG_FILENAME not in members:
            raise ValueError(f"应用包内缺少 {CONFIG_FILENAME} 配置文件")
        content = zf.read(MANIFEST_FILENAME).decode("utf-8")

    return AppManifest.parse(content)


def extract_app(archive_path: str, target_dir: str) -> str:
    """把应用包解压到指定目录，返回该目录的绝对路径。"""
    archive = Path(archive_path).expanduser().resolve()
    inspect_app(str(archive))

    target = Path(target_dir).resolve()
    target.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(archive) as zf:
        for member in zf.infolist():
            rel = _safe_member(member.filename)
            destination = target / rel
            if member.is_dir():
                destination.mkdir(parents=True, exist_ok=True)
            else:
                destination.parent.mkdir(parents=True, exist_ok=True)
                with zf.open(member) as source, open(destination, "wb") as out:
                    shutil.copyfileobj(source, out)

    return str(target)
