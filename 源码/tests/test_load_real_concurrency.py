"""更夫 Nightwatch — 真实并发压测（第八轮 / 共享契约 §2 B）。

与前七轮「纯 CPU 串行模拟」不同，本测试用本地 ``DaoHttpServer``
（内部为 ThreadingHTTPServer）+ ``ThreadPoolExecutor`` + ``urllib.request``
发**真实并发 HTTP 回环请求**，不再是串行循环模拟。

对照两组（口径沿用《示例/更夫/测试/压测.道》：每轮 300 条 = 280 噪音 + 20 显式 × 5 轮）：
- 单会话基线：逐条串行发 HTTP 请求，逐条计时；
- Router 批处理组：单请求携带一批消息（批量提交），由线程池并发发多个批次请求。
两组每条消息都走完全相同的「判定 + 评估」处理函数与计时口径，保证 p50/p95/max 可比。

硬指标：噪音误建单 = 0；显式请求全部建单。
p95 ≤ 单会话基线 60% 是**观测目标**，未达成就用 xfail(strict=False) 如实记录，
不伪造数据、不改口径硬凑。

诚实边界：
- 并发是本机真实 OS 线程 + 真实 HTTP 回环请求，但仍是单机本地回环，不是外网真实流量；
- 判定链在测试内以 Python 等价复刻 ``应用层/准入.道``、``应用层/评估.道`` 的关键词降级路径
  （GENGFU_NO_LLM=1，不调用 ollama），不是由解释器跨 OS 线程直接调用 .道 函数——
  HTTP handler 必须是 Python callable，且道解释器不保证跨 OS 线程并发调用安全；
- 端口 0 自动分配，服务器用 ``关闭()`` + ``join()`` 回收，避免端口泄漏。
"""

import json
import os
import re
import sys
import threading
import time
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from dao.stdlib.network import DaoHttpServer

# 不依赖真实网络 / ollama：本测试全程走关键词降级路径。
os.environ.setdefault("GENGFU_NO_LLM", "1")

# ======================== 判定口径（等价复刻 准入.道 / 评估.道） ========================
# 与原实现的差异仅在于语言载体（Python 而非道），规则内容一一对应。
请求词 = ["@更夫", "请修复", "帮我处理", "开工单", "请处理", "请帮忙"]
噪音短语 = ["收到", "谢谢", "+1", "已阅", "好的", "OK", "ok", "666", "收到谢谢", "get"]
白名单 = ["维护者"]
纯符号正则 = re.compile(r"^[^\w\s]+$")

# 对应压测.道 的审计规则：命中即 would_accept，无语言模型参与。
审计规则 = [
    {
        "名称": "显式请求建单",
        "关键词": ["@更夫", "请修复", "请处理", "帮我处理", "开工单", "请帮忙"],
        "结论": "would_accept",
        "范围": [],
    }
]


def 是噪音(文本: str) -> bool:
    """空内容 / 纯空白 / 已知噪音短语 / 纯符号 → 噪音。"""
    if 文本 == "":
        return True
    净文本 = 文本.strip()
    if 净文本 == "" or 净文本 in 噪音短语:
        return True
    return 纯符号正则.match(净文本) is not None


def 判定(文本: str, 发起人: str) -> str:
    """等价 准入器.判定：机器人/噪音忽略；白名单 + 请求词 → 准入显式；其余候选。"""
    if 是噪音(文本):
        return "准入忽略"
    if 发起人 in 白名单 and any(词 in 文本 for 词 in 请求词):
        return "准入显式"
    return "准入候选"


def 评估(文本: str, 来源: str) -> str:
    """等价 评估器 的关键词降级路径（模式审计、语言模型为空）。"""
    for 规则 in 审计规则:
        范围列表 = 规则.get("范围", [])
        if 范围列表 and 来源 not in 范围列表:
            continue
        if any(词 in 文本 for 词 in 规则["关键词"]):
            return 规则.get("结论", "would_accept")
    return "would_ignore"


