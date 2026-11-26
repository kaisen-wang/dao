"""更夫 Nightwatch — 第十一轮 · observe 审计 SQLite 真跨进程恢复一致性（子代理 A / crossproc-audit）。

覆盖共享契约《迭代规约-第十一轮.md》§2 A，弥补第十轮「同进程内新建审计器模拟跨进程恢复」的诚实缺口：
- 用 sys.executable 启动两个**独立 OS 进程**运行 .道 工作负载（cwd=示例/更夫）：
  Writer 进程写入 7 天 × 四类明细（30 条）后**正常退出**；Reader 进程在 writer 退出后另起，
  重新打开同一个 SQLite 库，.恢复审计() 后 .生成报告() + .持久化统计()。
- 用 ASCII 环境变量 GENGFU_CP_DB / GENGFU_CP_OUT 传库路径与结果路径；
  .道 工作负载由测试在 tempfile.TemporaryDirectory() 内生成，退出自动清理，项目目录不留 .db。
- 六个用例：恢复条数一致；四类计数/总数一致；误接受率一致；持久化统计落库条数一致；
  空库 reader 降级；重复 reader 幂等（确认读库不修改 writer 数据）。

诚实边界（重要）：
- 这里是「真 OS 进程 + 本地 SQLite」，只验证本机跨进程恢复路径的一致性；
  压缩模拟流 ≠ 真实一周 observe 运行，也 ≠ 生产环境多机 / 长周期审计。
- 不勾选 PRD §12 任何 DoD 项；真实一周 observe 仍为未完成项。

跨平台约定：一律用 sys.executable 启动子进程，禁止硬编码 .venv/bin/python；
禁止 signal.SIGKILL / os.kill(pid, SIGKILL)；停止子进程用 proc.terminate() 并超时 fallback proc.kill()；
单用例 ≤5 秒；所有断言消息用中文。
"""

import json
import os
import sqlite3
import subprocess
import sys
import tempfile
from pathlib import Path

import pytest

# 源码/tests/test_observe_cross_process.py -> 仓库根目录
PROJECT_ROOT = Path(__file__).resolve().parents[2]
MAIN = PROJECT_ROOT / "源码" / "main.py"
GENGFU_DIR = PROJECT_ROOT / "示例" / "更夫"
sys.path.insert(0, str(MAIN.parent))

# ASCII 环境变量名，避免跨平台环境变量编码差异；值由测试传入的临时目录决定。
ENV_DB = "GENGFU_CP_DB"
ENV_OUT = "GENGFU_CP_OUT"
MARKER = "GENGFU_CP_JSON:"

# 验证口径（与 测试/测试观察审计持久化.道 一致）：总数 30 / 9-3-17-1，误接受率 0.15。
期望总数 = 30
期望正确接受 = 9
期望误接受 = 3
期望正确忽略 = 17
期望误忽略 = 1
期望误接受率 = 0.15
期望误忽略率 = 0.1

# Writer 工作负载：真 OS 进程写入一周模拟流后正常退出（脚本执行完自然结束）。
# 结果同时写到文件（GENGFU_CP_OUT）并打印到 stdout；Python 侧以 stdout 为主、文件为备份。
WRITER_SCRIPT = """\
// 跨进程恢复测试 — Writer 工作负载（由 Python 测试在 tempfile 中生成）。
// 真 OS 进程：写入 7 天 × 四类明细后正常退出，进程真实结束。
从 系统 导入 取环境变量
从 文件 导入 写入
从 编码 导入 JSON
从 应用层.观察审计 导入 创建持久观察审计, 审计一周模拟流

定义 数据库路径 = 取环境变量("GENGFU_CP_DB", "")
定义 输出路径 = 取环境变量("GENGFU_CP_OUT", "")

定义 审计 = 创建持久观察审计(数据库路径, "跨进程writer")
定义 写入总数 = 审计一周模拟流(审计, [1,1,1,1,1,2,2], [0,1,0,1,0,1,0], [3,2,3,2,3,2,2], [0,0,0,0,1,0,0])

定义 结果 = {"进程": "writer", "写入总数": 写入总数, "报告": 审计.生成报告(), "统计": 审计.持久化统计()}
定义 载荷文本 = JSON.编码(结果)
尝试
    写入(输出路径, 载荷文本)
捕获 错误
    定义 忽略写文件 = 错误
打印(`GENGFU_CP_JSON:{载荷文本}`)
如果 审计.连接 != 空
    尝试
        审计.连接.关闭()
    捕获 错误
        定义 忽略关闭 = 错误
"""

