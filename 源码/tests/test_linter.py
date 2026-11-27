"""``dao.tools.linter`` 静态告警工具测试。

覆盖：D001–D007 每条规则的命中与不误报、``--select``/``--ignore`` 过滤、
JSON 输出、目录递归、CLI 退出码与中文告警格式。
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from dao.tools.linter import Linter, LintIssue, RULES  # noqa: E402

SOURCE_DIR = Path(__file__).resolve().parents[1]


def _cli(*args):
    """在源码目录下以子进程运行 linter CLI。"""
    return subprocess.run(
        [sys.executable, "-m", "dao.tools.linter", *map(str, args)],
        cwd=str(SOURCE_DIR),
        capture_output=True,
        text=True,
    )


def _rules(issues):
    return [issue.rule for issue in issues]


# -------------------- D001 未使用变量 --------------------


def test_d001_unused_variable_hit():
    """D001：定义了却从未读取的变量应被告警。"""
    source = "定义 未用 = 1\n"
    issues = Linter(select={"D001"}).check(source)
    assert _rules(issues) == ["D001"]
    assert "未用" in issues[0].message
    assert (issues[0].line, issues[0].column) == (1, 1)


def test_d001_used_exported_and_underscore_no_false_positive():
    """D001：被读取、显式导出或下划线开头的变量都不应误报。"""
    source = (
        "定义 已用 = 1\n"
        "打印(已用)\n"
        "定义 导出值 = 2\n"
        "导出 导出值\n"
        "定义 _临时 = 3\n"
    )
    assert Linter(select={"D001"}).check(source) == []


# -------------------- D002 重复变量定义 --------------------


def test_d002_duplicate_definition_hit():
    """D002：同一作用域重复定义应告警，且定位在第二次定义处。"""
    source = "定义 甲 = 1\n定义 甲 = 2\n"
    issues = Linter(select={"D002"}).check(source)
    assert len(issues) == 1
    assert issues[0].rule == "D002"
    assert issues[0].line == 2
    assert "重复定义" in issues[0].message


def test_d002_same_name_in_different_scopes_no_false_positive():
    """D002：不同函数作用域内的同名变量不应误报。"""
    source = (
        "函数 甲()\n"
        "    定义 值 = 1\n"
        "    返回 值\n"
        "\n"
        "函数 乙()\n"
        "    定义 值 = 2\n"
        "    返回 值\n"
    )
    assert Linter(select={"D002"}).check(source) == []


# -------------------- D003 不可达代码 --------------------


def test_d003_unreachable_after_return_hit():
    """D003：返回语句之后的语句应告警。"""
    source = (
        "函数 甲()\n"
        "    返回 1\n"
        "    打印(\"不可达\")\n"
    )
    issues = Linter(select={"D003"}).check(source)
    assert len(issues) == 1
    assert issues[0].rule == "D003"
    assert issues[0].line == 3
    assert "返回" in issues[0].message


def test_d003_reachable_code_no_false_positive():
    """D003：终止语句位于函数体末尾、或在分支内部时不应误报。"""
    source = (
        "函数 甲()\n"
        "    如果 真\n"
        "        返回 1\n"
        "    打印(\"可达\")\n"
        "函数 乙()\n"
        "    返回 2\n"
    )
    assert Linter(select={"D003"}).check(source) == []


# -------------------- D004 过长函数 --------------------


def test_d004_long_function_hit():
    """D004：函数体语句数超过阈值应告警。"""
    source = (
        "函数 过长()\n"
        "    定义 甲 = 1\n"
        "    定义 乙 = 2\n"
        "    定义 丙 = 3\n"
        "    定义 丁 = 4\n"
    )
    issues = Linter(select={"D004"}, max_statements=3).check(source)
    assert len(issues) == 1
    assert issues[0].rule == "D004"
    assert "过长" in issues[0].message and "4" in issues[0].message


def test_d004_short_function_no_false_positive():
    """D004：语句数未超阈值的函数不应误报。"""
    source = (
        "函数 简短()\n"
        "    定义 甲 = 1\n"
        "    返回 甲\n"
    )
    assert Linter(select={"D004"}, max_statements=3).check(source) == []


# -------------------- D005 魔法数字 --------------------


def test_d005_magic_number_hit():
    """D005：非允许列表中的数字字面量应告警。"""
    source = "定义 阈值 = 42\n"
    issues = Linter(select={"D005"}).check(source)
    assert len(issues) == 1
    assert issues[0].rule == "D005"
    assert "42" in issues[0].message and "魔法数字" in issues[0].message


def test_d005_allowed_numbers_no_false_positive():
    """D005：0 与 1 是默认允许值，不应误报；自定义白名单同样生效。"""
    assert Linter(select={"D005"}).check("定义 甲 = 0\n定义 乙 = 1\n") == []
    assert Linter(select={"D005"}, magic_allowlist={0, 1, 42}).check(
        "定义 阈值 = 42\n"
    ) == []


# -------------------- D006 裸捕获 --------------------


def test_d006_bare_catch_hit():
    """D006：未指定异常类型的捕获应告警。"""
    source = (
        "尝试\n"
        "    抛出 错误(\"失败\")\n"
        "捕获 错误对象\n"
        "    打印(错误对象)\n"
    )
    issues = Linter(select={"D006"}).check(source)
    assert len(issues) == 1
    assert issues[0].rule == "D006"
    assert "裸捕获" in issues[0].message


def test_d006_typed_catch_no_false_positive():
    """D006：明确指定异常类型的捕获不应误报。"""
    source = (
        "尝试\n"
        "    抛出 错误(\"失败\")\n"
        "捕获 错误: 错误对象\n"
        "    打印(错误对象)\n"
    )
    assert Linter(select={"D006"}).check(source) == []


# -------------------- D007 缺失文档注释 --------------------


def test_d007_missing_doc_comment_hit():
    """D007：开启可选规则后，无 /// 文档注释的函数应告警。"""
    source = "函数 甲()\n    返回 1\n"
    issues = Linter(select={"D007"}, check_doc_comments=True).check(source)
    assert len(issues) == 1
    assert issues[0].rule == "D007"
    assert "文档注释" in issues[0].message


