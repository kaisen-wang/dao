"""独立格式化器与格式化核心测试。

覆盖：缩进层级与宽度统一、制表符换算、行尾空白、空行折叠、幂等性、
字符串/注释保护、赋值与关键字空格、Token 语义不变、CRLF 保留，
以及 ``python -m dao.tools.formatter`` 的原地 / --check / --stdout 三种模式。
"""

import os
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from dao.lexer import Lexer
from dao.lsp.formatting import format_source
from dao.tokens import TokenType

SOURCE_DIR = Path(__file__).resolve().parents[1]


def _cli(*args):
    """在项目源码目录下以子进程运行格式化器 CLI。"""
    return subprocess.run(
        [sys.executable, "-m", "dao.tools.formatter", *map(str, args)],
        cwd=str(SOURCE_DIR),
        capture_output=True,
        text=True,
    )


def _token_signature(source):
    """比较词元序列；缩进/回退只在乎层级变化，不在乎原始空格数。"""
    result = []
    for token in Lexer(source).tokenize():
        value = None if token.type in (TokenType.缩进, TokenType.回退) else token.value
        result.append((token.type.name, value))
    return result


# ========================
# 核心格式化规则
# ========================


def test_缩进层级与宽度统一():
    """各级缩进统一为 4 的倍数，层级相对关系保持不变。"""
    source = (
        "函数 甲()\n"
        "  定义 乙 = 1\n"
        "    如果 乙\n"
        "      返回 乙\n"
        "  返回 0\n"
    )
    formatted = format_source(source)
    assert formatted == (
        "函数 甲()\n"
        "    定义 乙 = 1\n"
        "        如果 乙\n"
        "            返回 乙\n"
        "    返回 0\n"
    )


def test_缩进宽度可配置():
    """tabSize/indent_width 直接决定一级缩进的空格数。"""
    source = "如果 真\n  定义 甲 = 1\n"
    assert format_source(source, indent_width=2) == "如果 真\n  定义 甲 = 1\n"
    assert format_source(source, indent_width=3) == "如果 真\n   定义 甲 = 1\n"
    # 非法宽度回退到默认值 4。
    assert format_source(source, indent_width=0) == format_source(source)


def test_行首制表符换算为空格():
    """道语言不接受制表符缩进，格式化后行首不含制表符。"""
    formatted = format_source("如果 真\n\t定义 甲 = 1\n\t\t返回 甲\n")
    assert "\t" not in formatted
    assert formatted == "如果 真\n    定义 甲 = 1\n        返回 甲\n"


def test_行尾空白与空行折叠():
    """行尾空白被删除，连续空行折叠为一行。"""
    source = "定义 甲 = 1   \n\n\n\n定义 乙 = 2\t\n"
    assert format_source(source) == "定义 甲 = 1\n\n定义 乙 = 2\n"


def test_格式化幂等():
    """同一源码二次格式化的结果完全一致。"""
    samples = (
        "定义  甲=1\n函数 加(甲,乙)\n  返回 甲+乙\n",
        "  如果 真\n    定义 甲 = 1\n\n\n  返回 甲\n",
        '//  注释  \n定义 文本 = """a   \n  b\n"""\n',
        "",
    )
    for source in samples:
        once = format_source(source)
        assert format_source(once) == once


def test_字符串内容完整保留():
    """三引号字符串内的缩进、空行与行尾空格不被动到。"""
    source = '定义 文本 = """首行   \n  次行\n\n末行"""\n定义 甲=1\n'
    formatted = format_source(source)
    assert '"""首行   \n  次行\n\n末行"""' in formatted
    assert "定义 甲 = 1" in formatted
    single = "定义 文本 = ' 你好  世界 '\n"
    assert format_source(single) == single


def test_注释内容不被改写():
    """行注释内的多个空格保留，仅删除注释末尾空白并补一个前置空格。"""
    source = "//  注释  内容  \n定义 甲=1 // 行尾注释  \n"
    formatted = format_source(source)
    assert "//  注释  内容\n" in formatted
    assert "定义 甲 = 1 // 行尾注释\n" in formatted


def test_关键字与赋值空格规范():
    """多余空白折叠为单个空格，赋值号两侧补空格，复合运算符不变。"""
    source = "定义  甲=1\n如果  甲>=0  //  比较\n  设 甲=甲+1\n"
    formatted = format_source(source)
    assert "定义 甲 = 1" in formatted
    assert "如果 甲>=0 //  比较" in formatted
    assert "    设 甲 = 甲+1" in formatted


def test_格式化不改变Token语义():
    """格式化前后的词元序列（忽略缩进宽度）完全一致。"""
    samples = (
        "定义  甲=1   \n函数 加(甲,乙)\n  返回 甲+乙\n",
        "如果 真\n  定义 甲 = 1\n否则\n  定义 乙 = 2\n",
        "遍历 项 在 [1,2]\n  打印(项)\n",
    )
    for source in samples:
        assert _token_signature(format_source(source)) == _token_signature(source)


def test_CRLF换行风格保留():
    """原文件使用 CRLF 时，输出仍使用 CRLF。"""
    source = "定义 甲=1\r\n如果 真\r\n  返回 甲\r\n"
    formatted = format_source(source)
    assert "\r\n" in formatted and "\n" not in formatted.replace("\r\n", "")
    assert formatted == "定义 甲 = 1\r\n如果 真\r\n    返回 甲\r\n"


# ========================
# 命令行模式
# ========================


def _messy_file(tmp_path):
    path = tmp_path / "示例.道"
    path.write_text("定义  甲=1   \n\n\n如果 真\n  返回 甲\n", encoding="utf-8")
    return path


def test_CLI_原地格式化(tmp_path):
    """默认模式直接写回文件，标准化后 --check 返回 0。"""
    path = _messy_file(tmp_path)
    result = _cli(path)
    assert result.returncode == 0, result.stderr
    assert "已格式化" in result.stdout
    assert (
        path.read_text(encoding="utf-8")
        == "定义 甲 = 1\n\n如果 真\n    返回 甲\n"
    )
    assert _cli("--check", path).returncode == 0


def test_CLI_check模式(tmp_path):
    """--check 只报告不写文件，且需格式化时退出码为 1。"""
    path = _messy_file(tmp_path)
    original = path.read_text(encoding="utf-8")
    result = _cli("--check", path)
    assert result.returncode == 1
    assert "需要格式化" in result.stdout
    assert path.read_text(encoding="utf-8") == original


def test_CLI_stdout模式(tmp_path):
    """--stdout 输出结果且不修改文件。"""
    path = _messy_file(tmp_path)
    original = path.read_text(encoding="utf-8")
    result = _cli("--stdout", path)
    assert result.returncode == 0, result.stderr
    assert result.stdout == "定义 甲 = 1\n\n如果 真\n    返回 甲\n"
    assert path.read_text(encoding="utf-8") == original


def test_CLI_参数冲突与缺失文件(tmp_path):
    """--check 与 --stdout 冲突、文件不存在时返回非 0 且不崩溃。"""
    path = _messy_file(tmp_path)
    assert _cli("--check", "--stdout", path).returncode != 0
    assert _cli("--stdout", path, path).returncode != 0
    assert _cli(tmp_path / "不存在.道").returncode == 2
