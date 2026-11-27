"""道语言依赖包的打包与安装。

一个「依赖包」是扩展名为 ``.道包`` 的 ZIP 归档，内部结构为：

    道.配置          （包元数据，含「名称」「版本」，可选「道版本」约束）
    主程序.道        （包的源码，保持项目内的相对目录结构）
    子目录/工具.道
    README.md        （可选）
    LICENSE          （可选）

打包产物可直接用 ``dao install 包.道包`` 安装到当前项目的 ``道包/``
目录，或加 ``--global`` 安装到 ``~/.道/包/``。安装后的目录结构与
:class:`~dao.package.resolver.PackageResolver` 的搜索约定一致，因此
在项目的 ``道.配置`` 中声明依赖即可用 ``从 包名 导入 ...`` 使用。
"""

from __future__ import annotations

import os
import re
import shutil
import zipfile
from pathlib import Path

from ..version import __version__
from .config import PackageConfig
from .version import Version

CONFIG_FILENAME = "道.配置"
PACKAGE_SUFFIX = ".道包"

# 这些目录不进入依赖包：版本控制、缓存、虚拟环境、已安装依赖、构建产物。
EXCLUDED_DIRS = frozenset({
    ".git", ".hg", ".svn", ".workbuddy", ".vscode", ".idea",
    "__pycache__", ".pytest_cache", ".mypy_cache", ".ruff_cache",
    ".venv", "venv", "env", "node_modules",
    "道包", "dist", "build", "测试", "tests",
})

# 包根目录下随包携带的说明文件。
ROOT_DOCS = frozenset({"README.md", "README.道", "LICENSE", "许可证"})


def _validate_config(config: PackageConfig) -> None:
    """校验包元数据的基本字段，错误消息一律中文。"""
    if not config.name.strip():
        raise ValueError(f"{CONFIG_FILENAME} 缺少「名称」配置")
    if config.version is None:
        raise ValueError(f"{CONFIG_FILENAME} 缺少「版本」配置")
    if re.search(r'[\\/:*?"<>|]', config.name):
        raise ValueError(f"包名称含有非法字符：{config.name}")


def check_dao_version(
    config: PackageConfig,
    current_version: str | None = None,
) -> None:
    """校验包声明的「道版本」约束与当前解释器版本是否兼容。

    包未声明「道版本」时直接通过，保持旧包可用。

    :param config: 包元数据
    :param current_version: 用于测试或外部指定的当前版本，默认取解释器版本
    :raises ValueError: 当前版本不满足包的道版本约束
    """
    if config.dao_version is None:
        return

    current = Version.parse(current_version) if current_version else Version.parse(__version__)
    if config.dao_version.matches(current):
        return

    raise ValueError(
        f"包 '{config.name}' 需要道语言版本 {config.dao_version}，当前版本为 {current}"
    )


def _safe_arcname(name: str) -> str:
    """校验归档内的成员路径，防止路径穿越。"""
    normalized = name.replace("\\", "/")
    parts = normalized.split("/")
    if not normalized or normalized.startswith("/") or ".." in parts or ":" in normalized:
        raise ValueError(f"依赖包内存在不安全的路径：{name}")
    return normalized


def _archive_name(config: PackageConfig) -> str:
    return f"{config.name}-{config.version}{PACKAGE_SUFFIX}"


def collect_source_files(project_dir: str) -> list[tuple[Path, str]]:
    """收集应进入依赖包的文件。

    :return: ``(绝对路径, 归档内相对路径)`` 列表，按相对路径排序
    """
    project = Path(project_dir).resolve()
    if not project.is_dir():
        raise ValueError(f"项目目录不存在：{project_dir}")

    result: list[tuple[Path, str]] = []
    for root, dirs, files in os.walk(project):
        dirs[:] = sorted(
            d for d in dirs
            if d not in EXCLUDED_DIRS and not d.startswith(".")
        )
        for filename in sorted(files):
            path = Path(root) / filename
            rel = path.relative_to(project).as_posix()
            if (
                rel == CONFIG_FILENAME
                or path.suffix == ".道"
                or (Path(root) == project and rel in ROOT_DOCS)
            ):
                result.append((path, rel))

    result.sort(key=lambda item: item[1])
    return result


