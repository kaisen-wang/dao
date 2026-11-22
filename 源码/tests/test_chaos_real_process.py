"""更夫 Nightwatch — 真实 OS 进程 kill -9 混沌测试（第八轮）。

覆盖共享契约《迭代规约-真实验收.md》§2 A：
- 用 ``sys.executable`` 启动真实 Python 子进程运行道语言工作负载（不硬编码 .venv 路径）；
- 子进程 cwd 为 ``示例/更夫``，道语言模块搜索基于 os.getcwd()；
- 工作负载把 Outbox 落库（一条已投递、一条未投递）后保持存活，
  测试侧发真实 SIGKILL（``proc.kill()``）并确认退出码为 -9；
- 重启另一个真实进程从 SQLite 持久化存储恢复，按原幂等键重投验证不重复、补投未投递验证不丢失；
- 每轮用 ``tempfile.TemporaryDirectory()`` 隔离数据库与脚本，退出自动清理，项目目录不产生 .db。

诚实边界：本地开发机上的真实 kill -9 只覆盖「进程被外部信号强杀后本地 SQLite 恢复」这一条路径，
不等于生产环境 ×10 全场景（断网、外部真实消息计数、云主机守护重启等仍未验证）。
"""

import os
import signal
import sqlite3
import subprocess
import sys
import tempfile
import time
from pathlib import Path

import pytest

# 源码/tests/test_chaos_real_process.py -> 仓库根目录
PROJECT_ROOT = Path(__file__).resolve().parents[2]
MAIN = PROJECT_ROOT / "源码" / "main.py"
GENGFU_DIR = PROJECT_ROOT / "示例" / "更夫"

# 工作负载通过环境变量接收本轮临时目录与轮次（用 ASCII 名避免跨平台环境变量编码差异）。
ENV_DB = "GENGFU_CHAOS_DB"
ENV_ROUND = "GENGFU_CHAOS_ROUND"

# 道语言工作负载：写 Outbox（一条已投递 + 一条未投递）后保持存活，等待被 SIGKILL。
# 睡眠() 与 打印() 为道语言内置函数，无需从「时间」导入（重复导入会触发重定义）。
WORKER_SCRIPT = """\
// 真实进程混沌测试 — 工作负载（由 Python 测试在 tempfile 中生成）。
从 系统 导入 取环境变量
从 基础设施层.存储 导入 打开存储, 投递入队, 标记投递

定义 数据库路径 = 取环境变量("GENGFU_CHAOS_DB", "")
定义 轮次 = 取环境变量("GENGFU_CHAOS_ROUND", "0")
定义 存储 = 打开存储(数据库路径)
定义 已投递键 = `混沌-已投递-{轮次}`
定义 未投递键 = `混沌-未投递-{轮次}`

// 一条先落库再标记为已投递；另一条落库后保持 pending（崩溃时未投递）。
定义 已投递ID = 投递入队(`T-混沌-{轮次}`, "通知", `已投递载荷-{轮次}`, 已投递键)
标记投递(已投递ID)
定义 未投递ID = 投递入队(`T-混沌-{轮次}`, "通知", `未投递载荷-{轮次}`, 未投递键)

// 主线程保持存活，等待 Python 侧 proc.kill() 发送真实 SIGKILL。
遍历 i 从 1 到 100000
    睡眠(0.02)
"""

# 道语言恢复负载：模拟重启，重新打开同一个 SQLite 库，走恢复检查点，
# 并按原幂等键重投（验证不重复）、把崩溃前未投递的消息补投出去（验证不丢失）。
RECOVERY_SCRIPT = """\
// 真实进程混沌测试 — 重启恢复负载（由 Python 测试在 tempfile 中生成）。
从 系统 导入 取环境变量
从 基础设施层.存储 导入 打开存储, 投递入队, 标记投递
从 应用层.恢复 导入 恢复检查点

定义 数据库路径 = 取环境变量("GENGFU_CHAOS_DB", "")
定义 轮次 = 取环境变量("GENGFU_CHAOS_ROUND", "0")
定义 存储 = 打开存储(数据库路径)
定义 恢复结果 = 恢复检查点()
定义 已投递键 = `混沌-已投递-{轮次}`
定义 未投递键 = `混沌-未投递-{轮次}`

// 按原幂等键重投：幂等生效时应返回原 ID，不新增行。
定义 已投递ID2 = 投递入队(`T-混沌-{轮次}`, "通知", `重启重复投递-{轮次}`, 已投递键)
定义 未投递ID2 = 投递入队(`T-混沌-{轮次}`, "通知", `重启补投-{轮次}`, 未投递键)
标记投递(未投递ID2)

打印(`恢复完成 已投递ID={已投递ID2} 未投递ID={未投递ID2}`)
"""


def _启动工作负载(脚本路径: Path, 数据库路径: Path, 轮次: int) -> subprocess.Popen:
    """用 sys.executable 启动真实 Python 子进程运行道语言脚本。"""
    环境变量 = os.environ.copy()
    环境变量["PYTHONPATH"] = str(MAIN.parent)
    环境变量[ENV_DB] = str(数据库路径)
    环境变量[ENV_ROUND] = str(轮次)
    环境变量["GENGFU_NO_LLM"] = "1"  # 不依赖真实网络 / ollama
    return subprocess.Popen(
        [sys.executable, str(MAIN), str(脚本路径)],
        cwd=str(GENGFU_DIR),
        env=环境变量,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )


