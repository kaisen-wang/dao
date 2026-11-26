"""更夫 Nightwatch — 第十二轮 A：Outbox 投递器真 HTTP 回环测试。

弥补第十一轮诚实缺口：此前「外部消息 0 丢失 0 重复」只是本地 SQLite 行数口径，
没有真正把消息 POST 到 HTTP sink 的投递执行器。本测试用 DaoHttpServer 在本机回环
起 sink，路由 POST /outbox 按幂等键去重计数；用 sys.executable 启动真实 .道 子进程
（cwd=示例/更夫）调用 基础设施层/投递执行器.道 的 创建投递器(...).刷新()，按 sink
收到的唯一幂等键口径断言「丢失 0、重复 0」。

场景：
  1. sink 在线 → 入队 3 条（含 1 条重复幂等键）→ 刷新后 sink 唯一键 2、pending 清零；
  2. sink 未启动时刷新失败保留 pending → 启动 sink 再刷新 → 收到并清零；
  3. 断网刷新返回中文字典与失败明细；
  4. 同一进程双轮刷新的累计统计口径；
  5. 真 HTTP 非 2xx（503）保留 pending，恢复 200 后补发不重复。

诚实边界（务必与 PRD 区分）：
- 本机 HTTP 回环 sink ≠ 真实 GitHub / 飞书 / 企微 webhook；
- 这里断言的「外部消息 0 丢失 0 重复」是本机回环口径，不代表真实外部消息计数；
- **不勾选 PRD §12 任何 DoD 项**，只证明「本地可验证部分已实现」。

测试约定：一律 sys.executable；禁 signal.SIGKILL；停止用 proc.terminate() 并 fallback
proc.kill()；tempfile.TemporaryDirectory() 清理；子进程 cwd=示例/更夫；
环境变量名与值均用 ASCII；端口 0 自动分配 + 关闭()/join() 回收，避免端口泄漏。
"""

import json
import os
import socket
import subprocess
import sys
import tempfile
import threading
import time
from pathlib import Path

import pytest

# 源码/tests/test_outbox_http_delivery.py -> 仓库根目录
PROJECT_ROOT = Path(__file__).resolve().parents[2]
MAIN = PROJECT_ROOT / "源码" / "main.py"
GENGFU_DIR = PROJECT_ROOT / "示例" / "更夫"

# 让 Python 侧能 import DaoHttpServer（与既有 stdlib 测试一致）。
sys.path.insert(0, str(MAIN.parent))
from dao.stdlib.network import DaoHttpServer

# 工作负载通过 ASCII 名环境变量接收库路径/端口/轮次/输出路径，避免跨平台编码差异。
ENV_DB = "GENGFU_OUTBOX_DB"
ENV_URL = "GENGFU_OUTBOX_URL"
ENV_ROUND = "GENGFU_OUTBOX_ROUND"
ENV_OUTPUT = "GENGFU_OUTBOX_OUTPUT"
ENV_REFRESH = "GENGFU_OUTBOX_REFRESH"
ENV_DOUBLE = "GENGFU_OUTBOX_DOUBLE"

# ======================== .道 工作负载（在 tempfile 中生成） ========================

