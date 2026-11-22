"""CLI 项目模式（run / 运行）测试。

覆盖：
- 入口为文件路径 / 点分模块路径
- run 与 运行 命令等价
- 指定项目目录
- 配置缺失 / 入口缺失 / 入口文件不存在的报错
- 相对导入按项目根目录解析
- 原有单文件执行模式向后兼容
"""

import os
import subprocess
import sys
from pathlib import Path

import pytest

# 源码/tests/test_cli_run.py -> 仓库根目录
PROJECT_ROOT = Path(__file__).resolve().parents[2]
MAIN = PROJECT_ROOT / "源码" / "main.py"

sys.path.insert(0, str(MAIN.parent))
import main as cli_main


def write_config(project_dir: Path, entry: str | None = "主程序.道"):
    """在项目目录写入一份最小可用的 道.配置。"""
    entry_line = f"入口 {entry}\n" if entry is not None else ""
    (project_dir / "道.配置").write_text(
        "名称 测试项目\n"
        "版本 1.0.0\n"
        "描述 CLI 测试\n"
        f"{entry_line}\n"
        "依赖\n"
        "\n"
        "开发依赖\n",
        encoding="utf-8",
    )


def run_cli(args: list[str], cwd: Path):
    """在指定目录调用解释器主入口。"""
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


# ---------------------------------------------------------------------------
# 入口路径解析（纯函数）
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    ("entry", "expected"),
    [
        ("入口.道", "入口.道"),
        ("入口", "入口.道"),
        ("接入层/入口.道", "接入层/入口.道"),
        ("子目录/主程序", "子目录/主程序.道"),
        ("接入层.入口", "接入层/入口.道"),
        ("接入层.入口.道", "接入层/入口.道"),
    ],
)
def test_解析入口优先级(tmp_path, entry, expected):
    assert cli_main.resolve_entry_path(str(tmp_path), entry) == str(tmp_path / expected)


@pytest.mark.parametrize("entry", ["", "   "])
def test_解析入口为空报错(tmp_path, entry):
    with pytest.raises(ValueError, match="入口"):
        cli_main.resolve_entry_path(str(tmp_path), entry)


# ---------------------------------------------------------------------------
# 项目模式集成测试
# ---------------------------------------------------------------------------

def test_run_读取配置并运行入口(tmp_path):
    write_config(tmp_path)
    (tmp_path / "主程序.道").write_text('打印("HELLO_FROM_ENTRY")\n', encoding="utf-8")

    result = run_cli(["run"], tmp_path)

    assert result.returncode == 0, result.stderr
    assert "HELLO_FROM_ENTRY" in result.stdout


def test_run_点分模块路径入口(tmp_path):
    (tmp_path / "子目录").mkdir()
    write_config(tmp_path, "子目录.主程序")
    (tmp_path / "子目录" / "主程序.道").write_text('打印("DOT_PATH_OK")\n', encoding="utf-8")

    result = run_cli(["run"], tmp_path)

    assert result.returncode == 0, result.stderr
    assert "DOT_PATH_OK" in result.stdout


def test_运行中文命令与run等价(tmp_path):
    write_config(tmp_path)
    (tmp_path / "主程序.道").write_text('打印("CHINESE_CMD_OK")\n', encoding="utf-8")

    result = run_cli(["运行"], tmp_path)

    assert result.returncode == 0, result.stderr
    assert "CHINESE_CMD_OK" in result.stdout


def test_run_支持指定项目目录(tmp_path):
    write_config(tmp_path)
    (tmp_path / "主程序.道").write_text('打印("EXPLICIT_DIR_OK")\n', encoding="utf-8")

    result = run_cli(["run", str(tmp_path)], tmp_path.parent)

    assert result.returncode == 0, result.stderr
    assert "EXPLICIT_DIR_OK" in result.stdout


def test_run_切换工作目录以解析相对导入(tmp_path):
    (tmp_path / "子目录").mkdir()
    write_config(tmp_path, "子目录.入口")
    (tmp_path / "共享.道").write_text('导出 常量 问候 = "IMPORT_OK"\n', encoding="utf-8")
    (tmp_path / "子目录" / "入口.道").write_text(
        "从 共享 导入 问候\n打印(问候)\n", encoding="utf-8"
    )

    result = run_cli(["run"], tmp_path)

    assert result.returncode == 0, result.stderr
    assert "IMPORT_OK" in result.stdout


def test_run_缺少配置文件时报错(tmp_path):
    result = run_cli(["run"], tmp_path)

    assert result.returncode != 0
    assert "道.配置" in result.stderr


def test_run_缺少入口配置时报错(tmp_path):
    write_config(tmp_path, None)

    result = run_cli(["run"], tmp_path)

    assert result.returncode != 0
    assert "未配置「入口」" in result.stderr


def test_run_入口文件不存在时报错(tmp_path):
    write_config(tmp_path, "不存在.入口")

    result = run_cli(["run"], tmp_path)

    assert result.returncode != 0
    assert "入口文件不存在" in result.stderr


def test_原有单文件执行模式仍可用(tmp_path):
    script = tmp_path / "直接执行.道"
    script.write_text('打印("DIRECT_FILE_OK")\n', encoding="utf-8")

    result = run_cli([str(script)], tmp_path)

    assert result.returncode == 0, result.stderr
    assert "DIRECT_FILE_OK" in result.stdout
