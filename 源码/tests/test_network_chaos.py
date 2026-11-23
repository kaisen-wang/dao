"""更夫 Nightwatch — 真实断网 ×10 混沌测试（第十轮，子代理 A / network-chaos）。

覆盖共享契约《迭代规约-韧性审计与守护验收.md》§2 A：

* 用 ``sys.executable`` 启动**真实 Python 子进程**运行道语言工作负载，
  子进程 cwd 为 ``示例/更夫``（道语言模块搜索基于 os.getcwd()），
  工作负载为 ``tempfile.TemporaryDirectory()`` 内的绝对路径脚本；
* 断网模拟：用 socket 绑定端口 0 取空闲端口后立即释放，把 ``OLLAMA_HOST``
  指向 ``http://127.0.0.1:<该端口>``；**不设** ``GENGFU_NO_LLM``，
  让 ``基础设施层/语言模型.道`` 真的向不可达地址发起请求并降级；
* 至少 10 轮：每轮真实调用一次 ``创建语言模型().对话()`` 与 ``.判断()``，
  断言返回中文字典且 ``成功 == 假``、不抛未捕获异常；
* 恢复验证：断网期间用 ``基础设施层/存储.道`` 落 N=3 条 Outbox（幂等键唯一），
  断网"结束"后按原幂等键重投 → 不重复，pending 键补投 → 不丢失；
* 每轮用 ``tempfile.TemporaryDirectory()`` 隔离数据库与脚本，退出清理，
  项目目录不产生 ``.db`` / 仓库。

诚实边界（务必按此口径理解结果）：

1. 这里的"断网"是**本地不可达 host** 的真实网络异常（连接被拒绝 / socket 超时），
   不等于生产环境断网全场景（外网 DNS、链路中断、云端服务不可用等均未覆盖）。
2. **"外部消息丢失/重复计数"是本地模拟口径**：仅统计本轮临时 SQLite 的
   ``outbox`` 表行数与幂等键命中情况，**不是**真实外部系统（IM / GitHub /
   邮件）的消息计数；本轮没有发送任何真实外部消息。
3. 为同时满足契约"单轮 ≤2 秒"，工作负载调用
   ``创建语言模型("ollama", {"timeout": 0.3})`` 缩短 socket 超时；
   host 仍从 ``OLLAMA_HOST`` 环境变量读取（即上面分配的本地空闲端口），
   请求真实发出、真实失败、真实降级，只是不用产品默认的 120 秒超时
   （Windows 上对未监听端口的默认失败路径固定约 2 秒，两次调用必然超时预算）。

跨平台约定（契约 §0 硬约束）：

* 一律用 ``sys.executable`` 启动子进程，禁止硬编码 ``.venv/bin/python``；
* 禁止 ``signal.SIGKILL`` / ``os.kill(pid, SIGKILL)``（Windows 无 SIGKILL）；
  本测试无需杀进程，如需停止子进程只用 ``proc.terminate()`` 并 fallback
  ``proc.kill()``；
* 临时文件一律放系统临时目录（``tempfile``），退出自动清理。
"""

import json
import os
import socket
import sqlite3
import subprocess
import sys
import tempfile
import time
from pathlib import Path

import pytest

# 源码/tests/test_network_chaos.py -> 仓库根目录（与第八轮 test_chaos_real_process.py 一致）
PROJECT_ROOT = Path(__file__).resolve().parents[2]
MAIN = PROJECT_ROOT / "源码" / "main.py"
GENGFU_DIR = PROJECT_ROOT / "示例" / "更夫"

# 工作负载通过环境变量接收本轮临时数据库与轮次（ASCII 名避免跨平台编码差异）。
ENV_DB = "GENGFU_NET_DB"
ENV_ROUND = "GENGFU_NET_ROUND"