def test_d007_doc_comment_present_no_false_positive():
    """D007：紧邻函数声明的 /// 文档注释应抑制告警；默认关闭也不告警。"""
    source = "/// 返回一\n函数 甲()\n    返回 1\n"
    assert Linter(select={"D007"}, check_doc_comments=True).check(source) == []
    assert Linter().check("函数 甲()\n    返回 1\n") == []


# -------------------- 过滤、数据结构与 CLI --------------------


def test_select_and_ignore_filtering():
    """--select/--ignore 语义：ignore 优先级高于 select，未知规则被拒绝。"""
    source = "定义 甲 = 42\n打印(甲)\n"
    assert _rules(Linter(select={"D005"}).check(source)) == ["D005"]
    assert _rules(Linter(select={"D001", "D005"}, ignore={"D005"}).check(source)) == []

    linter = Linter()
    assert linter._enabled("D001") is True
    assert Linter(select={"D001"})._enabled("D005") is False
    assert set(RULES) == {"D001", "D002", "D003", "D004", "D005", "D006", "D007"}


def test_issue_is_chinese_and_serializable():
    """告警含中文消息、规则编号与行列，且可序列化为 JSON 友好的字典。"""
    issue = LintIssue("D001", "变量“甲”已定义但从未使用", 3, 5, "例子.道")
    assert "变量" in issue.message and issue.rule == "D001"
    assert str(issue) == "例子.道:3:5: D001 变量“甲”已定义但从未使用"
    assert issue.to_dict() == {
        "rule": "D001",
        "message": "变量“甲”已定义但从未使用",
        "line": 3,
        "column": 5,
        "filename": "例子.道",
        "severity": "warning",
    }


def test_cli_json_output_and_exit_codes(tmp_path):
    """CLI：--json 输出数组；有告警退出码 1，无告警退出码 0。"""
    bad = tmp_path / "坏.道"
    bad.write_text("定义 未用 = 1\n", encoding="utf-8")
    good = tmp_path / "好.道"
    good.write_text("定义 已用 = 1\n打印(已用)\n", encoding="utf-8")

    result = _cli(bad, "--json", "--select", "D001")
    assert result.returncode == 1
    payload = json.loads(result.stdout)
    assert len(payload) == 1 and payload[0]["rule"] == "D001"
    assert "未用" in payload[0]["message"]

    result = _cli(good, "--json", "--select", "D001")
    assert result.returncode == 0
    assert json.loads(result.stdout) == []


def test_cli_directory_recursion_and_text_report(tmp_path):
    """CLI：目录递归查找 .道 文件，文本报告含中文汇总与行列。"""
    nested = tmp_path / "子目录"
    nested.mkdir()
    (nested / "示例.道").write_text("定义 未用 = 1\n", encoding="utf-8")

    result = _cli(tmp_path, "--select", "D001")
    assert result.returncode == 1
    assert "D001" in result.stdout
    assert "1:1" in result.stdout
    assert "共发现" in result.stdout


def test_cli_unknown_rule_exits_with_error(tmp_path):
    """CLI：--select 传入未知规则编号时以退出码 2 报错。"""
    target = tmp_path / "示例.道"
    target.write_text("定义 x = 1\n", encoding="utf-8")
    result = _cli(target, "--select", "D999")
    assert result.returncode == 2
    assert "未知规则" in result.stderr


@pytest.mark.parametrize("source, expected", [
    ("定义 x = 1\n", ["D001"]),
    ("定义 x = 1\n定义 x = 2\n", ["D001", "D001", "D002"]),
])
def test_parametrized_unused_and_duplicate(source, expected):
    """参数化：验证未使用变量与重复定义的组合命中数量。"""
    assert _rules(Linter(select={"D001", "D002"}).check(source)) == expected
