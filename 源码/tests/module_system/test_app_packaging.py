"""应用打包（dao/package/app.py）单元测试。

覆盖：
- 打成 .道应用 归档，含清单、源码与已安装依赖
- 清单校验与归档路径安全校验
- 解压到指定目录、应用道版本校验
"""

import os
import sys
import zipfile
from pathlib import Path

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from dao.package.app import (
    APP_SUFFIX,
    MANIFEST_FILENAME,
    AppManifest,
    build_app,
    check_app_dao_version,
    extract_app,
    inspect_app,
)
from dao.package.packer import CONFIG_FILENAME
from dao.package.version import Version


def make_app_project(
    root: Path,
    name: str = "应用",
    version: str = "1.0.0",
    dao_version: str | None = None,
    with_dep: bool = True,
) -> Path:
    """构造一个带已安装依赖的最小应用项目。"""
    project = root / name
    (project / "工具").mkdir(parents=True)
    dao_line = f"道版本 {dao_version}\n" if dao_version else ""
    (project / CONFIG_FILENAME).write_text(
        f"名称 {name}\n版本 {version}\n{dao_line}入口 主程序\n"
        "依赖\n    数学库 >=1.0.0\n\n开发依赖\n",
        encoding="utf-8",
    )
    (project / "主程序.道").write_text(
        '从 数学库 导入 加\n打印(加(2, 3))\n', encoding="utf-8"
    )
    (project / "工具" / "辅助.道").write_text(
        '导出 函数 助记()\n    返回 "辅助"\n', encoding="utf-8"
    )
    if with_dep:
        pkg = project / "道包" / "数学库"
        pkg.mkdir(parents=True)
        (pkg / CONFIG_FILENAME).write_text(
            "名称 数学库\n版本 1.0.0\n入口 主程序\n", encoding="utf-8"
        )
        (pkg / "主程序.道").write_text(
            "导出 函数 加(甲, 乙)\n    返回 甲 + 乙\n", encoding="utf-8"
        )
    return project


class TestAppManifest:
    def test_parse_and_str(self):
        content = (
            "名称 我的应用\n版本 1.2.0\n入口 主程序.道\n"
            "道版本 >=1.2.0\n打包时间 2026-11-27T09:00:00\n"
        )
        manifest = AppManifest.parse(content)
        assert manifest.name == "我的应用"
        assert manifest.version == Version(1, 2, 0)
        assert manifest.entry == "主程序.道"
        assert str(manifest.dao_version) == ">=1.2.0"
        assert "打包时间 2026-11-27T09:00:00" in str(manifest)

    @pytest.mark.parametrize(
        "content",
        ["版本 1.0.0\n入口 主程序", "名称 缺版本\n入口 主程序", "名称 缺入口\n版本 1.0.0"],
    )
    def test_parse_missing_fields(self, content):
        with pytest.raises(ValueError, match="清单"):
            AppManifest.parse(content)


class TestBuildApp:
    def test_生成归档含清单源码与依赖(self, tmp_path):
        project = make_app_project(tmp_path)
        (project / "README.md").write_text("说明", encoding="utf-8")

        archive_path = build_app(str(project))

        assert Path(archive_path).is_file()
        assert Path(archive_path).name == f"应用-1.0.0{APP_SUFFIX}"
        with zipfile.ZipFile(archive_path) as zf:
            names = set(zf.namelist())
        assert {
            MANIFEST_FILENAME,
            CONFIG_FILENAME,
            "主程序.道",
            "工具/辅助.道",
            "道包/数学库/道.配置",
            "道包/数学库/主程序.道",
            "README.md",
        } <= names

    def test_不携带依赖(self, tmp_path):
        project = make_app_project(tmp_path)
        archive_path = build_app(str(project), include_deps=False)

        with zipfile.ZipFile(archive_path) as zf:
            names = zf.namelist()
        assert not any(name.startswith("道包/") for name in names)

    def test_自定义输出路径(self, tmp_path):
        project = make_app_project(tmp_path)
        output = tmp_path / "产物"
        archive_path = build_app(str(project), str(output))

        assert Path(archive_path) == output / f"应用-1.0.0{APP_SUFFIX}"

    def test_缺少配置报错(self, tmp_path):
        with pytest.raises(ValueError, match="道.配置"):
            build_app(str(tmp_path))

    def test_缺少入口报错(self, tmp_path):
        (tmp_path / CONFIG_FILENAME).write_text(
            "名称 应用\n版本 1.0.0\n", encoding="utf-8"
        )
        (tmp_path / "主程序.道").write_text("打印(1)", encoding="utf-8")
        with pytest.raises(ValueError, match="入口"):
            build_app(str(tmp_path))

    def test_入口文件不存在报错(self, tmp_path):
        (tmp_path / CONFIG_FILENAME).write_text(
            "名称 应用\n版本 1.0.0\n入口 不存在\n", encoding="utf-8"
        )
        with pytest.raises(ValueError, match="入口文件不存在"):
            build_app(str(tmp_path))