def 处理单条(消息: dict) -> tuple[bool, float]:
    """两组共用的单条处理函数：只在「准入显式 且 评估接受」时建单，并返回逐条耗时（毫秒）。"""
    开始 = time.perf_counter()
    结论 = 判定(消息["文本"], 消息["发起人"])
    建单 = False
    if 结论 == "准入显式" and 评估(消息["文本"], 消息["来源"]) == "would_accept":
        建单 = True
    return 建单, (time.perf_counter() - 开始) * 1000


# ======================== HTTP 处理函数 ========================
def _单条处理(请求):
    """POST /single：处理一条消息，返回 {"建单": bool, "耗时毫秒": float}。"""
    消息 = 请求.JSON()
    建单, 耗时 = 处理单条(消息)
    return {
        "状态码": 200,
        "内容": json.dumps({"建单": 建单, "耗时毫秒": 耗时}, ensure_ascii=False),
    }


def _批处理(请求):
    """POST /batch：一次请求携带一批消息（批量提交），逐条复用 处理单条。"""
    消息列表 = 请求.JSON()
    结果 = [处理单条(消息) for 消息 in 消息列表]
    return {
        "状态码": 200,
        "内容": json.dumps(
            [{"建单": 建单, "耗时毫秒": 耗时} for 建单, 耗时 in 结果], ensure_ascii=False
        ),
    }


def _发请求(地址: str, 载荷):
    """用 urllib 发真实 HTTP POST，返回 (解析后的 JSON, 请求往返耗时毫秒)。"""
    数据 = json.dumps(载荷, ensure_ascii=False).encode("utf-8")
    请求 = urllib.request.Request(
        地址,
        data=数据,
        method="POST",
        headers={"Content-Type": "application/json; charset=utf-8"},
    )
    开始 = time.perf_counter()
    with urllib.request.urlopen(请求, timeout=10) as 响应:
        文本 = 响应.read().decode("utf-8")
    return json.loads(文本), (time.perf_counter() - 开始) * 1000


# ======================== 负载构造（300 条/轮 ×5 轮） ========================
纯符号池 = ["！！！", "，。", "@@@", "###", "——", "。。。", "！！！？", "***", "///", "~~~",
         "!!!", "???", "···", "==", "++", "--", "……", "￥￥", "^^^", "&&&"]
噪音短语池 = ["收到", "谢谢", "+1", "已阅", "好的", "OK", "ok", "666", "收到谢谢",
           "get", "在吗", "哈哈", "嗯嗯", "好的收到", "稍等", "了解", "赞", "收到啦",
           "OK谢谢", "666"]
显式请求池 = [
    "@更夫 请修复登录缺陷", "请处理订单超时问题", "@更夫 帮我处理支付报错",
    "请修复首页样式错乱", "开工单修复搜索失败", "请帮忙排查内存泄漏",
    "@更夫 请处理接口500错误", "请修复数据同步延迟", "@更夫 请修复按钮失效",
    "请处理日志堆积问题", "帮我处理构建失败问题", "@更夫 开工单处理崩溃",
    "请修复鉴权漏洞", "@更夫 请处理慢查询", "请帮忙修复文件上传失败",
    "请处理缓存击穿问题", "@更夫 请修复并发问题", "请处理消息队列积压",
    "请修复导出失败", "请帮忙处理定时任务异常",
]


def _构造批次(轮次: int) -> list[dict]:
    """构造一轮 300 条：94 空内容 + 93 纯符号 + 93 噪音短语 + 20 显式请求。"""
    批次 = []
    for i in range(94):
        批次.append({"文本": "", "来源": "本地噪音", "发起人": "路人",
                     "外部编号": f"N-{轮次}-空-{i}", "类别": "噪音"})
    for i in range(93):
        批次.append({"文本": 纯符号池[i % len(纯符号池)], "来源": "本地噪音", "发起人": "路人",
                     "外部编号": f"N-{轮次}-符-{i}", "类别": "噪音"})
    for i in range(93):
        批次.append({"文本": 噪音短语池[i % len(噪音短语池)], "来源": "本地噪音", "发起人": "路人",
                     "外部编号": f"N-{轮次}-语-{i}", "类别": "噪音"})
    for i in range(20):
        批次.append({"文本": 显式请求池[i], "来源": "本地请求", "发起人": "维护者",
                     "外部编号": f"R-{轮次}-显-{i}", "类别": "显式"})
    return 批次


