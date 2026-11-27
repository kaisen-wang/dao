"""依赖包打包与安装（dao/package/packer.py）测试。

覆盖：
- 打包生成 .道包 归档，并排除缓存/依赖/构建目录
- 配置校验与归档安全性校验
- 安装到本地 / 全局目录、幂等安装、版本冲突强制覆盖
- 包声明的「道版本」约束随包携带，并在安装时校验兼容性
- 安装后立即可被 PackageManager 解析并导入
"""

import os
import sys
import zipfile
from pathlib import Path

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from dao.package.config import PackageConfig
from dao.package.manager import PackageManager
from dao.package.packer import (
    CONFIG_FILENAME,
    PACKAGE_SUFFIX,
    check_dao_version,
    inspect_package,
    install_package,
    list_installed_packages,
    pack_project,
)


def make_package_project(
    root: Path,
    name: str = "数学库",
    version: str = "1.2.0",
    dao_version: str | None = None,
) -> Path:
    """构造一个最小可打包的道语言项目。"""
    project = root / name
    (project / "工具").mkdir(parents=True)
    dao_line = f"道版本 {dao_version}\n" if dao_version else ""
    (project / CONFIG_FILENAME).write_text(
        f"名称 {name}\n版本 {version}\n{dao_line}入口 主程序\n\n依赖\n\n开发依赖\n",
        encoding="utf-8",
    )
    (project / "主程序.道").write_text(
        "导出 函数 加(甲, 乙)\n    返回 甲 + 乙\n", encoding="utf-8"
    )
    (project / "工具" / "辅助.道").write_text(
        '导出 函数 助记()\n    返回 "辅助"\n', encoding="utf-8"
    )
    return project


class TestPackProject:
    def test_生成归档并包含源码与配置(self, tmp_path):
        project = make_package_project(tmp_path)
        (project / "README.md").write_text("说明", encoding="utf-8")

        archive_path = pack_project(str(project))

        assert Path(archive_path).is_file()
        assert Path(archive_path).name == f"数学库-1.2.0{PACKAGE_SUFFIX}"
        with zipfile.ZipFile(archive_path) as zf:
            names = set(zf.namelist())
        assert names == {CONFIG_FILENAME, "主程序.道", "工具/辅助.道", "README.md"}

    def test_排除缓存与依赖目录(self, tmp_path):
        project = make_package_project(tmp_path)
        (project / "道包" / "别的包").mkdir(parents=True)
        (project / "道包" / "别的包" / "内部.道").write_text("打印(1)", encoding="utf-8")
        (project / "__pycache__").mkdir()
        (project / "__pycache__" / "缓存.道").write_text("打印(2)", encoding="utf-8")
        (project / "临时.pyc").write_bytes(b"\x00")

        archive_path = pack_project(str(project))

        with zipfile.ZipFile(archive_path) as zf:
            names = set(zf.namelist())
        assert "道包/别的包/内部.道" not in names
        assert "__pycache__/缓存.道" not in names
        assert "临时.pyc" not in names

    def test_自定义输出路径(self, tmp_path):
        project = make_package_project(tmp_path)
        output_dir = tmp_path / "产物"
        archive_path = pack_project(str(project), str(output_dir))

        assert Path(archive_path) == output_dir / f"数学库-1.2.0{PACKAGE_SUFFIX}"
        assert Path(archive_path).is_file()

    def test_缺少配置报错(self, tmp_path):
        with pytest.raises(ValueError, match="道.配置"):
            pack_project(str(tmp_path))

    @pytest.mark.parametrize("content", [
        "版本 1.0.0\n",
        "名称 缺版本\n",
        "名称 坏/名字\n版本 1.0.0\n",
    ])
    def test_配置字段无效报错(self, tmp_path, content):
        (tmp_path / CONFIG_FILENAME).write_text(content, encoding="utf-8")
        (tmp_path / "主程序.道").write_text("打印(1)", encoding="utf-8")

        with pytest.raises(ValueError):
            pack_project(str(tmp_path))

    def test_没有源文件报错(self, tmp_path):
        (tmp_path / CONFIG_FILENAME).write_text(
            "名称 空包\n版本 1.0.0\n", encoding="utf-8"
        )
        with pytest.raises(ValueError, match="没有可打包"):
            pack_project(str(tmp_path))


