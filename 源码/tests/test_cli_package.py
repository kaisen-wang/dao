"""CLI 依赖包子命令测试（pack / 打包、install / 安装、packages / 包列表）。"""

import os
import subprocess
import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[2]
MAIN = PROJECT_ROOT / "源码" / "main.py"

sys.path.insert(0, str(MAIN.parent))
import main as cli_main


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


def make_library(root: Path, name: str = "数学库", version: str = "1.2.0") -> Path:
    project = root / f"{name}-{version}-src"
    (project / "工具").mkdir(parents=True)
    (project / "道.配置").write_text(
        f"名称 {name}\n版本 {version}\n入口 主程序\n\n依赖\n\n开发依赖\n",
        encoding="utf-8",
    )
    (project / "主程序.道").write_text(
        "导出 函数 加(甲, 乙)\n    返回 甲 + 乙\n", encoding="utf-8"
    )
    (project / "工具" / "辅助.道").write_text(
        "导出 函数 助记()\n    返回 42\n", encoding="utf-8"
    )
    return project


def make_app(root: Path, name: str = "数学库", version: str = "1.2.0") -> Path:
    app = root / "应用"
    app.mkdir(exist_ok=True)
    (app / "道.配置").write_text(
        "名称 应用\n版本 1.0.0\n入口 主程序\n"
        f"依赖\n    {name} >={version}\n\n开发依赖\n",
        encoding="utf-8",
    )
    (app / "主程序.道").write_text(
        f"从 {name} 导入 加\n从 {name}.工具.辅助 导入 助记\n"
        "打印(加(2, 3))\n打印(助记())\n",
        encoding="utf-8",
    )
    return app


@pytest.mark.parametrize("command", ["pack", "打包"])
def test_pack_命令生成依赖包(tmp_path, command):
    library = make_library(tmp_path)

    result = run_cli([command, str(library)], tmp_path)

    assert result.returncode == 0, result.stderr
    archive = library / "数学库-1.2.0.道包"
    assert archive.is_file()
    assert "已生成依赖包" in result.stdout


def test_pack_缺少配置时以非零码退出(tmp_path):
    result = run_cli(["pack", str(tmp_path)], tmp_path)
    assert result.returncode != 0
    assert "道.配置" in result.stderr


@pytest.mark.parametrize("command", ["install", "安装"])
def test_install_命令安装依赖包(tmp_path, command):
    library = make_library(tmp_path)
    archive = library / "数学库-1.2.0.道包"
    assert run_cli(["pack", str(library)], tmp_path).returncode == 0
    app = make_app(tmp_path)

    result = run_cli([command, str(archive), "-p", str(app)], tmp_path)

    assert result.returncode == 0, result.stderr
    assert (app / "道包" / "数学库" / "主程序.道").is_file()
    assert "已安装依赖" in result.stdout


def test_打包安装后项目可直接运行(tmp_path):
    library = make_library(tmp_path)
    assert run_cli(["pack", str(library)], tmp_path).returncode == 0
    app = make_app(tmp_path)
    archive = library / "数学库-1.2.0.道包"
    assert run_cli(["install", str(archive), "-p", str(app)], tmp_path).returncode == 0

    result = run_cli(["run"], app)

    assert result.returncode == 0, result.stderr
    assert "5" in result.stdout
    assert "42" in result.stdout


@pytest.mark.parametrize("command", ["packages", "包列表"])
def test_包列表命令(tmp_path, command):
    library = make_library(tmp_path)
    assert run_cli(["pack", str(library)], tmp_path).returncode == 0
    app = make_app(tmp_path)
    archive = library / "数学库-1.2.0.道包"
    assert run_cli(["install", str(archive), "-p", str(app)], tmp_path).returncode == 0

    result = run_cli([command, str(app)], tmp_path)

    assert result.returncode == 0, result.stderr
    assert "数学库 1.2.0" in result.stdout


def test_版本冲突需强制覆盖(tmp_path):
    library = make_library(tmp_path)
    assert run_cli(["pack", str(library)], tmp_path).returncode == 0
    app = make_app(tmp_path)
    archive = library / "数学库-1.2.0.道包"
    assert run_cli(["install", str(archive), "-p", str(app)], tmp_path).returncode == 0

    upgraded = tmp_path / "升级源码"
    upgraded.mkdir()
    (upgraded / "道.配置").write_text(
        "名称 数学库\n版本 2.0.0\n入口 主程序\n", encoding="utf-8"
    )
    (upgraded / "主程序.道").write_text("导出 函数 加(甲, 乙)\n    返回 甲 + 乙\n", encoding="utf-8")
    new_archive = tmp_path / "数学库-2.0.0.道包"
    assert run_cli(["pack", str(upgraded), "-o", str(new_archive)], tmp_path).returncode == 0

    conflict = run_cli(["install", str(new_archive), "-p", str(app)], tmp_path)
    assert conflict.returncode != 0
    assert "已安装版本" in conflict.stderr

    forced = run_cli(["install", str(new_archive), "-p", str(app), "--force"], tmp_path)
    assert forced.returncode == 0, forced.stderr
    assert "版本 2.0.0" in (app / "道包" / "数学库" / "道.配置").read_text(encoding="utf-8")


def test_入口解析函数仍从主入口导出(tmp_path):
    assert cli_main.resolve_entry_path(str(tmp_path), "主程序") == str(tmp_path / "主程序.道")