# Reader 工作负载：writer 退出后另起的真 OS 进程，重新打开同一个库，
# .恢复审计() 后生成报告与持久化统计（纯读，不写明细）。
READER_SCRIPT = """\
// 跨进程恢复测试 — Reader 工作负载（writer 退出后另起）。
// 重新打开同一个 SQLite 库，从磁盘恢复审计明细并打印报告与统计。
从 系统 导入 取环境变量
从 文件 导入 写入
从 编码 导入 JSON
从 应用层.观察审计 导入 创建持久观察审计

定义 数据库路径 = 取环境变量("GENGFU_CP_DB", "")
定义 输出路径 = 取环境变量("GENGFU_CP_OUT", "")

定义 审计 = 创建持久观察审计(数据库路径, "跨进程reader")
定义 恢复条数 = 审计.恢复审计()

定义 结果 = {"进程": "reader", "恢复条数": 恢复条数, "报告": 审计.生成报告(), "统计": 审计.持久化统计()}
定义 载荷文本 = JSON.编码(结果)
尝试
    写入(输出路径, 载荷文本)
捕获 错误
    定义 忽略写文件 = 错误
打印(`GENGFU_CP_JSON:{载荷文本}`)
如果 审计.连接 != 空
    尝试
        审计.连接.关闭()
    捕获 错误
        定义 忽略关闭 = 错误
"""


def _启动工作负载(脚本路径: Path, 数据库路径: Path, 输出路径: Path) -> subprocess.Popen:
    """用 sys.executable 启动真实 Python 子进程运行 .道 工作负载（cwd=示例/更夫）。"""
    环境变量 = os.environ.copy()
    环境变量["PYTHONPATH"] = str(MAIN.parent)
    环境变量[ENV_DB] = str(数据库路径)
    环境变量[ENV_OUT] = str(输出路径)
    环境变量["GENGFU_NO_LLM"] = "1"  # 不依赖真实网络 / ollama
    return subprocess.Popen(
        [sys.executable, str(MAIN), str(脚本路径)],
        cwd=str(GENGFU_DIR),
        env=环境变量,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )


def _运行工作负载(脚本路径: Path, 数据库路径: Path, 输出路径: Path, 超时秒: float = 5.0) -> dict:
    """启动工作负载、等待其真实结束（正常退出），并解析 JSON 结果。"""
    进程 = _启动工作负载(脚本路径, 数据库路径, 输出路径)
    try:
        标准输出, 标准错误 = 进程.communicate(timeout=超时秒)
    except subprocess.TimeoutExpired:
        # 跨平台回收：先 terminate()，超时才 fallback kill()；不使用 SIGKILL。
        if 进程.poll() is None:
            进程.terminate()
            try:
                进程.communicate(timeout=1)
            except subprocess.TimeoutExpired:
                进程.kill()
                进程.communicate(timeout=1)
        pytest.fail(f"工作负载 {脚本路径.name} 超过 {超时秒} 秒未结束（已 terminate/kill 回收）")

    assert 进程.returncode == 0, (
        f"工作负载 {脚本路径.name} 未正常退出：退出码 {进程.returncode}；"
        f"stdout={标准输出!r} stderr={标准错误!r}"
    )

    # 以 stdout 的标记行为主解析（契约要求解析两个进程的 stdout）。
    for 行 in 标准输出.splitlines():
        if 行.startswith(MARKER):
            try:
                return json.loads(行[len(MARKER):])
            except json.JSONDecodeError as 错误:
                pytest.fail(f"工作负载 {脚本路径.name} 的 JSON 结果无法解析：{错误}；原始行={行!r}")

    # stdout 没有标记行时退回结果文件，保证测试稳定。
    if 输出路径.exists():
        return json.loads(输出路径.read_text(encoding="utf-8"))

    pytest.fail(
        f"工作负载 {脚本路径.name} 的 stdout 未找到 {MARKER} 标记行且结果文件不存在；"
        f"stdout={标准输出!r} stderr={标准错误!r}"
    )


@pytest.fixture(scope="module")
def 跨进程结果():
    """模块级共享：writer 真进程写完并正常退出后，再起 reader 真进程读同库。"""
    with tempfile.TemporaryDirectory(prefix="更夫跨进程观察审计-") as 临时目录:
        临时路径 = Path(临时目录)
        写脚本 = 临时路径 / "writer.道"
        读脚本 = 临时路径 / "reader.道"
        写脚本.write_text(WRITER_SCRIPT, encoding="utf-8")
        读脚本.write_text(READER_SCRIPT, encoding="utf-8")

        数据库 = 临时路径 / "observe.db"
        # communicate() 等 writer 进程真实结束后才启动 reader，确保是两个独立 OS 进程。
        写结果 = _运行工作负载(写脚本, 数据库, 临时路径 / "writer.json")
        读结果 = _运行工作负载(读脚本, 数据库, 临时路径 / "reader.json")
        yield {
            "writer": 写结果,
            "reader": 读结果,
            "数据库": 数据库,
            "读脚本": 读脚本,
            "临时路径": 临时路径,
        }