class TestInspectPackage:
    def test_读取包元数据(self, tmp_path):
        project = make_package_project(tmp_path)
        archive_path = pack_project(str(project))

        config = inspect_package(archive_path)

        assert config.name == "数学库"
        assert str(config.version) == "1.2.0"
        assert config.entry == "主程序"

    def test_文件不存在或非归档报错(self, tmp_path):
        with pytest.raises(ValueError, match="不存在"):
            inspect_package(str(tmp_path / "不存在.道包"))

        fake = tmp_path / "假包.道包"
        fake.write_text("不是压缩包", encoding="utf-8")
        with pytest.raises(ValueError, match="不是有效"):
            inspect_package(str(fake))

    def test_缺少配置的归档报错(self, tmp_path):
        archive = tmp_path / "缺配置.道包"
        with zipfile.ZipFile(archive, "w") as zf:
            zf.writestr("主程序.道", "打印(1)")
        with pytest.raises(ValueError, match="缺少"):
            inspect_package(str(archive))

    def test_路径穿越的归档报错(self, tmp_path):
        archive = tmp_path / "危险包.道包"
        with zipfile.ZipFile(archive, "w") as zf:
            zf.writestr(CONFIG_FILENAME, "名称 危险包\n版本 1.0.0\n")
            zf.writestr("../外部.道", "打印(1)")
        with pytest.raises(ValueError, match="不安全"):
            inspect_package(str(archive))


class TestInstallPackage:
    def test_安装到本地道包目录(self, tmp_path):
        project = make_package_project(tmp_path)
        archive_path = pack_project(str(project))

        app = tmp_path / "应用"
        app.mkdir()
        target = install_package(archive_path, project_dir=str(app))

        assert Path(target) == app / "道包" / "数学库"
        assert (Path(target) / CONFIG_FILENAME).is_file()
        assert (Path(target) / "工具" / "辅助.道").is_file()

    def test_同版本重复安装是幂等的(self, tmp_path):
        project = make_package_project(tmp_path)
        archive_path = pack_project(str(project))
        app = tmp_path / "应用"
        app.mkdir()

        first = install_package(archive_path, project_dir=str(app))
        marker = Path(first) / "自定义.道"
        marker.write_text("保留", encoding="utf-8")
        second = install_package(archive_path, project_dir=str(app))

        assert first == second
        assert marker.is_file()

    def test_版本冲突需强制覆盖(self, tmp_path):
        project = make_package_project(tmp_path)
        archive_path = pack_project(str(project))
        app = tmp_path / "应用"
        app.mkdir()
        install_package(archive_path, project_dir=str(app))

        # 同名项目已存在，在另一目录生成新版本
        other = tmp_path / "新源码"
        other.mkdir()
        (other / CONFIG_FILENAME).write_text(
            "名称 数学库\n版本 2.0.0\n入口 主程序\n", encoding="utf-8"
        )
        (other / "主程序.道").write_text("打印(2)", encoding="utf-8")
        new_archive = pack_project(str(other))

        with pytest.raises(ValueError, match="已安装版本"):
            install_package(new_archive, project_dir=str(app))

        target = install_package(new_archive, project_dir=str(app), force=True)
        assert "版本 2.0.0" in (Path(target) / CONFIG_FILENAME).read_text(encoding="utf-8")
        assert not (Path(target) / "自定义.道").exists()

    def test_安装到全局目录(self, tmp_path, monkeypatch):
        monkeypatch.setattr(Path, "home", classmethod(lambda cls: tmp_path))
        project = make_package_project(tmp_path)
        archive_path = pack_project(str(project))

        target = install_package(archive_path, global_install=True)

        assert Path(target) == tmp_path / ".道" / "包" / "数学库"
        assert (Path(target) / "主程序.道").is_file()

    def test_列出已安装包(self, tmp_path, monkeypatch):
        project = make_package_project(tmp_path)
        archive_path = pack_project(str(project))
        app = tmp_path / "应用"
        app.mkdir()
        install_package(archive_path, project_dir=str(app))

        assert list_installed_packages(str(app)) == [("数学库", "1.2.0", "")]
        assert list_installed_packages(str(tmp_path / "空白项目")) == []

        monkeypatch.setattr(Path, "home", classmethod(lambda cls: tmp_path))
        install_package(archive_path, global_install=True)
        assert list_installed_packages(global_install=True) == [("数学库", "1.2.0", "")]


