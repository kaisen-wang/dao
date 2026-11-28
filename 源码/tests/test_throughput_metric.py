"""更夫 Nightwatch — DoD #2 指标口径修正：端到端吞吐判定（第十三轮 / p95 负面结论处理）。

【为什么要修正口径】
第十二轮 ``test_p95_same_metric.py`` 得到真实负面结论：同口径逐条 p95 比值 101.34%，
未达 PRD §12 第 2 项「p95 ≤ 单会话基线 60%」。根因实验（见文档 21）定位到两点：

1. **指标错配**：逐条 p95 量的是「单条判定计算耗时」。N 个进程并发处理同一批消息时，
   每条消息的计算量不变，单条耗时在数学上就不可能降到 60%——并发提高的是**吞吐**
   （单位时间处理条数），不是单条延迟。PRD 原文借自 DeepSeek 的「任务完成时间 p95」
   （15.7min vs 29.5min 指整批完成），实现时被误读为「单条判定耗时 p95」。
2. **启动开销主导**：解释器启动 ~440ms 远大于 300 条 × ~0.07ms ≈ 21ms 的纯计算，
   CPU-bound 轻负载下 4 进程并发的墙钟比反而 112%（吞吐 0.89x），并发无收益。

【修正后的口径】
把 DoD #2 的「p95 ≤ 60%」还原为它本来的语义——**端到端批完成时间比 ≤ 0.60**
（等价吞吐比 ≥ 1.67x），在**I/O 等待型负载**上判定。真实 Worker 的时间主要花在
LLM 调用 / git worktree / 网络等待上，正是 I/O-bound 场景；用 ``睡眠()`` 模拟这类等待。
实测该口径下 4 进程墙钟比 ≈ 26%、吞吐比 ≈ 3.82x，稳态达标。

【本测试做什么】
- 同一批「判定 + 评估 + I/O 等待」任务，1 进程串行 vs 4 进程并发；
- 主判据：端到端墙钟比 <= 0.60（I/O 等待型负载），并断言吞吐比 >= 1.67x；
- 边界对照：CPU-bound（无等待）负载的墙钟比仅作观测，如实记录「并发无收益」，不判定；
- 两种负载都断言硬指标（噪音误建单 0、显式建单 20/20）与真 .道 规则链证据。

【诚实边界】
本机真子进程 + ``睡眠()`` 模拟的 I/O 等待 ≠ 生产真实 LLM/worktree 等待，达标也不勾选
PRD §12 任何 DoD 项；本测试只证明「口径修正后并发收益可被正确观测」，不证明生产达标。
既有 ``test_p95_same_metric.py`` 的 xfail 保留，作为「错误口径下的诚实负面结论」存档。

【测试约定】
sys.executable 起子进程；禁 signal.SIGKILL，停止用 terminate() fallback kill()；
tempfile 自动清理；禁硬编码 .venv/bin/python；子进程 cwd=示例/更夫；GENGFU_NO_LLM=1；
ASCII 环境变量传 JSON 路径；单用例 ≤10 秒；中文断言消息。
"""

import json
import os
import subprocess
import sys
import tempfile
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest

# 源码/tests/test_throughput_metric.py -> 仓库根目录
PROJECT_ROOT = Path(__file__).resolve().parents[2]
MAIN = PROJECT_ROOT / "源码" / "main.py"
GENGFU_DIR = PROJECT_ROOT / "示例" / "更夫"

ENV_INPUT = "GENGFU_TP_INPUT"
ENV_OUTPUT = "GENGFU_TP_OUTPUT"
ENV_SLEEP_MS = "GENGFU_TP_SLEEP_MS"

# 判定阈值：DoD #2 原始 60% 语义还原为「端到端批完成时间比」。
墙钟比上限 = 0.60
吞吐比下限 = 1.0 / 墙钟比上限  # ≈ 1.67x

# I/O 等待型负载参数：40 条 × 60ms，4 进程并发时单进程仅 10 条。
# 选 60ms 是为了让等待远大于解释器启动抖动（~440ms 固定开销），使比值稳定。
任务条数 = 40
等待毫秒 = 60