# 道语言工作负载：每轮一个子进程内完成「真实断网降级 + Outbox 断网积压 + 恢复重投」。
# 用 ``打印`` 输出带前缀的 JSON 行，供 Python 侧严格断言；不修改任何产品代码。
WORKLOAD_SCRIPT = """\
// 真实断网 ×10 混沌测试 — 道语言工作负载（由 Python 测试在 tempfile 中生成）。
// 阶段一：断网降级 —— 真连 OLLAMA_HOST 指向的本地不可达端口，失败后中文字典降级。
从 系统 导入 取环境变量
从 基础设施层.语言模型 导入 创建语言模型
从 基础设施层.存储 导入 打开存储, 投递入队, 标记投递
从 编码 导入 JSON

定义 数据库路径 = 取环境变量("GENGFU_NET_DB", "")
定义 轮次 = 取环境变量("GENGFU_NET_ROUND", "0")

// host 从 OLLAMA_HOST 读取（测试侧指向本地未监听端口）；只缩短 socket 超时以满足单轮预算。
// GENGFU_NO_LLM 不设：本工作负载直调 L1 语言模型，不走入口层的强制降级开关。
定义 模型 = 创建语言模型("ollama", {"timeout": 0.3})
定义 对话结果 = 模型.对话(`断网探针-{轮次}`)
定义 判断结果 = 模型.判断(`断网判断探针-{轮次}`)
打印("DIALOG:" + JSON.编码(对话结果))
打印("JUDGE:" + JSON.编码(判断结果))

// 阶段二：断网期间落 N=3 条 Outbox（幂等键唯一）。
// 键A 在断网前已投递(sent)；键B/键C 处于 pending，模拟断网期间积压未发出。
定义 存储 = 打开存储(数据库路径)
定义 键A = `网络混沌-已投递-{轮次}`
定义 键B = `网络混沌-积压1-{轮次}`
定义 键C = `网络混沌-积压2-{轮次}`
定义 idA = 投递入队(`T-{轮次}`, "通知", `载荷A-{轮次}`, 键A)
标记投递(idA)
定义 idB = 投递入队(`T-{轮次}`, "通知", `载荷B-{轮次}`, 键B)
定义 idC = 投递入队(`T-{轮次}`, "通知", `载荷C-{轮次}`, 键C)

// 阶段三：断网"结束"后的本地重投模拟。
// 按原幂等键重投：命中幂等应返回原 ID、不新增行 → 本地模拟口径重复数 0。
// pending 键补投：应成功标记 sent、内容不被改写 → 本地模拟口径丢失数 0。
// 注意：这只是本地 Outbox 表口径，不是任何真实外部系统的消息计数。
定义 idA2 = 投递入队(`T-{轮次}`, "通知", `重投A-{轮次}`, 键A)
定义 idB2 = 投递入队(`T-{轮次}`, "通知", `重投B-{轮次}`, 键B)
定义 idC2 = 投递入队(`T-{轮次}`, "通知", `重投C-{轮次}`, 键C)
标记投递(idB2)
标记投递(idC2)
打印("OUTBOX:" + JSON.编码({"已投递ID":idA, "重投A_ID":idA2, "积压1原ID":idB, "积压1补投ID":idB2, "积压2原ID":idC, "积压2补投ID":idC2}))
"""

# 子进程 stdout 中结果行的前缀。
前缀对话 = "DIALOG:"
前缀判断 = "JUDGE:"
前缀外发 = "OUTBOX:"


def _取空闲端口() -> int:
    """绑定 127.0.0.1:0 取一个空闲端口后立即释放，不依赖外网 DNS / 真实网络。"""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as 套:
        套.bind(("127.0.0.1", 0))
        return int(套.getsockname()[1])


def _取结果行(标准输出: str, 前缀: str) -> dict:
    """从子进程 stdout 中取指定前缀的 JSON 行并解码为字典。"""
    命中 = [
        行[len(前缀):]
        for 行 in 标准输出.splitlines()
        if 行.startswith(前缀)
    ]
    assert len(命中) == 1, f"期望恰好一行 {前缀} 结果，实际 {len(命中)} 行；stdout={标准输出!r}"
    结果 = json.loads(命中[0])
    assert isinstance(结果, dict), f"{前缀} 结果不是字典：{结果!r}"
    return 结果


