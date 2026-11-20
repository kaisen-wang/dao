"""第 4 轮语言自举旗舰示例的回归测试。

在 示例/自举/ 下用纯道语言实现静态检查器，并与 Python 侧
``dao.lsp.features.compute_diagnostics`` 做同输入对照。
"""

import os
import re
import subprocess
import sys

import pytest

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
REPO_ROOT = os.path.abspath(os.path.join(ROOT, ".."))
sys.path.insert(0, ROOT)  # noqa: E402

from dao.lsp.features import compute_diagnostics  # noqa: E402

MAIN_PY = os.path.join(ROOT, "main.py")
PYTHON = os.path.join(ROOT, ".venv", "bin", "python")
CHECKER = os.path.join(REPO_ROOT, "示例", "自举", "静态检查器.道")
SELF_CHECK = os.path.join(REPO_ROOT, "示例", "自举", "自举自检.道")
ENV_TARGET = "DAO_CHECK_TARGET"


def 运行道脚本(脚本路径, 目标路径=None, 标准输入=b"", 超时=30):
    """在源码目录用 main.py 执行 .道 脚本，返回 CompletedProcess。"""
    环境 = os.environ.copy()
    if 目标路径 is None:
        环境.pop(ENV_TARGET, None)
    else:
        环境[ENV_TARGET] = 目标路径
    return subprocess.run(
        [PYTHON, MAIN_PY, 脚本路径],
        cwd=ROOT,
        env=环境,
        input=标准输入,
        capture_output=True,
        timeout=超时,
    )


def 合并输出(结果):
    """stdout 与 stderr 合并，便于检查中文诊断与统计。"""
    return 结果.stdout + 结果.stderr


class Test静态检查器:
    def test_正确源码检查通过(self, tmp_path):
        """合法 .道 源码应输出通过语义且退出码为 0。"""
        目标 = tmp_path / "正确.道"
        目标.write_text("定义 x = 1\n打印(x)\n", encoding="utf-8")
        结果 = 运行道脚本(CHECKER, str(目标))
        输出 = 合并输出(结果).decode("utf-8", errors="replace")
        assert 结果.returncode == 0, 输出
        assert "通过" in 输出
        assert str(目标) in 输出

    def test_词法错误检查报错(self, tmp_path):
        """未闭合字符串应产生词法错误诊断、非零退出码与错误统计。"""
        目标 = tmp_path / "词法错误.道"
        目标.write_text('"未闭合的字符串\n', encoding="utf-8")
        结果 = 运行道脚本(CHECKER, str(目标))
        输出 = 合并输出(结果).decode("utf-8", errors="replace")
        assert 结果.returncode != 0
        assert "词法错误" in 输出
        assert "未闭合" in 输出
        assert "统计" in 输出
        assert "词法错误" in 结果.stderr.decode("utf-8", errors="replace")

    def test_语法错误检查报错(self, tmp_path):
        """残缺表达式应产生语法错误诊断。"""
        目标 = tmp_path / "语法错误.道"
        目标.write_text("定义 x = \n", encoding="utf-8")
        结果 = 运行道脚本(CHECKER, str(目标))
        输出 = 合并输出(结果).decode("utf-8", errors="replace")
        assert 结果.returncode != 0
        assert "语法错误" in 输出

    def test_未指定目标文件时退出码为3(self):
        """未传目标路径时应提示指定文件并以退出码 3 结束。"""
        结果 = 运行道脚本(CHECKER)
        错误 = 结果.stderr.decode("utf-8", errors="replace")
        assert 结果.returncode == 3
        assert "未指定目标文件" in 错误

    def test_Python侧与道语言侧诊断对照(self, tmp_path):
        """同一批错误源码在 Python 与道语言侧诊断条数和类型一致。"""
        样本 = {
            "词法": '"未闭合的字符串\n',
            "语法": "定义 x = \n",
        }
        行模式 = re.compile(r"^(\d+):(\d+) (\S+) (.+)$")
        for 名称, 源码 in 样本.items():
            目标 = tmp_path / f"{名称}.道"
            目标.write_text(源码, encoding="utf-8")

            python诊断 = compute_diagnostics(源码)
            python类型 = [项["message"].split("：", 1)[0] for 项 in python诊断]

            结果 = 运行道脚本(CHECKER, str(目标))
            错误文本 = 结果.stderr.decode("utf-8", errors="replace")
            道诊断 = []
            for 行 in 错误文本.splitlines():
                匹配 = 行模式.match(行.strip())
                if 匹配:
                    道诊断.append((匹配.group(3), 匹配.group(4)))
            道类型 = [条目[0] for 条目 in 道诊断]

            assert len(道诊断) == len(python诊断), (名称, 错误文本, python诊断)
            assert 道类型 == python类型, (名称, 道类型, python类型)
            assert 结果.returncode != 0


class Test自举自检:
    def test_元数据与字节原语输出(self):
        """自检脚本应打印关键字数量、内置函数示例与中文 UTF-8 字节数。"""
        结果 = 运行道脚本(SELF_CHECK, 标准输入=b"abc")
        输出 = 合并输出(结果).decode("utf-8", errors="replace")
        assert 结果.returncode == 0, 输出
        assert "关键字数量: 79" in 输出
        assert "内置函数名示例:" in 输出
        assert "打印" in 输出
        assert '字节长度("你好") = 6' in 输出
        assert "读字节(3) = b'abc'" in 输出
