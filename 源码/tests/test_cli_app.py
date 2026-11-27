"""CLI 应用打包测试（build / 构建应用、run-app / 运行应用）。"""

import os
import subprocess
import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[2]
MAIN = PROJECT_ROOT / "源码" / "main.py"

sys.path.insert(0, str(MAIN.parent))


def run_cli(args: list[str], cwd: Path):
    env = os.environ.copy()
    env["PYTHONPATH"] = str(MAIN.parent)
    return subprocess.run(
        [sys.executable, str(MAIN), *args],
        cwd=str(cwd),
        env=env,
        capture_output=True,
        text=True,
        check=False,
        timeout=60,
    )


def make_library(root: Path) -> Path:
    project = root / "数学库-src"
    project.mkdir()
    (project / "道.配置").write_text(
        "名称 数学库\n版本 1.0.0\n入口 主程序\n", encoding="utf-8"
    )
    (project / "主程序.道").write_text(
        "导出 函数 加(甲, 乙)\n    返回 甲 + 乙\n", encoding="utf-8"
    )
    return project


def make_app(root: Path, dao_version: str | None = None) -> Path:
    project = root / "应用"
    project.mkdir(exist_ok=True)
    dao_line = f"道版本 {dao_version}\n" if dao_version else ""
    (project / "道.配置").write_text(
        f"名称 应用\n版本 1.0.0\n{dao_line}入口 主程序\n"
        "依赖\n    数学库 >=1.0.0\n\n开发依赖\n",
        encoding="utf-8",
    )
    (project / "主程序.道").write_text(
        "从 数学库 导入 加\n打印(加(2, 3))\n", encoding="utf-8"
    )
    return project


def build_with_dependency(root: Path, dao_version: str | None = None) -> Path:
    """准备一个已安装依赖、可打成应用的项目，返回应用包路径。"""
    library = make_library(root)
    assert run_cli(["pack", str(library)], root).returncode == 0
    app = make_app(root, dao_version)
    archive = library / "数学库-1.0.0.道包"
    assert run_cli(["install", str(archive), "-p", str(app)], root).returncode == 0
    assert run_cli(["build", str(app)], root).returncode == 0
    return app / "应用-1.0.0.道应用"


@pytest.mark.parametrize("command", ["build", "构建应用", "打包应用"])
def test_build_命令生成应用包(tmp_path, command):
    archive = build_with_dependency(tmp_path)

    result = run_cli([command, str(tmp_path / "应用")], tmp_path)

    assert result.returncode == 0, result.stderr
    assert "已生成应用包" in result.stdout
    assert archive.is_file()


def test_build_缺少入口时报错(tmp_path):
    (tmp_path / "道.配置").write_text("名称 应用\n版本 1.0.0\n", encoding="utf-8")
    result = run_cli(["build", str(tmp_path)], tmp_path)
    assert result.returncode != 0
    assert "入口" in result.stderr


@pytest.mark.parametrize("command", ["run-app", "运行应用"])
def test_run_app_命令运行应用(tmp_path, command):
    archive = build_with_dependency(tmp_path)

    result = run_cli([command, str(archive)], tmp_path)

    assert result.returncode == 0, result.stderr
    assert "5" in result.stdout


def test_应用可脱离原项目运行(tmp_path):
    archive = build_with_dependency(tmp_path)
    app_dir = tmp_path / "应用"

    # 删掉原项目的依赖与源码，证明应用包是自包含的
    import shutil

    shutil.rmtree(app_dir / "道包")
    (app_dir / "主程序.道").unlink()

    result = run_cli(["run-app", str(archive)], tmp_path)

    assert result.returncode == 0, result.stderr
    assert "5" in result.stdout


def test_run_app_道版本不满足时报错(tmp_path):
    archive = build_with_dependency(tmp_path, dao_version=">=2.0.0")
    result = run_cli(["run-app", str(archive)], tmp_path)
    assert result.returncode != 0
    assert "需要道语言版本" in result.stderr


def test_run_app_运行后清理临时目录(tmp_path):
    archive = build_with_dependency(tmp_path)
    before = {p.name for p in Path("/tmp").glob("dao-app-*")}

    result = run_cli(["run-app", str(archive)], tmp_path)

    assert result.returncode == 0, result.stderr
    after = {p.name for p in Path("/tmp").glob("dao-app-*")}
    assert after == before