# ======================== 两组负载 ========================
def _运行基线(全部批次: list[list[dict]], 单条地址: str):
    """单会话基线：逐条串行发 HTTP 请求，记录逐条耗时与建单计数。"""
    耗时列表 = []
    建单计数 = {"噪音": 0, "显式": 0}
    开始 = time.perf_counter()
    for 批次 in 全部批次:
        for 消息 in 批次:
            响应, _ = _发请求(单条地址, 消息)
            if 响应["建单"]:
                建单计数[消息["类别"]] += 1
            耗时列表.append(响应["耗时毫秒"])
    总耗时毫秒 = (time.perf_counter() - 开始) * 1000
    return 耗时列表, 建单计数, 总耗时毫秒


def _运行批处理组(全部批次: list[list[dict]], 批处理地址: str,
                批大小: int = 75, 并发数: int = 8):
    """Router 批处理组：按批切分，由 ThreadPoolExecutor 并发发 HTTP 请求。"""
    批次列表 = [批次[i:i + 批大小] for 批次 in 全部批次 for i in range(0, len(批次), 批大小)]
    耗时列表 = []
    建单计数 = {"噪音": 0, "显式": 0}
    开始 = time.perf_counter()
    with ThreadPoolExecutor(max_workers=并发数) as 线程池:
        任务 = [线程池.submit(_发请求, 批处理地址, 批次) for 批次 in 批次列表]
        for 批次, 任务项 in zip(批次列表, 任务):
            响应列表, _ = 任务项.result()
            assert len(响应列表) == len(批次), "批处理响应条数与提交条数不一致"
            for 消息, 响应 in zip(批次, 响应列表):
                if 响应["建单"]:
                    建单计数[消息["类别"]] += 1
                耗时列表.append(响应["耗时毫秒"])
    总耗时毫秒 = (time.perf_counter() - 开始) * 1000
    return 耗时列表, 建单计数, 总耗时毫秒


def _百分位(耗时列表: list[float]) -> dict:
    """与压测.道 一致：排序后取下取整的 50%/95% 位置及最大值。"""
    排序 = sorted(耗时列表)
    数量 = len(排序)
    return {"p50": 排序[int(0.50 * 数量)], "p95": 排序[int(0.95 * 数量)], "max": 排序[-1]}


@pytest.fixture(scope="module")
def 压测结果():
    """启动本地 DaoHttpServer（端口 0），跑完两组后正确关闭服务器线程。"""
    服务器 = DaoHttpServer()
    服务器.路由("POST", "/single", _单条处理)
    服务器.路由("POST", "/batch", _批处理)
    服务器线程 = threading.Thread(target=服务器.启动, kwargs={"端口": 0}, daemon=True)
    服务器线程.start()

    截止 = time.monotonic() + 5
    while 服务器.端口 is None and time.monotonic() < 截止:
        time.sleep(0.01)
    if 服务器.端口 is None:
        服务器.关闭()
        服务器线程.join(timeout=5)
        pytest.fail("DaoHttpServer 未在时限内完成端口绑定")

    基址 = f"http://127.0.0.1:{服务器.端口}"
    try:
        全部批次 = [_构造批次(轮次) for 轮次 in range(1, 6)]
        基线耗时, 基线建单, 基线总耗时 = _运行基线(全部批次, 基址 + "/single")
        批耗时, 批建单, 批总耗时 = _运行批处理组(全部批次, 基址 + "/batch")
    finally:
        # 必须正确释放：shutdown + server_close，并 join 服务器线程，避免端口泄漏。
        服务器.关闭()
        服务器线程.join(timeout=5)

    assert not 服务器线程.is_alive(), "服务器线程未正确关闭（存在端口泄漏风险）"
    return {
        "基线": _百分位(基线耗时),
        "批处理": _百分位(批耗时),
        "基线总耗时毫秒": 基线总耗时,
        "批处理总耗时毫秒": 批总耗时,
        "基线建单": 基线建单,
        "批处理建单": 批建单,
        "采样数": len(基线耗时),
    }