# 入队 3 条（第 3 条复用第 1 条的幂等键）后可选刷新 1~2 轮。
# 刷新使用无参 .刷新()，真正走 网络.请求，不经任何注入。
ENQUEUE_SCRIPT = """\
// 第十二轮 A — 真 HTTP 回环入队工作负载（由 Python 测试在 tempfile 中生成）。
// 本机回环 sink ≠ 真实平台 webhook，不勾选 PRD §12 DoD。
从 系统 导入 取环境变量
从 文件 导入 写入
从 编码 导入 JSON
从 基础设施层.存储 导入 打开存储, 投递入队, 待投递列表
从 基础设施层.投递执行器 导入 创建投递器

定义 数据库路径 = 取环境变量("GENGFU_OUTBOX_DB", "")
定义 接收URL = 取环境变量("GENGFU_OUTBOX_URL", "")
定义 轮次 = 取环境变量("GENGFU_OUTBOX_ROUND", "0")
定义 输出路径 = 取环境变量("GENGFU_OUTBOX_OUTPUT", "")
定义 是否刷新 = 取环境变量("GENGFU_OUTBOX_REFRESH", "1")
定义 是否双轮 = 取环境变量("GENGFU_OUTBOX_DOUBLE", "0")

打开存储(数据库路径)

定义 键甲 = `回环-{轮次}-甲`
定义 键乙 = `回环-{轮次}-乙`
// 第三条复用键甲：投递入队 幂等应返回原 ID，pending 仍只有两条。
定义 ID甲 = 投递入队(`T-{轮次}-甲`, "通知", `载荷甲-{轮次}`, 键甲)
定义 ID乙 = 投递入队(`T-{轮次}-乙`, "通知", `载荷乙-{轮次}`, 键乙)
定义 ID甲重复 = 投递入队(`T-{轮次}-甲重复`, "通知", `载荷甲重复-{轮次}`, 键甲)

定义 投递器 = 创建投递器(接收URL, 1)
定义 首轮 = {}
定义 次轮 = {}
如果 是否刷新 == "1"
    首轮 = 投递器.刷新()
    如果 是否双轮 == "1"
        次轮 = 投递器.刷新()

写入(输出路径, JSON.编码({
    "入队ID": [ID甲, ID乙, ID甲重复],
    "待投递数": 长度(待投递列表()),
    "首轮": 首轮,
    "次轮": 次轮,
    "统计": 投递器.投递统计()
}))
"""

# 只刷新一轮（用于 sink 启动后的补发），不重复入队。
REFRESH_SCRIPT = """\
// 第十二轮 A — 真 HTTP 回环补发工作负载（由 Python 测试在 tempfile 中生成）。
// 本机回环 sink ≠ 真实平台 webhook，不勾选 PRD §12 DoD。
从 系统 导入 取环境变量
从 文件 导入 写入
从 编码 导入 JSON
从 基础设施层.存储 导入 打开存储, 待投递列表
从 基础设施层.投递执行器 导入 创建投递器

定义 数据库路径 = 取环境变量("GENGFU_OUTBOX_DB", "")
定义 接收URL = 取环境变量("GENGFU_OUTBOX_URL", "")
定义 输出路径 = 取环境变量("GENGFU_OUTBOX_OUTPUT", "")

打开存储(数据库路径)
定义 投递器 = 创建投递器(接收URL, 1)
定义 结果 = 投递器.刷新()
写入(输出路径, JSON.编码({
    "首轮": 结果,
    "待投递数": 长度(待投递列表()),
    "统计": 投递器.投递统计()
}))
"""


# ======================== sink 启动/关闭与真子进程启动/回收 ========================

def _启动sink(状态码=200):
    """在本机回环起 POST /outbox sink，按幂等键去重计数并返回指定状态码。

    返回 (server, thread, 记录)。记录['键列表'] 只保留唯一幂等键，
    用于按外部 sink 口径断言 0 丢失 0 重复（不是本地 SQLite 行数口径）。
    """
    server = DaoHttpServer()
    记录 = {"键列表": [], "载荷列表": [], "状态码": 状态码, "锁": threading.Lock()}

    def 处理(req):
        数据 = req.JSON()
        键 = 数据["幂等键"]
        with 记录["锁"]:
            # 外部 sink 按幂等键去重：同一键重复 POST 只计一次。
            if 键 not in 记录["键列表"]:
                记录["键列表"].append(键)
                记录["载荷列表"].append(数据)
        return {"状态码": 记录["状态码"], "内容": {"已接收": 键}}

    server.路由("POST", "/outbox", 处理)
    thread = threading.Thread(target=server.启动, kwargs={"端口": 0}, daemon=True)
    thread.start()
    截止 = time.monotonic() + 5
    while server.端口 is None and time.monotonic() < 截止:
        time.sleep(0.01)
    assert server.端口 is not None, "本机回环 sink 未能在预期时间内启动"
    return server, thread, 记录


def _关闭sink(server, thread):
    """关闭 sink 并等待线程退出，避免端口泄漏。"""
    server.关闭()
    thread.join(timeout=5)
    assert not thread.is_alive(), "sink 线程未能退出（端口可能泄漏）"


def _空闲端口():
    """取一个当前空闲的本地端口，用于模拟『sink 未启动』的连接拒绝场景。"""
    with socket.socket() as 临时套接字:
        临时套接字.bind(("127.0.0.1", 0))
        return 临时套接字.getsockname()[1]