def _读外发箱(数据库: Path, 幂等键列表: list[str]) -> list[tuple]:
    """用 Python 直接读 SQLite 校验 outbox 最终状态（不依赖道语言查询结果）。

    显式 ``close()``：Windows 上 ``with sqlite3.connect()`` 只提交不关闭连接，
    残留文件句柄会让外层 ``TemporaryDirectory`` 清理时报 WinError 32。
    """
    连接 = sqlite3.connect(str(数据库), timeout=1)
    try:
        return 连接.execute(
            "SELECT id, 幂等键, 状态, 内容 FROM outbox "
            "WHERE 幂等键 IN (?, ?, ?) ORDER BY 幂等键",
            幂等键列表,
        ).fetchall()
    finally:
        连接.close()


@pytest.mark.parametrize("轮次", range(1, 11))
def test_真实断网十轮降级与外发箱恢复(轮次: int):
    """断网 ×10：对话/判断真实降级；断网期间积压的 Outbox 重投不重复、补投不丢失。"""
    开始时间 = time.monotonic()

    # 环境不可达 → 如实 skip，不伪造通过。
    if not MAIN.is_file():
        pytest.skip(f"道语言入口不存在：{MAIN}，无法启动真实子进程")
    if not GENGFU_DIR.is_dir():
        pytest.skip(f"示例/更夫 目录不存在：{GENGFU_DIR}，道语言模块搜索无法进行")

    with tempfile.TemporaryDirectory(prefix=f"更夫断网-{轮次}-") as 临时目录:
        临时路径 = Path(临时目录)
        工作负载 = 临时路径 / "工作负载.道"
        数据库 = 临时路径 / "断网.db"  # 每轮独立，项目目录不产生 .db
        工作负载.write_text(WORKLOAD_SCRIPT, encoding="utf-8")

        空闲端口 = _取空闲端口()
        环境变量 = os.environ.copy()
        环境变量["PYTHONPATH"] = str(MAIN.parent)
        环境变量["OLLAMA_HOST"] = f"http://127.0.0.1:{空闲端口}"
        环境变量[ENV_DB] = str(数据库)
        环境变量[ENV_ROUND] = str(轮次)
        # 明确"不设" GENGFU_NO_LLM：该开关只在接入层/入口.道读取，
        # 这里直调 L1 语言模型，pop 掉可避免任何上层强制降级掩盖真实断网。
        环境变量.pop("GENGFU_NO_LLM", None)

        try:
            子进程 = subprocess.Popen(
                [sys.executable, str(MAIN), str(工作负载)],
                cwd=str(GENGFU_DIR),
                env=环境变量,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )
        except OSError as 错误:  # 解释器无法启动属环境不可达
            pytest.skip(f"无法用 sys.executable 启动子进程：{错误}")

        try:
            标准输出, 标准错误 = 子进程.communicate(timeout=8)
        except subprocess.TimeoutExpired:
            # 进程失控：跨平台停止，禁用 SIGKILL。
            if 子进程.poll() is None:
                子进程.terminate()
                try:
                    子进程.communicate(timeout=2)
                except subprocess.TimeoutExpired:
                    子进程.kill()
                    标准输出, 标准错误 = 子进程.communicate(timeout=2)
            pytest.fail(f"第 {轮次} 轮：子进程超过 8 秒未退出，stderr={标准错误!r}")
        耗时 = time.monotonic() - 开始时间

        assert 子进程.returncode == 0, (
            f"第 {轮次} 轮：子进程退出码 {子进程.returncode}；"
            f"stdout={标准输出!r} stderr={标准错误!r}"
        )

        # --- 阶段一断言：断网降级必须是中文字典且 成功 == 假、未抛异常 ---
        对话结果 = _取结果行(标准输出, 前缀对话)
        判断结果 = _取结果行(标准输出, 前缀判断)
        assert 对话结果.get("成功") is False, f"第 {轮次} 轮：对话未降级：{对话结果!r}"
        assert 判断结果.get("成功") is False, f"第 {轮次} 轮：判断未降级：{判断结果!r}"
        # 错误文本含「Ollama 请求失败」证明真的发起了网络请求（而非客户端创建失败等伪降级）。
        assert "Ollama 请求失败" in 对话结果.get("错误", ""), (
            f"第 {轮次} 轮：对话错误不是真实网络请求失败：{对话结果!r}"
        )
        assert "Ollama 请求失败" in 判断结果.get("错误", ""), (
            f"第 {轮次} 轮：判断错误不是真实网络请求失败：{判断结果!r}"
        )

        # --- 阶段二/三断言：Outbox 幂等重投不重复、pending 补投不丢失 ---
        外发结果 = _取结果行(标准输出, 前缀外发)
        已投递键 = f"网络混沌-已投递-{轮次}"
        积压键1 = f"网络混沌-积压1-{轮次}"
        积压键2 = f"网络混沌-积压2-{轮次}"
        幂等键列表 = [已投递键, 积压键1, 积压键2]

        # 同键重投命中幂等 → 返回原 ID，不新增投递行。
        assert 外发结果["重投A_ID"] == 外发结果["已投递ID"], (
            f"第 {轮次} 轮：同键重投未命中幂等（出现重复投递）"
        )
        assert 外发结果["积压1补投ID"] == 外发结果["积压1原ID"], (
            f"第 {轮次} 轮：积压键1 重投未命中幂等"
        )
        assert 外发结果["积压2补投ID"] == 外发结果["积压2原ID"], (
            f"第 {轮次} 轮：积压键2 重投未命中幂等"
        )

        最终行 = _读外发箱(数据库, 幂等键列表)
        按键 = {行[1]: 行 for 行 in 最终行}
        assert set(按键) == set(幂等键列表), (
            f"第 {轮次} 轮：恢复后有幂等键丢失：{sorted(按键)}"
        )
        # 本地模拟口径：重复数 = 行数 - 唯一键数；丢失数 = 应有键数 - 实有键数。
        # 这**不是**真实外部消息计数，仅为 tempfile 内 SQLite 的行数统计。
        重复数 = len(最终行) - len(按键)
        丢失数 = len(幂等键列表) - len(按键)
        assert 重复数 == 0 and 丢失数 == 0, (
            f"第 {轮次} 轮：本地模拟口径重复数={重复数} 丢失数={丢失数}"
        )
        assert all(行[2] == "sent" for 行 in 最终行), (
            f"第 {轮次} 轮：存在未补投成功的积压消息：{最终行}"
        )
        # 积压键内容未被重投内容改写 → 幂等生效、载荷不丢失。
        assert 按键[积压键1][3] == f"载荷B-{轮次}", "积压键1 载荷被改写/丢失"
        assert 按键[积压键2][3] == f"载荷C-{轮次}", "积压键2 载荷被改写/丢失"

        连接 = sqlite3.connect(str(数据库), timeout=1)
        try:
            总行数 = 连接.execute("SELECT COUNT(*) FROM outbox").fetchone()[0]
        finally:
            连接.close()
        assert 总行数 == 3, f"第 {轮次} 轮：outbox 总行数应为 3，实际 {总行数}"

        # 单轮时间预算 ≤2 秒（契约 §2 A）；实际耗时随机器负载有小幅波动。
        assert 耗时 <= 2.0, f"第 {轮次} 轮：单轮耗时 {耗时:.2f}s 超过 2 秒预算"

        print(
            f"第 {轮次:2d} 轮：对话成功={对话结果['成功']} 判断成功={判断结果['成功']} "
            f"Outbox幂等键={len(按键)} 恢复率={len(按键) / len(幂等键列表):.0%} "
            f"重复数=0 丢失数=0（本地模拟口径，非真实外部消息计数） 耗时={耗时:.2f}s"
        )