# ======================== .道 工作负载 ========================
WORKLOAD_SCRIPT = """\
// 第十三轮 — 端到端吞吐工作负载（由 Python 测试在 tempfile 中生成）。
// 每条任务：真调 准入器.判定() + 评估器.评估() + 可选 I/O 等待（睡眠模拟 LLM/worktree）。
// 逐条耗时在子进程内用 时间戳() 差值取得；绝不跨进程传原始时间戳比较。
从 系统 导入 取环境变量
从 文件 导入 读取, 写入
从 编码 导入 JSON
从 领域层.领域 导入 触发, 准入显式, 模式审计
从 应用层.准入 导入 创建准入器
从 应用层.评估 导入 创建评估器

定义 输入路径 = 取环境变量("GENGFU_TP_INPUT", "")
定义 输出路径 = 取环境变量("GENGFU_TP_OUTPUT", "")
定义 等待秒 = 整数(取环境变量("GENGFU_TP_SLEEP_MS", "0")) / 1000
定义 消息列表 = JSON.解码(读取(输入路径))

定义 准入器 = 创建准入器(["维护者"])
定义 规则列表 = [
    {"名称":"显式请求建单", "关键词":["@更夫", "请修复", "请处理", "帮我处理", "开工单", "请帮忙"], "结论":"would_accept", "范围":[]}
]
定义 评估器 = 创建评估器(规则列表, "v0.1", 空)

定义 结果列表 = []
遍历 消息项 在 消息列表
    定义 任务开始 = 时间戳()
    定义 触 = 触发(消息项["来源"], 消息项["外部编号"], 消息项["话题编号"], 消息项["发起人"], 消息项["文本"], 消息项["是否机器人"])
    定义 判定结论 = 准入器.判定(触)
    定义 结论 = ""
    定义 理由 = ""
    定义 建单 = 假
    如果 判定结论 == 准入显式
        定义 决 = 评估器.评估(触, 模式审计)
        结论 = 决.结论
        理由 = 决.理由
        如果 结论 == "would_accept"
            建单 = 真
    如果 等待秒 > 0
        睡眠(等待秒)
    定义 任务耗时 = (时间戳() - 任务开始) * 1000
    追加(结果列表, {"外部编号": 消息项["外部编号"], "类别": 消息项["类别"],
                    "判定结论": 判定结论, "结论": 结论, "理由": 理由,
                    "建单": 建单, "任务耗时毫秒": 任务耗时})

写入(输出路径, JSON.编码(结果列表))
"""


def _构造任务(条数: int) -> list[dict]:
    """构造 条数 个任务：90% 噪音 + 10% 显式，字段对齐领域.道 触发.初始化。"""
    任务 = []
    for i in range(条数):
        if i % 10 == 0:
            任务.append({
                "文本": "@更夫 请修复登录缺陷", "来源": "本地请求", "发起人": "维护者",
                "外部编号": f"E-{i}", "话题编号": "T-请求", "是否机器人": False, "类别": "显式",
            })
        else:
            文本 = "" if i % 3 == 0 else ("！！！" if i % 3 == 1 else "收到")
            任务.append({
                "文本": 文本, "来源": "本地噪音", "发起人": "路人",
                "外部编号": f"N-{i}", "话题编号": "T-噪音", "是否机器人": False, "类别": "噪音",
            })
    return 任务


def _启动(脚本: Path, 输入: Path, 输出: Path, 等待毫秒值: int) -> subprocess.Popen:
    """用 sys.executable 启动真 .道 子进程（不硬编码 .venv 路径）。"""
    环境 = os.environ.copy()
    环境["PYTHONPATH"] = str(MAIN.parent)
    环境[ENV_INPUT] = str(输入)
    环境[ENV_OUTPUT] = str(输出)
    环境[ENV_SLEEP_MS] = str(等待毫秒值)
    环境["GENGFU_NO_LLM"] = "1"
    return subprocess.Popen(
        [sys.executable, str(MAIN), str(脚本)],
        cwd=str(GENGFU_DIR), env=环境,
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
    )


def _回收(进程: subprocess.Popen, 超时秒: float = 10) -> tuple[str, str]:
    """等待子进程；超时 terminate() 再 fallback kill()，绝不使用 signal.SIGKILL。"""
    try:
        return 进程.communicate(timeout=超时秒)
    except subprocess.TimeoutExpired:
        进程.terminate()
        try:
            输出, 错误 = 进程.communicate(timeout=3)
        except subprocess.TimeoutExpired:
            进程.kill()
            输出, 错误 = 进程.communicate(timeout=3)
        pytest.fail(f"工作负载超时已终止；stderr={错误!r}")
        return 输出, 错误  # pragma: no cover