def _等待outbox落库(数据库路径: Path, 幂等键列表: list[str], 超时秒: float = 1.2) -> bool:
    """轮询 SQLite，等待工作负载把两条消息落库并提交。"""
    截止 = time.monotonic() + 超时秒
    while time.monotonic() < 截止:
        try:
            with sqlite3.connect(str(数据库路径), timeout=0.2) as 连接:
                行列表 = 连接.execute(
                    "SELECT 幂等键 FROM outbox WHERE 幂等键 IN (?, ?)", 幂等键列表
                ).fetchall()
            if {键 for (键,) in 行列表} == set(幂等键列表):
                return True
        except sqlite3.Error:
            # 库尚未建表或工作负载正在建表，稍后重试。
            pass
        time.sleep(0.02)
    return False


def _读outbox(数据库路径: Path, 幂等键列表: list[str]) -> list[tuple]:
    """用 Python 直接读 SQLite 检查 outbox 表的最终状态。"""
    with sqlite3.connect(str(数据库路径), timeout=1) as 连接:
        return 连接.execute(
            "SELECT id, 幂等键, 状态, 内容 FROM outbox "
            "WHERE 幂等键 IN (?, ?) ORDER BY 幂等键",
            幂等键列表,
        ).fetchall()


@pytest.mark.parametrize("轮次", range(1, 11))
def test_真实kill9与持久化恢复(轮次: int):
    """真实 kill -9 ×10：退出码 -9；重启后已投递不重复、未投递不丢失。"""
    开始时间 = time.monotonic()
    with tempfile.TemporaryDirectory(prefix=f"更夫混沌-{轮次}-") as 临时目录:
        临时路径 = Path(临时目录)
        工作负载 = 临时路径 / "工作负载.道"
        恢复脚本 = 临时路径 / "恢复.道"
        数据库 = 临时路径 / "混沌.db"  # 每轮独立，项目目录不产生 .db
        工作负载.write_text(WORKER_SCRIPT, encoding="utf-8")
        恢复脚本.write_text(RECOVERY_SCRIPT, encoding="utf-8")

        已投递键 = f"混沌-已投递-{轮次}"
        未投递键 = f"混沌-未投递-{轮次}"
        幂等键列表 = [已投递键, 未投递键]

        # --- 阶段一：真实子进程写入 Outbox 后被真实 SIGKILL ---
        工作进程 = _启动工作负载(工作负载, 数据库, 轮次)
        try:
            assert _等待outbox落库(数据库, 幂等键列表), (
                f"第 {轮次} 轮：工作负载未在时限内写入 Outbox"
            )
            # 记录 kill 前的投递 ID，用于验证重启重投没有新建行。
            with sqlite3.connect(str(数据库), timeout=1) as 连接:
                kill前ID = dict(
                    连接.execute(
                        "SELECT 幂等键, id FROM outbox WHERE 幂等键 IN (?, ?)", 幂等键列表
                    ).fetchall()
                )
        finally:
            # 即使上面的断言失败，也要杀掉并回收进程，避免进程泄漏。
            if 工作进程.poll() is None:
                工作进程.kill()
            工作输出, 工作错误 = 工作进程.communicate(timeout=5)

        assert 工作进程.returncode == -signal.SIGKILL, (
            f"第 {轮次} 轮：期望退出码 -9（SIGKILL），实际 {工作进程.returncode}；"
            f"stdout={工作输出!r} stderr={工作错误!r}"
        )

        # --- 阶段二：重启真实进程，从持久化存储恢复 ---
        恢复进程 = _启动工作负载(恢复脚本, 数据库, 轮次)
        恢复输出, 恢复错误 = 恢复进程.communicate(timeout=10)
        assert 恢复进程.returncode == 0, (
            f"第 {轮次} 轮：恢复进程退出码 {恢复进程.returncode}；"
            f"stdout={恢复输出!r} stderr={恢复错误!r}"
        )

        # --- 阶段三：Python 直接读 SQLite 校验幂等与不丢失 ---
        最终行 = _读outbox(数据库, 幂等键列表)
        按键 = {行[1]: 行 for 行 in 最终行}
        assert set(按键) == set(幂等键列表), f"第 {轮次} 轮：恢复后有幂等键丢失：{按键}"
        assert len(最终行) == 2, f"第 {轮次} 轮：恢复后 outbox 出现重复行：{最终行}"

        # ID 未变 → 重启重投命中幂等，没有新建投递行（重复数 = 0）。
        assert 按键[已投递键][0] == kill前ID[已投递键]
        assert 按键[未投递键][0] == kill前ID[未投递键]
        assert 按键[已投递键][2] == "sent", "已投递消息状态应保持 sent"
        assert 按键[未投递键][2] == "sent", "未投递消息应在重启后被补投"
        assert 按键[未投递键][3] == f"未投递载荷-{轮次}", "未投递消息载荷不应丢失或被改写"

        with sqlite3.connect(str(数据库), timeout=1) as 连接:
            总行数 = 连接.execute("SELECT COUNT(*) FROM outbox").fetchone()[0]
        assert 总行数 == 2, f"第 {轮次} 轮：outbox 总行数应为 2，实际 {总行数}"

        恢复率 = len(按键) / len(幂等键列表)
        重复数 = len(最终行) - len(按键)
        丢失数 = len(幂等键列表) - len(按键)
        耗时 = time.monotonic() - 开始时间
        print(
            f"第 {轮次:2d} 轮：恢复率={恢复率:.0%} 重复数={重复数} "
            f"丢失数={丢失数} 耗时={耗时:.2f}s"
        )