def test_跨进程恢复条数一致(跨进程结果):
    """用例 1：writer 正常退出写入 30 条；reader 恢复条数与写入数一致。"""
    assert 跨进程结果["writer"]["写入总数"] == 期望总数, "writer 一周模拟流写入数应为 30"
    assert 跨进程结果["reader"]["恢复条数"] == 跨进程结果["writer"]["写入总数"], (
        "reader 跨进程恢复条数应等于 writer 写入条数"
    )
    assert 跨进程结果["reader"]["恢复条数"] == 期望总数, "reader 恢复条数应为 30"


def test_四类计数与总数一致(跨进程结果):
    """用例 2：reader 报告的四类计数与总数与 writer 完全一致。"""
    写报告 = 跨进程结果["writer"]["报告"]
    读报告 = 跨进程结果["reader"]["报告"]
    for 字段 in ["总数", "正确接受", "误接受", "正确忽略", "误忽略"]:
        assert 读报告[字段] == 写报告[字段], f"跨进程恢复后「{字段}」应与 writer 一致"
    assert 读报告["总数"] == 期望总数
    assert 读报告["正确接受"] == 期望正确接受
    assert 读报告["误接受"] == 期望误接受
    assert 读报告["正确忽略"] == 期望正确忽略
    assert 读报告["误忽略"] == 期望误忽略


def test_误接受率一致(跨进程结果):
    """用例 3：reader 的误接受率 / 误忽略率与 writer 一致，且符合一周流口径。"""
    写报告 = 跨进程结果["writer"]["报告"]
    读报告 = 跨进程结果["reader"]["报告"]
    assert 读报告["误接受率"] == 写报告["误接受率"], "跨进程恢复后误接受率应一致"
    assert 读报告["误忽略率"] == 写报告["误忽略率"], "跨进程恢复后误忽略率应一致"
    assert 读报告["误接受率"] == 期望误接受率, "误接受率应为 0.15"
    assert 读报告["误忽略率"] == 期望误忽略率, "误忽略率应为 0.1"


def test_持久化统计落库条数一致(跨进程结果):
    """用例 4：.持久化统计() 的落库条数与四类分布，跨进程一致。"""
    写统计 = 跨进程结果["writer"]["统计"]
    读统计 = 跨进程结果["reader"]["统计"]
    assert 读统计["落库条数"] == 写统计["落库条数"], "reader 落库条数应与 writer 一致"
    assert 读统计["落库条数"] == 期望总数, "落库条数应为 30"
    for 类别 in ["正确接受", "误接受", "正确忽略", "误忽略"]:
        assert 读统计["各类别"][类别] == 写统计["各类别"][类别], f"落库类别「{类别}」条数应一致"
    assert 读统计["落库条数"] == 跨进程结果["reader"]["报告"]["总数"], "落库条数应与报告总数一致"


def test_空库reader降级():
    """用例 5：新临时空库上 reader 恢复 0 条、报告总数 0，不抛异常、正常退出。"""
    with tempfile.TemporaryDirectory(prefix="更夫跨进程空库-") as 临时目录:
        临时路径 = Path(临时目录)
        读脚本 = 临时路径 / "reader.道"
        读脚本.write_text(READER_SCRIPT, encoding="utf-8")
        结果 = _运行工作负载(读脚本, 临时路径 / "空库.db", 临时路径 / "空库结果.json")
        assert 结果["恢复条数"] == 0, "空库恢复条数应为 0"
        assert 结果["报告"]["总数"] == 0, "空库报告总数应为 0"
        assert 结果["统计"]["落库条数"] == 0, "空库落库条数应为 0"


def test_重复reader幂等(跨进程结果):
    """用例 6：重复 reader 结果相同，且读库不修改 writer 数据。"""
    with sqlite3.connect(str(跨进程结果["数据库"]), timeout=1) as 连接:
        首次落库数 = 连接.execute("SELECT COUNT(*) FROM 观察审计明细").fetchone()[0]
    assert 首次落库数 == 期望总数, "writer 写入后落库条数应为 30"

    读脚本 = 跨进程结果["读脚本"]
    临时路径 = 跨进程结果["临时路径"]
    数据库 = 跨进程结果["数据库"]
    第一次 = _运行工作负载(读脚本, 数据库, 临时路径 / "reader-1.json")
    第二次 = _运行工作负载(读脚本, 数据库, 临时路径 / "reader-2.json")

    assert 第一次 == 第二次, "重复 reader 的恢复/报告/统计结果应完全一致（幂等）"
    assert 第二次["恢复条数"] == 期望总数, "重复 reader 恢复条数仍应为 30"
    with sqlite3.connect(str(数据库), timeout=1) as 连接:
        再次落库数 = 连接.execute("SELECT COUNT(*) FROM 观察审计明细").fetchone()[0]
    assert 再次落库数 == 首次落库数, "reader 只读库，不应改变落库条数"