def _启动工作负载(脚本路径, 临时路径, 标签, 数据库路径, 接收URL, 轮次,
                 是否刷新="1", 是否双轮="0"):
    """用 sys.executable 启动真实 .道 子进程，返回解析后的输出字典。"""
    输出路径 = 临时路径 / f"输出-{标签}.json"
    环境变量 = os.environ.copy()
    环境变量["PYTHONPATH"] = str(MAIN.parent)
    环境变量[ENV_DB] = str(数据库路径)
    环境变量[ENV_URL] = 接收URL
    环境变量[ENV_ROUND] = str(轮次)
    环境变量[ENV_OUTPUT] = str(输出路径)
    环境变量[ENV_REFRESH] = 是否刷新
    环境变量[ENV_DOUBLE] = 是否双轮
    环境变量["GENGFU_NO_LLM"] = "1"  # 不依赖真实网络 / ollama
    proc = subprocess.Popen(
        [sys.executable, str(MAIN), str(脚本路径)],
        cwd=str(GENGFU_DIR),
        env=环境变量,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    try:
        标准输出, 标准错误 = proc.communicate(timeout=10)
    except subprocess.TimeoutExpired:
        proc.terminate()
        try:
            标准输出, 标准错误 = proc.communicate(timeout=3)
        except subprocess.TimeoutExpired:
            proc.kill()
            标准输出, 标准错误 = proc.communicate(timeout=3)
        pytest.fail(f"工作负载[{标签}]超时已终止；stderr={标准错误!r}")
    assert proc.returncode == 0, (
        f"工作负载[{标签}]退出码 {proc.returncode}；"
        f"stdout={标准输出!r} stderr={标准错误!r}"
    )
    assert 输出路径.exists(), f"工作负载[{标签}]未写出 JSON 结果文件"
    return json.loads(输出路径.read_text(encoding="utf-8"))


def _写脚本(临时路径, 名称, 内容):
    脚本路径 = 临时路径 / 名称
    脚本路径.write_text(内容, encoding="utf-8")
    return 脚本路径


def _断言零丢失零重复(记录, 期望键集合):
    """按 sink 唯一幂等键口径断言外部消息 0 丢失 0 重复（中文断言）。"""
    唯一键集合 = set(记录["键列表"])
    丢失数 = len(期望键集合 - 唯一键集合)
    重复数 = len(记录["键列表"]) - len(唯一键集合)
    assert 丢失数 == 0, (
        f"本机回环 sink 丢失数应为 0，实际 {丢失数}；"
        f"期望键={期望键集合}，实际键={唯一键集合}"
    )
    assert 重复数 == 0, (
        f"本机回环 sink 重复数应为 0，实际 {重复数}；完整记录={记录['键列表']}"
    )


# ======================== 用例 ========================

def test_场景1_sink在线三入队含重复键零丢失零重复():
    """本机回环 sink 在线：3 条入队（1 条重复键）→ 唯一键 2、pending 清零、0/0。"""
    with tempfile.TemporaryDirectory(prefix="gengfu-outbox-") as 临时目录:
        临时路径 = Path(临时目录)
        脚本 = _写脚本(临时路径, "入队并刷新.道", ENQUEUE_SCRIPT)
        数据库 = 临时路径 / "场景1.db"
        server, thread, 记录 = _启动sink()
        try:
            结果 = _启动工作负载(
                脚本, 临时路径, "场景1", 数据库,
                f"http://127.0.0.1:{server.端口}/outbox", 1,
            )
        finally:
            _关闭sink(server, thread)

    assert 结果["入队ID"][0] == 结果["入队ID"][2], (
        "同一幂等键重复入队应命中幂等，返回同一投递 ID"
    )
    assert 结果["首轮"]["成功"] == 2, f"sink 在线应成功投递 2 条，实际 {结果['首轮']['成功']}"
    assert 结果["首轮"]["失败"] == 0, f"sink 在线不应有失败，实际 {结果['首轮']['失败']}"
    assert 结果["首轮"]["剩余待投递"] == 0, "刷新后 pending 应清零"
    assert 结果["待投递数"] == 0, "SQLite 待投递行数应为 0"
    键甲, 键乙 = "回环-1-甲", "回环-1-乙"
    assert set(记录["键列表"]) == {键甲, 键乙}, (
        f"sink 唯一幂等键应为 {{{键甲}, {键乙}}}，实际 {set(记录['键列表'])}"
    )
    _断言零丢失零重复(记录, {键甲, 键乙})
    print("场景1：本机回环 sink 唯一键 2，丢失 0、重复 0（≠ 真实平台 webhook，不勾选 DoD）")


def test_场景2_离线失败保留pending启动sink后补发零丢失零重复():
    """sink 未启动 → 投递失败保留 pending → 启动 sink 再刷新 → 收到并清零、0/0。"""
    with tempfile.TemporaryDirectory(prefix="gengfu-outbox-") as 临时目录:
        临时路径 = Path(临时目录)
        入队脚本 = _写脚本(临时路径, "入队.道", ENQUEUE_SCRIPT)
        补发脚本 = _写脚本(临时路径, "补发.道", REFRESH_SCRIPT)
        数据库 = 临时路径 / "场景2.db"
        离线URL = f"http://127.0.0.1:{_空闲端口()}/outbox"

        # 阶段一：sink 未启动，连接被拒绝 → 失败且保留 pending。
        首次 = _启动工作负载(
            入队脚本, 临时路径, "场景2离线", 数据库, 离线URL, 2,
        )
        assert 首次["首轮"]["成功"] == 0, "sink 未启动时不应有成功投递"
        assert 首次["首轮"]["失败"] == 2, f"sink 未启动应有 2 条失败，实际 {首次['首轮']['失败']}"
        assert 首次["首轮"]["剩余待投递"] == 2, "失败消息应保留 pending 等待补发"
        assert 首次["待投递数"] == 2, "SQLite 待投递行数应保持 2"
        assert 首次["统计"]["累计失败"] == 2, "累计失败应记录 2 次"
        assert 首次["统计"]["累计成功"] == 0, "累计成功应为 0"

        # 阶段二：启动 sink 后用第二个真子进程打开同一个库补发。
        server, thread, 记录 = _启动sink()
        try:
            补发 = _启动工作负载(
                补发脚本, 临时路径, "场景2补发", 数据库,
                f"http://127.0.0.1:{server.端口}/outbox", 2,
            )
        finally:
            _关闭sink(server, thread)

    assert 补发["首轮"]["成功"] == 2, f"补发应成功 2 条，实际 {补发['首轮']['成功']}"
    assert 补发["首轮"]["失败"] == 0, "补发不应再有失败"
    assert 补发["首轮"]["剩余待投递"] == 0, "补发后 pending 应清零"
    assert 补发["待投递数"] == 0, "补发后 SQLite 待投递行数应为 0"
    键甲, 键乙 = "回环-2-甲", "回环-2-乙"
    assert set(记录["键列表"]) == {键甲, 键乙}, (
        f"sink 应只收到两个唯一幂等键，实际 {set(记录['键列表'])}"
    )
    _断言零丢失零重复(记录, {键甲, 键乙})
    print("场景2：离线失败保留 pending → 在线补发，本机回环 sink 丢失 0、重复 0（不勾选 DoD）")


def test_断网刷新返回中文字典与失败明细字段():
    """断网时 刷新() 返回中文字典：明细含幂等键/状态码 0/中文结果，说明含边界。"""
    with tempfile.TemporaryDirectory(prefix="gengfu-outbox-") as 临时目录:
        临时路径 = Path(临时目录)
        脚本 = _写脚本(临时路径, "断网.道", ENQUEUE_SCRIPT)
        数据库 = 临时路径 / "断网.db"
        结果 = _启动工作负载(
            脚本, 临时路径, "断网", 数据库,
            f"http://127.0.0.1:{_空闲端口()}/outbox", 3,
        )

    首轮 = 结果["首轮"]
    for 键 in ("成功", "失败", "剩余待投递", "明细", "说明"):
        assert 键 in 首轮, f"断网刷新结果应含中文字段「{键}」"
    assert len(首轮["明细"]) == 2, f"断网应有 2 条失败明细，实际 {len(首轮['明细'])}"
    for 明细 in 首轮["明细"]:
        for 键 in ("幂等键", "状态码", "结果"):
            assert 键 in 明细, f"失败明细应含字段「{键}」"
        assert 明细["状态码"] == 0, f"断网明细状态码应为 0，实际 {明细['状态码']}"
        assert "失败" in 明细["结果"], f"失败明细结果应为中文且含「失败」：{明细['结果']}"
        assert "保留待投递" in 明细["结果"], "失败明细应说明 pending 被保留"
    assert "回环" in 首轮["说明"], "说明应写清本机回环口径"
    assert "DoD" in 首轮["说明"], "说明应写清不勾选 DoD"


def test_双轮刷新累计成功失败与最近明细口径():
    """同一 投递器 连续两轮刷新：累计成功 2、累计失败 0、最近明细数 0。"""
    with tempfile.TemporaryDirectory(prefix="gengfu-outbox-") as 临时目录:
        临时路径 = Path(临时目录)
        脚本 = _写脚本(临时路径, "双轮.道", ENQUEUE_SCRIPT)
        数据库 = 临时路径 / "双轮.db"
        server, thread, 记录 = _启动sink()
        try:
            结果 = _启动工作负载(
                脚本, 临时路径, "双轮", 数据库,
                f"http://127.0.0.1:{server.端口}/outbox", 4,
                是否双轮="1",
            )
        finally:
            _关闭sink(server, thread)

    统计 = 结果["统计"]
    assert 结果["首轮"]["成功"] == 2, "第一轮应成功投递 2 条"
    assert 结果["次轮"]["成功"] == 0, "第二轮 pending 已清零，应无成功投递"
    assert 统计["累计成功"] == 2, f"累计成功应为 2，实际 {统计['累计成功']}"
    assert 统计["累计失败"] == 0, f"累计失败应为 0，实际 {统计['累计失败']}"
    assert 统计["最近明细数"] == 0, "最近一轮明细为空，最近明细数应为 0"
    _断言零丢失零重复(记录, {"回环-4-甲", "回环-4-乙"})


def test_真HTTP非2xx保留pending恢复200后补发不重复():
    """真 HTTP 503 → 失败保留 pending；切换 200 后补发，唯一幂等键仍 0 丢失 0 重复。"""
    with tempfile.TemporaryDirectory(prefix="gengfu-outbox-") as 临时目录:
        临时路径 = Path(临时目录)
        入队脚本 = _写脚本(临时路径, "非2xx入队.道", ENQUEUE_SCRIPT)
        补发脚本 = _写脚本(临时路径, "非2xx补发.道", REFRESH_SCRIPT)
        数据库 = 临时路径 / "非2xx.db"
        server, thread, 记录 = _启动sink(状态码=503)
        try:
            首次 = _启动工作负载(
                入队脚本, 临时路径, "非2xx", 数据库,
                f"http://127.0.0.1:{server.端口}/outbox", 5,
            )
            assert 首次["首轮"]["失败"] == 2, "sink 返回 503 应有 2 条失败"
            assert 首次["首轮"]["剩余待投递"] == 2, "非 2xx 应保留 pending"
            for 明细 in 首次["首轮"]["明细"]:
                assert 明细["状态码"] == 503, f"明细应记录真 HTTP 状态码 503，实际 {明细['状态码']}"
                assert "失败" in 明细["结果"], "非 2xx 明细结果应为中文失败说明"

            记录["状态码"] = 200
            补发 = _启动工作负载(
                补发脚本, 临时路径, "非2xx补发", 数据库,
                f"http://127.0.0.1:{server.端口}/outbox", 5,
            )
        finally:
            _关闭sink(server, thread)

    assert 补发["首轮"]["成功"] == 2, "恢复 200 后补发应成功 2 条"
    assert 补发["首轮"]["剩余待投递"] == 0, "补发后 pending 应清零"
    assert set(记录["键列表"]) == {"回环-5-甲", "回环-5-乙"}, (
        f"sink 唯一幂等键应为 2 个，实际 {set(记录['键列表'])}"
    )
    _断言零丢失零重复(记录, {"回环-5-甲", "回环-5-乙"})
    print("非2xx：真 HTTP 503 保留 pending → 200 补发，本机回环 sink 丢失 0、重复 0（不勾选 DoD）")
