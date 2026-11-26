"""更夫 Nightwatch — 第十二轮 B：真子进程验证周期巡检调度 + 决策落库。

弥补第十一轮诚实缺口②：Watchdog 此前只在同进程注入时间戳模拟停滞，
`.巡检()` 未接入真实周期调度。本测试用 ``sys.executable`` 启动真实 OS 子进程，
执行 ``示例/更夫/测试/测试周期巡检.道``，由真 .道 解释器注册 ``周期执行``，
后台线程按 50 毫秒真实触发，把 nudge/alert 决策落库到 SQLite，再回到 Python 侧
用 sqlite3 独立核验落库结果（不是同进程 mock）。

诚实边界：
- 真实周期调度器驱动 + 注入时间戳加速——停滞分钟靠回拨 perf_counter 基准模拟
  31/61 分钟，不是真等 30 分钟；FR-16「30 分钟内被发现」的真实生产定时巡检
  仍需长驻环境（真实时钟 + 守护进程）。
- 本机真子进程 ≠ 生产真实流量；**不勾选 PRD §12 任何 DoD 项**。

测试约定：一律 ``sys.executable``；禁止 ``signal.SIGKILL``，停止用
``proc.terminate()`` 并 fallback ``proc.kill()``；临时库放 ``TemporaryDirectory``，
不在项目目录生成 .db；子进程 cwd=``示例/更夫``（模块搜索基于 os.getcwd()）。
"""

import os
import re
import sqlite3
import subprocess
import sys
import tempfile
from pathlib import Path

# 源码/tests/test_watchdog_periodic.py -> 仓库根目录
PROJECT_ROOT = Path(__file__).resolve().parents[2]
MAIN = PROJECT_ROOT / "源码" / "main.py"
GENGFU_DIR = PROJECT_ROOT / "示例" / "更夫"
SCRIPT = "测试/测试周期巡检.道"  # 相对 cwd=示例/更夫，与手工实跑命令一致
ENV_DB = "GENGFU_PERIODIC_DB"


def _启动(数据库路径: Path | None) -> subprocess.Popen:
    """用 sys.executable 启动真实 OS 子进程执行 .道 周期巡检测试。"""
    环境变量 = os.environ.copy()
    环境变量["PYTHONPATH"] = str(MAIN.parent)
    环境变量["GENGFU_NO_LLM"] = "1"  # 不依赖真实网络 / ollama
    环境变量.pop(ENV_DB, None)
    if 数据库路径 is not None:
        环境变量[ENV_DB] = str(数据库路径)
    return subprocess.Popen(
        [sys.executable, str(MAIN), SCRIPT],
        cwd=str(GENGFU_DIR),
        env=环境变量,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )


def _回收(进程: subprocess.Popen, 超时秒: float = 20) -> tuple[str, str]:
    """等待子进程结束；超时用 terminate() + fallback kill()，绝不使用 SIGKILL。"""
    try:
        return 进程.communicate(timeout=超时秒)
    except subprocess.TimeoutExpired:
        进程.terminate()
        try:
            return 进程.communicate(timeout=5)
        except subprocess.TimeoutExpired:
            进程.kill()
            return 进程.communicate(timeout=5)


def _中文统计(标准输出: str) -> dict[str, int]:
    """从 .道 测试的中文统计行提取计数（键为中文，值必须是非负整数）。"""
    断言行 = "周期巡检统计：" in 标准输出
    assert 断言行, f"子进程 stdout 缺少中文统计行；stdout={标准输出!r}"
    提取 = {}
    for 键 in ("巡检轮次", "累计nudge", "累计告警", "落库nudge", "落库alert"):
        匹配 = re.search(rf"{键}=(\d+)", 标准输出)
        assert 匹配 is not None, f"中文统计缺少字段 {键}；stdout={标准输出!r}"
        提取[键] = int(匹配.group(1))
    return 提取