def pack_project(project_dir: str, output: str | None = None) -> str:
    """把一个道语言项目打成 ``.道包`` 归档。

    :param project_dir: 项目根目录，必须含有效的 ``道.配置``
    :param output: 输出路径；省略时写到项目根目录下的 ``名称-版本.道包``
    :return: 生成归档的绝对路径
    :raises ValueError: 配置缺失/无效，或没有可打包的源文件
    """
    project = Path(project_dir).resolve()
    config_path = project / CONFIG_FILENAME
    if not config_path.is_file():
        raise ValueError(f"项目目录 '{project}' 缺少 {CONFIG_FILENAME} 配置文件")

    config = PackageConfig.from_file(str(config_path))
    _validate_config(config)

    files = collect_source_files(str(project))
    if not any(rel.endswith(".道") for _, rel in files):
        raise ValueError(f"项目 '{project}' 中没有可打包的 .道 源文件")

    if output:
        output_path = Path(output).expanduser().resolve()
        if output_path.is_dir() or output_path.suffix != PACKAGE_SUFFIX:
            # 传入目录（含尚未创建的目录）时，在目录内生成默认文件名
            output_path = output_path / _archive_name(config)
    else:
        output_path = project / _archive_name(config)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(output_path, "w", zipfile.ZIP_DEFLATED) as archive:
        for source, rel in files:
            archive.write(source, _safe_arcname(rel))

    return str(output_path)


def inspect_package(archive_path: str) -> PackageConfig:
    """读取并校验一个 ``.道包`` 归档，返回其中的包元数据。

    :raises ValueError: 文件不存在、不是有效归档、缺少配置或路径不安全
    """
    archive = Path(archive_path).expanduser().resolve()
    if not archive.is_file():
        raise ValueError(f"依赖包文件不存在：{archive_path}")
    if not zipfile.is_zipfile(archive):
        raise ValueError(f"不是有效的 .道包 归档：{archive_path}")

    with zipfile.ZipFile(archive) as zf:
        members = zf.namelist()
        for member in members:
            _safe_arcname(member)
        if CONFIG_FILENAME not in members:
            raise ValueError(f"依赖包内缺少 {CONFIG_FILENAME} 配置文件")
        content = zf.read(CONFIG_FILENAME).decode("utf-8")

    config = PackageConfig.parse(content)
    _validate_config(config)
    return config


def _config_from_dir(package_dir: Path) -> PackageConfig | None:
    config_path = package_dir / CONFIG_FILENAME
    if not config_path.is_file():
        return None
    return PackageConfig.from_file(str(config_path))


def install_package(
    archive_path: str,
    project_dir: str | None = None,
    global_install: bool = False,
    force: bool = False,
    check_version: bool = True,
) -> str:
    """把一个 ``.道包`` 安装为本地或全局依赖。

    :param archive_path: ``.道包`` 文件路径
    :param project_dir: 本地安装的目标项目根目录，默认当前工作目录
    :param global_install: 为真时安装到 ``~/.道/包/``
    :param force: 已安装不同版本时是否强制覆盖
    :param check_version: 是否校验包声明的「道版本」与当前解释器兼容
    :return: 安装后的包目录绝对路径
    :raises ValueError: 归档无效、道版本不兼容、版本冲突或目标路径不是目录
    """
    archive = Path(archive_path).expanduser().resolve()
    config = inspect_package(str(archive))
    if check_version:
        check_dao_version(config)

    if global_install:
        target_root = Path.home() / ".道" / "包"
    else:
        target_root = Path(project_dir or os.getcwd()).resolve() / "道包"

    target = target_root / config.name
    if target.exists():
        if not target.is_dir():
            raise ValueError(f"安装目标不是目录，无法覆盖：{target}")
        installed = _config_from_dir(target)
        installed_version = str(installed.version) if installed and installed.version else "未知"
        if str(config.version) == installed_version and not force:
            return str(target)
        if not force:
            raise ValueError(
                f"包 '{config.name}' 已安装版本 {installed_version}，"
                f"要安装 {config.version} 请加 --force 强制覆盖"
            )
        shutil.rmtree(target)

    target.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(archive) as zf:
        for member in zf.infolist():
            rel = _safe_arcname(member.filename)
            destination = target / rel
            if member.is_dir():
                destination.mkdir(parents=True, exist_ok=True)
            else:
                destination.parent.mkdir(parents=True, exist_ok=True)
                with zf.open(member) as source, open(destination, "wb") as out:
                    shutil.copyfileobj(source, out)

    return str(target)


def list_installed_packages(
    project_dir: str | None = None,
    global_install: bool = False,
) -> list[tuple[str, str, str]]:
    """列出已安装的包，返回 ``(名称, 版本, 道版本约束)`` 列表。"""
    if global_install:
        target_root = Path.home() / ".道" / "包"
    else:
        target_root = Path(project_dir or os.getcwd()).resolve() / "道包"

    if not target_root.is_dir():
        return []

    result: list[tuple[str, str, str]] = []
    for child in sorted(target_root.iterdir(), key=lambda p: p.name):
        if not child.is_dir():
            continue
        config = _config_from_dir(child)
        if config is None:
            continue
        dao_version = str(config.dao_version) if config.dao_version else ""
        version = str(config.version) if config.version else "未知"
        result.append((config.name or child.name, version, dao_version))
    return result