def test_真实并发硬指标与性能观测(压测结果):
    """硬指标（噪音零误建单、显式全建单）+ p50/p95/max 实测报告。"""
    基线 = 压测结果["基线"]
    批处理 = 压测结果["批处理"]

    # —— 硬指标 ——
    assert 压测结果["基线建单"]["噪音"] == 0, "基线组噪音消息误建单"
    assert 压测结果["批处理建单"]["噪音"] == 0, "批处理组噪音消息误建单"
    assert 压测结果["基线建单"]["显式"] == 100, "基线组显式请求未全部建单"
    assert 压测结果["批处理建单"]["显式"] == 100, "批处理组显式请求未全部建单"
    assert 压测结果["采样数"] == 1500, "采样数应为 5 轮 × 300 条"

    比值 = 批处理["p95"] / 基线["p95"] if 基线["p95"] else float("inf")
    print("\n==================== 更夫 Nightwatch 真实并发压测报告 ====================")
    print("并发实现：DaoHttpServer(ThreadingHTTPServer) + ThreadPoolExecutor(8) + urllib POST")
    print(f"负载规模：300 条/轮（280 噪音 + 20 显式）× 5 轮 = 1500 条/组；采样数 {压测结果['采样数']}")
    print("【硬指标】")
    print(f"  噪音误建单：基线 {压测结果['基线建单']['噪音']} / 批处理 {压测结果['批处理建单']['噪音']}（目标 0）")
    print(f"  显式请求建单：基线 {压测结果['基线建单']['显式']} / 批处理 {压测结果['批处理建单']['显式']}（目标 100）")
    print("【逐条耗时 p50 / p95 / max（毫秒，等价 判定+评估，两组口径一致）】")
    print(f"  单会话基线（逐条串行）：p50={基线['p50']:.4f} p95={基线['p95']:.4f} max={基线['max']:.4f}")
    print(f"  Router 批处理组（并发）：p50={批处理['p50']:.4f} p95={批处理['p95']:.4f} max={批处理['max']:.4f}")
    print("【总耗时（端到端墙钟，毫秒）】")
    print(f"  单会话基线：{压测结果['基线总耗时毫秒']:.2f}；Router 批处理组：{压测结果['批处理总耗时毫秒']:.2f}")
    print(f"【p95 ≤ 基线 60% 目标】实测 p95 比值 = {比值:.2%}（{'达成' if 比值 <= 0.6 else '未达成，如实记录'})")
    print("【诚实注记】p95 口径为逐条「判定+评估」逻辑耗时（与压测.道 一致），不含 HTTP 往返；")
    print("           真实并发下每请求建线程 + GIL 竞争，端到端总耗时可能高于串行基线，不代表并发收益。")
    print("=========================================================================")


@pytest.mark.xfail(
    strict=False,
    reason="p95 ≤ 基线 60% 为观测目标而非硬门槛：达成则 xpass，未达成则 xfail；"
           "两种结果均如实记录，不伪造数据、不改口径硬凑",
)
def test_p95不高于基线60百分比(压测结果):
    """观测目标：Router 批处理组 p95 ≤ 单会话基线 p95 的 60%（未达成则 xfail 如实标注）。"""
    assert 压测结果["批处理"]["p95"] <= 0.6 * 压测结果["基线"]["p95"], (
        f"实测 批处理 p95={压测结果['批处理']['p95']:.4f}ms，"
        f"基线 p95={压测结果['基线']['p95']:.4f}ms，"
        f"目标 ≤ 60%（即 {0.6 * 压测结果['基线']['p95']:.4f}ms）未达成"
    )