def test_真子进程运行周期巡检道测试全通过():
    """真子进程跑 测试周期巡检.道：退出码 0、10/10 用例通过、中文统计达标。"""
    with tempfile.TemporaryDirectory(prefix="更夫周期巡检-") as 临时目录:
        数据库 = Path(临时目录) / "周期巡检.db"
        进程 = _启动(数据库)
        标准输出, 标准错误 = _回收(进程)

    assert 进程.returncode == 0, (
        f"真子进程退出码 {进程.returncode}；stderr={标准错误!r}；stdout={标准输出!r}"
    )
    assert "测试套件:" in 标准输出, f"stdout 缺少测试套件汇总：{标准输出!r}"
    assert "失败: 0" in 标准输出, f"道测试存在失败用例：{标准输出!r}"
    assert "总计: 10, 通过: 10" in 标准输出, f"道测试用例数不符：{标准输出!r}"
    assert "真实周期调度器驱动" in 标准输出 and "不勾选 DoD" in 标准输出, (
        f"stdout 缺少诚实边界说明：{标准输出!r}"
    )

    统计 = _中文统计(标准输出)
    assert 统计["巡检轮次"] >= 3, f"周期轮次不足 3：{统计}"
    assert 统计["累计nudge"] >= 1, f"累计 nudge 不足 1：{统计}"
    assert 统计["累计告警"] >= 1, f"累计告警不足 1：{统计}"
    assert 统计["落库nudge"] >= 1, f"落库 nudge 不足 1：{统计}"
    assert 统计["落库alert"] >= 1, f"落库 alert 不足 1：{统计}"

    print(
        "\n================ 真子进程周期巡检报告 ================\n"
        "实现：sys.executable 启真 OS 子进程 + 真 .道 周期执行(50ms) 后台回调；\n"
        f"轮次={统计['巡检轮次']}，累计 nudge={统计['累计nudge']}，"
        f"告警={统计['累计告警']}，落库 nudge={统计['落库nudge']}，"
        f"alert={统计['落库alert']}\n"
        "诚实注记：真实周期调度器驱动 + 注入时间戳加速，非真等 30 分钟；\n"
        "          FR-16 真实生产定时巡检仍需长驻环境；本机子进程 ≠ 生产流量，不勾选 DoD。\n"
        "==================================================="
    )


def test_真子进程把nudge与告警决策落库到独立SQLite():
    """子进程退出后用 sqlite3 独立核验：决策表含 nudge 与 alert，且不在项目目录留 .db。"""
    def 项目库快照() -> set[str]:
        return {路径.name for 路径 in GENGFU_DIR.rglob("*.db")}

    运行前 = 项目库快照()
    with tempfile.TemporaryDirectory(prefix="更夫周期巡检落库-") as 临时目录:
        临时路径 = Path(临时目录)
        数据库 = 临时路径 / "周期巡检落库.db"
        进程 = _启动(数据库)
        _标准输出, 标准错误 = _回收(进程)

        assert 进程.returncode == 0, (
            f"真子进程退出码 {进程.returncode}；stderr={标准错误!r}"
        )
        assert 数据库.exists(), "子进程未在临时目录创建 SQLite 库"
        with sqlite3.connect(数据库) as 连接:
            行数 = 连接.execute(
                "SELECT 结论, COUNT(*) FROM 决策 GROUP BY 结论"
            ).fetchall()
        结论计数 = dict(行数)

    nudge数 = 结论计数.get("nudge", 0)
    alert数 = 结论计数.get("alert", 0)
    assert nudge数 >= 1, f"SQLite 决策表未落库 nudge：{结论计数}"
    assert alert数 >= 1, f"SQLite 决策表未落库 alert：{结论计数}"

    assert not (临时路径.exists()), "TemporaryDirectory 退出后未清理临时库"
    assert 项目库快照() == 运行前, "本测试在 示例/更夫 项目目录新增了 .db 残留"
    print(f"\n落库独立核验：nudge={nudge数}，alert={alert数}（临时 SQLite，退出即清理）")


def test_默认内存库模式无需环境变量亦全通过():
    """不注入 GENGFU_PERIODIC_DB 时走 ':memory:'，手工实跑命令路径同样通过。"""
    with tempfile.TemporaryDirectory(prefix="更夫周期巡检内存库-"):
        # 临时目录仅用于约束子进程不写项目文件；数据库路径环境变量不注入。
        进程 = _启动(None)
        标准输出, 标准错误 = _回收(进程)

    assert 进程.returncode == 0, (
        f"内存库模式真子进程退出码 {进程.returncode}；stderr={标准错误!r}"
    )
    assert "失败: 0" in 标准输出, f"内存库模式存在失败用例：{标准输出!r}"
    统计 = _中文统计(标准输出)
    assert 统计["巡检轮次"] >= 3, f"内存库模式轮次不足：{统计}"
    assert 统计["落库nudge"] >= 1 and 统计["落库alert"] >= 1, (
        f"内存库模式落库计数异常：{统计}"
    )
