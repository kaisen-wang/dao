"""``dao.tools.profiler`` 性能分析器测试。

覆盖：interpreter/vm 两种模式的函数级采样、调用次数/总耗时/平均耗时、
热点排序（含真实程序）、中文报告格式、空报告、CLI 输出与错误退出码。
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from dao.tools.profiler import (  # noqa: E402
    FunctionStat,
    ProfileReport,
    profile_file,
    profile_source,
)

SOURCE_DIR = Path(__file__).resolve().parents[1]

# 递归版本在解释器和 VM 两种模式下都能正确运行（VM 对部分循环/声明组合
# 存在既有缺陷），且能稳定产生“热函数 16 次、冷函数 1 次”的调用分布。
递归程序 = """\
函数 热函数(n)
    如果 n <= 0
        返回 0
    返回 1 + 热函数(n - 1)

函数 冷函数()
    返回 0

打印(热函数(15))
打印(冷函数())
"""


def _quiet_profile(source, mode):
    """剖析时屏蔽 打印 输出，只关心统计结果。"""
    import contextlib
    import io

    with contextlib.redirect_stdout(io.StringIO()):
        return profile_source(source, mode=mode)


def _cli(*args):
    return subprocess.run(
        [sys.executable, "-m", "dao.tools.profiler", *map(str, args)],
        cwd=str(SOURCE_DIR),
        capture_output=True,
        text=True,
    )


# -------------------- 函数级采样 --------------------


def test_interpreter_mode_collects_function_stats():
    """interpreter 模式：采集到用户函数及其调用次数与耗时。"""
    report = _quiet_profile(递归程序, "interpreter")
    assert report.mode == "interpreter"
    assert set(report.function_stats) == {"热函数", "冷函数"}
    hot = report.function_stats["热函数"]
    assert hot.calls == 16
    assert hot.total_time > 0
    assert report.elapsed > 0


def test_vm_mode_collects_function_stats():
    """vm 模式：同样采集到用户函数，且顶层 <module> 不计入函数统计。"""
    report = _quiet_profile(递归程序, "vm")
    assert report.mode == "vm"
    assert set(report.function_stats) == {"热函数", "冷函数"}
    assert "<module>" not in report.function_stats
    assert report.function_stats["热函数"].calls == 16


def test_function_stat_average_time():
    """平均耗时 = 总耗时 / 调用次数；零调用时平均耗时为 0。"""
    stat = FunctionStat("测试函数", calls=4, total_time=0.4)
    assert stat.average_time == pytest.approx(0.1)
    assert FunctionStat("空函数").average_time == 0.0
    data = stat.to_dict()
    assert data["name"] == "测试函数" and data["calls"] == 4
    assert data["total_time"] == pytest.approx(0.4)


# -------------------- 热点排序 --------------------


def test_hotspot_sorting_by_total_time():
    """top() 按总耗时降序排列，并遵守 n 上限；同耗时按调用次数稳定排序。"""
    report = ProfileReport(
        mode="interpreter",
        filename="<测试>",
        function_stats={
            "冷门": FunctionStat("冷门", calls=1, total_time=0.01),
            "最热": FunctionStat("最热", calls=5, total_time=0.9),
            "次热": FunctionStat("次热", calls=3, total_time=0.5),
        },
    )
    assert [stat.name for stat in report.top(2)] == ["最热", "次热"]
    assert [stat.name for stat in report.top()] == ["最热", "次热", "冷门"]
    assert report.top(0) == []


def test_hotspot_sorting_real_program_both_modes():
    """真实程序：调用 16 次的热函数必须排在只调用 1 次的冷函数之前。"""
    for mode in ("interpreter", "vm"):
        report = _quiet_profile(递归程序, mode)
        ranked = report.top(3)
        assert ranked[0].name == "热函数"
        assert ranked[0].calls > ranked[1].calls
        assert ranked[0].total_time >= ranked[1].total_time


# -------------------- 报告格式 --------------------


def test_render_chinese_report_format():
    """render() 输出中文报告：标题、模式、总耗时、统计表头与热点榜。"""
    report = ProfileReport(
        mode="vm", filename="示例.道", elapsed=0.123456,
        function_stats={"甲": FunctionStat("甲", calls=2, total_time=0.08)},
    )
    text = report.render(5)
    assert "道语言性能分析报告" in text
    assert "文件: 示例.道" in text
    assert "模式: vm" in text
    assert "总耗时:" in text and "秒" in text
    assert "调用次数" in text and "平均耗时" in text
    assert "热点 Top 5" in text
    assert "1. 甲 —— 调用 2 次" in text


def test_render_empty_report():
    """没有采样到函数时，报告保留中文表头并给出空态提示。"""
    text = ProfileReport(mode="interpreter", filename="<输入>").render()
    assert "未采样到用户函数" in text
    assert "（无热点）" in text
    assert "道语言性能分析报告" in text


def test_to_dict_serializable():
    """to_dict() 返回可 JSON 序列化且按热点排序的函数列表。"""
    report = ProfileReport(
        mode="interpreter", filename="<输入>", elapsed=0.2,
        function_stats={
            "甲": FunctionStat("甲", 1, 0.1),
            "乙": FunctionStat("乙", 9, 0.5),
        },
    )
    data = report.to_dict(top_n=1)
    assert data["mode"] == "interpreter" and data["filename"] == "<输入>"
    assert len(data["functions"]) == 1
    assert data["functions"][0]["name"] == "乙"


# -------------------- 文件与 CLI --------------------


def test_profile_file(tmp_path):
    """profile_file() 从磁盘读取 .道 文件并正常剖析。"""
    target = tmp_path / "基准.道"
    target.write_text(递归程序, encoding="utf-8")
    report = profile_file(target, mode="interpreter")
    assert "热函数" in report.function_stats
    assert str(target) == report.filename


def test_cli_text_report_and_top(tmp_path):
    """CLI：中文报告输出到 stdout，--top N 限制榜单条数，退出码 0。"""
    target = tmp_path / "基准.道"
    target.write_text(递归程序, encoding="utf-8")
    result = _cli(target, "--mode", "vm", "--top", "1")
    assert result.returncode == 0, result.stderr
    assert "道语言性能分析报告" in result.stdout
    assert "模式: vm" in result.stdout
    assert "热点 Top 1" in result.stdout
    assert "热函数" in result.stdout
    assert "冷函数" not in result.stdout


def test_cli_invalid_arguments(tmp_path):
    """CLI：不存在的文件与负数 --top 均返回退出码 2。"""
    missing = tmp_path / "不存在.道"
    result = _cli(missing)
    assert result.returncode == 2
    assert "文件不存在" in result.stderr

    target = tmp_path / "基准.道"
    target.write_text(递归程序, encoding="utf-8")
    result = _cli(target, "--top", "-1")
    assert result.returncode == 2
    assert "--top" in result.stderr