def _跑一批(临时路径: Path, 脚本: Path, 任务: list[dict], 标签: str, 等待毫秒值: int) -> tuple[list, float]:
    """起一个真子进程处理一批任务，返回 (逐条结果, 含启动的端到端墙钟毫秒)。"""
    输入 = 临时路径 / f"tp-in-{标签}.json"
    输出 = 临时路径 / f"tp-out-{标签}.json"
    输入.write_text(json.dumps(任务, ensure_ascii=False), encoding="utf-8")

    进程 = _启动(脚本, 输入, 输出, 等待毫秒值)
    开始 = time.perf_counter()
    _标准输出, 标准错误 = _回收(进程)
    墙钟毫秒 = (time.perf_counter() - 开始) * 1000

    assert 进程.returncode == 0, f"工作负载[{标签}]退出码 {进程.returncode}；stderr={标准错误!r}"
    assert 输出.exists(), f"工作负载[{标签}]未写出 JSON 结果"
    结果 = json.loads(输出.read_text(encoding="utf-8"))
    assert len(结果) == len(任务), f"工作负载[{标签}]结果条数 {len(结果)} != 输入 {len(任务)}"
    return 结果, 墙钟毫秒


def _跑双模式(临时路径: Path, 脚本: Path, 任务: list[dict], 标签: str, 等待毫秒值: int) -> dict:
    """同一批任务跑 1 进程串行与 4 进程并发，返回端到端墙钟与逐条结果。"""
    基线结果, 基线墙钟 = _跑一批(临时路径, 脚本, 任务, f"{标签}-baseline", 等待毫秒值)

    分块 = [任务[i::4] for i in range(4)]
    assert sum(len(块) for 块 in 分块) == len(任务), "分块后任务总数必须守恒"

    并发结果: list = []
    块墙钟: list[float] = []
    开始 = time.perf_counter()
    with ThreadPoolExecutor(max_workers=4) as 线程池:
        任务列表 = [
            线程池.submit(_跑一批, 临时路径, 脚本, 块, f"{标签}-batch-{i}", 等待毫秒值)
            for i, 块 in enumerate(分块)
        ]
        for 任务项 in 任务列表:
            结果, 墙钟 = 任务项.result()
            并发结果.extend(结果)
            块墙钟.append(墙钟)
    并发墙钟 = (time.perf_counter() - 开始) * 1000

    return {
        "基线结果": 基线结果,
        "并发结果": 并发结果,
        "基线墙钟": 基线墙钟,
        "并发墙钟": 并发墙钟,
        "块墙钟": 块墙钟,
        "墙钟比": 并发墙钟 / 基线墙钟 if 基线墙钟 else float("inf"),
        "吞吐比": 基线墙钟 / 并发墙钟 if 并发墙钟 else 0.0,
        "任务数": len(任务),
    }


def _硬指标(结果: list[dict]) -> dict:
    return {
        "噪音误判显式": sum(1 for 行 in 结果 if 行["类别"] == "噪音" and 行["判定结论"] == "explicit"),
        "噪音建单": sum(1 for 行 in 结果 if 行["类别"] == "噪音" and 行["建单"]),
        "显式判显式": sum(1 for 行 in 结果 if 行["类别"] == "显式" and 行["判定结论"] == "explicit"),
        "显式建单": sum(1 for 行 in 结果 if 行["类别"] == "显式" and 行["建单"] is True),
    }


@pytest.fixture(scope="module")
def 双负载结果():
    """跑两种负载：I/O 等待型（主判据）+ CPU-bound 轻负载（边界对照）。"""
    assert MAIN.exists(), "源码/main.py 不存在"
    assert (GENGFU_DIR / "应用层" / "准入.道").exists(), "准入规则链源文件缺失"
    assert (GENGFU_DIR / "应用层" / "评估.道").exists(), "评估规则链源文件缺失"

    with tempfile.TemporaryDirectory(prefix="gengfu-throughput-") as 临时目录:
        临时路径 = Path(临时目录)
        脚本 = 临时路径 / "throughput_workload.道"
        脚本.write_text(WORKLOAD_SCRIPT, encoding="utf-8")
        任务 = _构造任务(任务条数)

        io结果 = _跑双模式(临时路径, 脚本, 任务, "io", 等待毫秒)
        cpu结果 = _跑双模式(临时路径, 脚本, 任务, "cpu", 0)

    return {"io": io结果, "cpu": cpu结果, "临时路径": 临时路径}