class TestPackageManagerIntegration:
    def test_manager_install_后立即可解析(self, tmp_path):
        project = make_package_project(tmp_path)
        archive_path = pack_project(str(project))
        app = tmp_path / "应用"
        app.mkdir()
        (app / CONFIG_FILENAME).write_text(
            "名称 应用\n版本 1.0.0\n入口 主程序\n依赖\n    数学库 >=1.0.0\n",
            encoding="utf-8",
        )

        manager = PackageManager(project_dir=str(app))
        assert manager.resolve_module("数学库") is None
        manager.install(archive_path)
        resolved = manager.resolve_module("数学库")

        assert resolved is not None
        assert Path(resolved).is_file()
        assert Path(resolved).name == "主程序.道"

    def test_无扩展名入口也能解析(self, tmp_path):
        app = tmp_path / "应用"
        app.mkdir()
        (app / CONFIG_FILENAME).write_text(
            "名称 应用\n版本 1.0.0\n依赖\n    数学库 >=1.0.0\n", encoding="utf-8"
        )
        pkg = app / "道包" / "数学库"
        pkg.mkdir(parents=True)
        (pkg / CONFIG_FILENAME).write_text(
            "名称 数学库\n版本 1.0.0\n入口 接入层.入口\n", encoding="utf-8"
        )
        (pkg / "接入层").mkdir()
        entry = pkg / "接入层" / "入口.道"
        entry.write_text("导出 函数 测试()\n    返回 1\n", encoding="utf-8")

        assert PackageManager(project_dir=str(app)).resolve_module("数学库") == str(entry)


class TestDaoVersion:
    def test_校验兼容与不兼容(self):
        config = PackageConfig.parse("名称 数学库\n版本 1.0.0\n道版本 >=1.2.0\n")
        check_dao_version(config, "1.2.0")
        check_dao_version(config, "1.5.0")
        with pytest.raises(ValueError, match="需要道语言版本"):
            check_dao_version(config, "1.1.1")

    def test_未声明道版本的包直接通过(self):
        config = PackageConfig.parse("名称 旧包\n版本 1.0.0\n")
        check_dao_version(config, "0.1.0")

    def test_打包后元数据携带道版本(self, tmp_path):
        project = make_package_project(tmp_path, dao_version=">=1.2.0")
        archive_path = pack_project(str(project))

        config = inspect_package(archive_path)
        assert str(config.dao_version) == ">=1.2.0"
        with zipfile.ZipFile(archive_path) as zf:
            assert "道版本 >=1.2.0" in zf.read(CONFIG_FILENAME).decode("utf-8")

    def test_安装时校验道版本并可跳过(self, tmp_path):
        project = make_package_project(tmp_path, dao_version=">=2.0.0")
        archive_path = pack_project(str(project))
        app = tmp_path / "应用"
        app.mkdir()

        with pytest.raises(ValueError, match="需要道语言版本"):
            install_package(archive_path, project_dir=str(app))

        target = install_package(
            archive_path, project_dir=str(app), check_version=False
        )
        assert (Path(target) / CONFIG_FILENAME).is_file()

    def test_包列表展示道版本要求(self, tmp_path):
        project = make_package_project(tmp_path, dao_version="^1.2.0")
        archive_path = pack_project(str(project))
        app = tmp_path / "应用"
        app.mkdir()
        install_package(archive_path, project_dir=str(app))

        assert list_installed_packages(str(app)) == [("数学库", "1.2.0", "^1.2.0")]

    def test_包管理器install支持跳过版本检查(self, tmp_path):
        project = make_package_project(tmp_path, dao_version=">=2.0.0")
        archive_path = pack_project(str(project))
        app = tmp_path / "应用"
        app.mkdir()
        (app / CONFIG_FILENAME).write_text(
            "名称 应用\n版本 1.0.0\n依赖\n    数学库 >=1.0.0\n", encoding="utf-8"
        )
        manager = PackageManager(project_dir=str(app))

        with pytest.raises(ValueError, match="需要道语言版本"):
            manager.install(archive_path)
        assert manager.install(archive_path, check_version=False).endswith("数学库")
