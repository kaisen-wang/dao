"""类型检查 CLI：阻断模式、仅警告模式与默认行为。"""

import os
import subprocess
import sys
from pathlib import Path

MAIN = Path(__file__).resolve().parents[1] / "main.py"


def write_program(tmp_path: Path, source: str) -> Path:
    program = tmp_path / "主程序.道"
    program.write_text(source, encoding="utf-8")
    return program


def run_cli(program: Path, *flags: str, cwd: Path) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(MAIN), str(program), *flags],
        cwd=str(cwd),
        capture_output=True,
        text=True,
    )


class TestTypeCheckCLI:
    def test_type_check_blocks_execution_on_error(self, tmp_path):
        program = write_program(
            tmp_path,
            '定义 x: 文本 = 42\n打印("不应执行")\n',
        )
        result = run_cli(program, "--type-check", cwd=tmp_path)
        assert result.returncode != 0
        assert "类型错误" in result.stderr
        assert "不应执行" not in result.stdout
        assert "42" not in result.stdout

    def test_type_check_diagnostic_includes_line_and_column(self, tmp_path):
        program = write_program(tmp_path, '\n定义 x: 文本 = 42\n')
        result = run_cli(program, "--type-check", cwd=tmp_path)
        assert result.returncode != 0
        assert "行" in result.stderr and "列" in result.stderr
        assert "文本" in result.stderr and "数值" in result.stderr

    def test_type_check_passes_clean_program(self, tmp_path):
        program = write_program(tmp_path, '定义 x: 数值 = 42\n打印(x)\n')
        result = run_cli(program, "--type-check", cwd=tmp_path)
        assert result.returncode == 0
        assert "类型错误" not in result.stderr
        assert "42" in result.stdout

    def test_type_check_warn_only_warns_and_continues(self, tmp_path):
        program = write_program(tmp_path, '定义 x: 文本 = 42\n打印(x)\n')
        result = run_cli(program, "--type-check-warn", cwd=tmp_path)
        assert result.returncode == 0
        assert "类型警告" in result.stdout
        assert "42" in result.stdout

    def test_default_behavior_is_unchanged(self, tmp_path):
        program = write_program(tmp_path, '定义 x: 文本 = 42\n打印(x)\n')
        result = run_cli(program, cwd=tmp_path)
        assert result.returncode == 0
        assert "类型警告" not in result.stdout
        assert "类型错误" not in result.stderr
        assert "42" in result.stdout