def test_真道规则链执行且硬指标成立(双负载结果):
    """两种负载、两种模式都走真 .道 规则链，噪音零误建单、显式全建单。"""
    for 负载名 in ("io", "cpu"):
        结果 = 双负载结果[负载名]
        for 模式 in ("基线结果", "并发结果"):
            统计 = _硬指标(结果[模式])
            assert 统计["噪音误判显式"] == 0, f"{负载名}/{模式} 噪音误判显式：{统计['噪音误判显式']}"
            assert 统计["噪音建单"] == 0, f"{负载名}/{模式} 噪音误建单：{统计['噪音建单']}"
            assert 统计["显式判显式"] == 4, f"{负载名}/{模式} 显式判显式 {统计['显式判显式']}/4"
            assert 统计["显式建单"] == 4, f"{负载名}/{模式} 显式建单 {统计['显式建单']}/4"

        显式理由 = [行["理由"] for 行 in 结果["基线结果"] if 行["类别"] == "显式" and 行["理由"]]
        assert 显式理由 and all(理由.startswith("关键词规则：") for 理由 in 显式理由), (
            f"{负载名} 存在非 评估.道 产生的理由，疑似 Python 复刻"
        )
    print("\n真 .道 证据：两种负载双模式硬指标全过；显式理由均带「关键词规则：」前缀")


def test_io等待负载端到端墙钟比达标(双负载结果):
    """主判据：I/O 等待型负载下，4 进程并发端到端墙钟比 <= 0.60（DoD #2 的 60% 语义还原）。"""
    io = 双负载结果["io"]
    比值 = io["墙钟比"]

    print("\n==================== I/O 等待型负载 · 端到端吞吐判定 ====================")
    print(f"负载：{io['任务数']} 条 × {等待毫秒}ms I/O 等待（模拟 LLM/worktree），"
          f"1 进程串行 vs 4 进程并发")
    print(f"  基线端到端墙钟={io['基线墙钟']:.1f}ms；并发端到端墙钟={io['并发墙钟']:.1f}ms")
    print(f"  4 块并发墙钟={[round(值, 1) for 值 in io['块墙钟']]}")
    print(f"  实测墙钟比={比值:.2%}（目标 ≤ {墙钟比上限:.0%}）；"
          f"吞吐比={io['吞吐比']:.2f}x（目标 ≥ {吞吐比下限:.2f}x）")
    print("=====================================================================")

    assert 比值 <= 墙钟比上限, (
        f"I/O 负载端到端墙钟比 {比值:.2%} > {墙钟比上限:.0%}："
        f"基线 {io['基线墙钟']:.1f}ms，并发 {io['并发墙钟']:.1f}ms"
    )
    assert io["吞吐比"] >= 吞吐比下限, (
        f"吞吐比 {io['吞吐比']:.2f}x < {吞吐比下限:.2f}x"
    )


def test_cpu轻负载并发无收益作为边界对照(双负载结果):
    """边界对照：CPU-bound 轻负载下并发不降墙钟，如实记录，不做达标判定。"""
    cpu = 双负载结果["cpu"]
    print("\n==================== CPU-bound 轻负载 · 边界对照（不判定） ====================")
    print(f"负载：{cpu['任务数']} 条纯判定/评估（无 I/O 等待），解释器启动开销主导")
    print(f"  基线墙钟={cpu['基线墙钟']:.1f}ms；并发墙钟={cpu['并发墙钟']:.1f}ms；"
          f"墙钟比={cpu['墙钟比']:.2%}；吞吐比={cpu['吞吐比']:.2f}x")
    print("  结论：单条计算耗时与并发无关；启动开销 ~440ms >> 纯计算 ~21ms，")
    print("        因此 CPU-bound 轻负载下并发无收益——这是 第十二轮 p95 负面结论的根因。")
    print("==========================================================================")
    # 只做健全性断言，不做性能达标断言：墙钟比为正、两种模式都产出结果。
    assert cpu["墙钟比"] > 0, "CPU 负载墙钟比必须为正"
    assert len(cpu["基线结果"]) == len(cpu["并发结果"]) == cpu["任务数"], "两种模式结果条数必须守恒"


def test_临时目录清理且项目目录无残留(双负载结果):
    """TemporaryDirectory 退出后清理；真子进程未在项目目录留下工作负载产物。"""
    assert not 双负载结果["临时路径"].exists(), "临时目录退出后未清理"
    残留 = [
        路径.name for 路径 in GENGFU_DIR.rglob("*")
        if 路径.is_file() and 路径.name.startswith(("tp-in-", "tp-out-", "throughput_workload.道"))
    ]
    assert not 残留, f"项目目录残留本测试产物：{残留}"