class TestInspectApp:
    def test_读取应用清单(self, tmp_path):
        project = make_app_project(tmp_path, dao_version=">=1.2.0")
        archive_path = build_app(str(project))

        manifest = inspect_app(archive_path)

        assert manifest.name == "应用"
        assert str(manifest.version) == "1.0.0"
        assert manifest.entry == "主程序"
        assert str(manifest.dao_version) == ">=1.2.0"
        assert manifest.built_at

    def test_非归档与缺少清单报错(self, tmp_path):
        with pytest.raises(ValueError, match="不存在"):
            inspect_app(str(tmp_path / "无.道应用"))

        fake = tmp_path / "假.道应用"
        fake.write_text("不是压缩包", encoding="utf-8")
        with pytest.raises(ValueError, match="不是有效"):
            inspect_app(str(fake))

        with zipfile.ZipFile(fake, "w") as zf:
            zf.writestr(CONFIG_FILENAME, "名称 应用\n版本 1.0.0\n入口 主程序\n")
        with pytest.raises(ValueError, match="清单"):
            inspect_app(str(fake))

    def test_路径穿越的归档报错(self, tmp_path):
        archive = tmp_path / "危险.道应用"
        with zipfile.ZipFile(archive, "w") as zf:
            zf.writestr(MANIFEST_FILENAME, "名称 危险\n版本 1.0.0\n入口 主程序\n")
            zf.writestr(CONFIG_FILENAME, "名称 危险\n版本 1.0.0\n入口 主程序\n")
            zf.writestr("../外部.道", "打印(1)")
        with pytest.raises(ValueError, match="不安全"):
            inspect_app(str(archive))


class TestExtractApp:
    def test_解压到指定目录(self, tmp_path):
        project = make_app_project(tmp_path)
        archive_path = build_app(str(project))
        target = tmp_path / "解压"

        result = extract_app(archive_path, str(target))

        assert Path(result) == target.resolve()
        assert (target / "主程序.道").is_file()
        assert (target / "道包" / "数学库" / "主程序.道").is_file()
        assert (target / MANIFEST_FILENAME).is_file()

    def test_非法归档不会被解压(self, tmp_path):
        fake = tmp_path / "假.道应用"
        fake.write_text("不是压缩包", encoding="utf-8")
        with pytest.raises(ValueError, match="不是有效"):
            extract_app(str(fake), str(tmp_path / "解压"))


class TestAppDaoVersion:
    def test_校验兼容与不兼容(self, tmp_path):
        project = make_app_project(tmp_path, dao_version=">=2.0.0")
        manifest = inspect_app(build_app(str(project)))

        with pytest.raises(ValueError, match="需要道语言版本"):
            check_app_dao_version(manifest)
        check_app_dao_version(manifest, "2.0.0")

    def test_未声明道版本的旧应用直接通过(self, tmp_path):
        project = make_app_project(tmp_path)
        check_app_dao_version(inspect_app(build_app(str(project))), "0.1.0")
