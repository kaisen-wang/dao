"""更夫 Nightwatch — 真 .道 规则链子进程并发压测（第十一轮 / 共享契约 §2 C）。

弥补第八轮 ``test_load_real_concurrency.py`` 的诚实缺口：那一轮的判定链是在
Python 里「等价复刻」``应用层/准入.道``、``应用层/评估.道`` 的关键词路径；本轮
改用 ``sys.executable`` 启动**真实 OS 子进程**执行 ``源码/main.py``，由真 .道
解释器加载并执行 ``从 应用层.准入 导入 创建准入器``、
``从 应用层.评估 导入 创建评估器`` 的 ``判定()`` / ``评估()`` 方法链。

口径沿用《示例/更夫/测试/压测.道》：每轮 300 条 = 280 噪音 + 20 显式 × 5 轮；
Python 侧用 ``ThreadPoolExecutor`` 并发启动多个子进程（每进程一批消息），
工作负载 .道 脚本在 ``tempfile.TemporaryDirectory()`` 内生成，用 ASCII 环境变量
传 JSON 输入/输出路径，逐条调用真 .道 判定/评估并把结论写回 JSON 结果文件。

硬指标：噪音误建单 = 0（判为 explicit 的噪音数 0）；20 条显式全部判为 explicit
且全部建单；重复投递同一去重键只产生 1 条 Trigger（复用 ``保存触发`` 幂等）。
p50/p95/max 仅观测、不硬断言 p95 ≤ 基线 60%；诚实写明
「本机真子进程并发 ≠ 生产真实流量」。

诚实边界（务必与 PRD 区分）：
- 判定链确由真 .道 解释器子进程执行，但事件仍是本地构造，不是真实 webhook；
- DEFAULT 不依赖真实网络 / ollama（GENGFU_NO_LLM=1 + 评估器不传语言模型，走关键词降级）；
- **不勾选 PRD §12 任何 DoD 项**；本测试只证明「本地可验证部分已实现」。

测试约定：一律用 ``sys.executable``；禁止 ``signal.SIGKILL``，停止子进程用
``proc.terminate()`` 并 fallback ``proc.kill()``；临时文件退出自动清理；
子进程 cwd=``示例/更夫``（模块搜索基于 os.getcwd()）。
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

# 源码/tests/test_rule_engine_real_process.py -> 仓库根目录
PROJECT_ROOT = Path(__file__).resolve().parents[2]
MAIN = PROJECT_ROOT / "源码" / "main.py"
GENGFU_DIR = PROJECT_ROOT / "示例" / "更夫"

# 工作负载通过 ASCII 名环境变量接收 JSON 输入/输出路径与幂等库路径，
# 避免跨平台环境变量编码差异（与第八轮真子进程范式一致）。
ENV_INPUT = "GENGFU_RULE_INPUT"
ENV_OUTPUT = "GENGFU_RULE_OUTPUT"
ENV_DB = "GENGFU_RULE_DB"

# ======================== .道 工作负载（在 tempfile 中生成） ========================
# 真调用链：创建准入器(["维护者"]).判定(触) + 创建评估器(关键词规则).评估(触, 模式审计)。
# 理由字符串「关键词规则：」只存在于 应用层/评估.道，Python 等价复刻无法自然产出，
# 故可用作「确由真 .道 规则链执行」的可观测证据。
WORKLOAD_SCRIPT = """\
// 第十一轮 C — 真 .道 规则链工作负载（由 Python 测试在 tempfile 中生成）。
// 判定链由真 .道 解释器子进程执行，弥补第八轮「Python 等价复刻」缺口；事件仍为本地构造。
从 系统 导入 取环境变量
从 文件 导入 读取, 写入
从 编码 导入 JSON
从 领域层.领域 导入 触发, 准入显式, 模式审计
从 应用层.准入 导入 创建准入器
从 应用层.评估 导入 创建评估器

定义 输入路径 = 取环境变量("GENGFU_RULE_INPUT", "")
定义 输出路径 = 取环境变量("GENGFU_RULE_OUTPUT", "")
定义 消息列表 = JSON.解码(读取(输入路径))

定义 准入器 = 创建准入器(["维护者"])
定义 规则列表 = [
    {"名称":"显式请求建单", "关键词":["@更夫", "请修复", "请处理", "帮我处理", "开工单", "请帮忙"], "结论":"would_accept", "范围":[]}
]
定义 评估器 = 创建评估器(规则列表)

定义 结果列表 = []
遍历 消息项 在 消息列表
    定义 触 = 触发(消息项["来源"], 消息项["外部编号"], 消息项["话题编号"], 消息项["发起人"], 消息项["文本"], 消息项["是否机器人"])
    定义 条开始 = 时间戳()
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
    定义 条耗时 = (时间戳() - 条开始) * 1000
    追加(结果列表, {"外部编号": 消息项["外部编号"], "类别": 消息项["类别"], "判定结论": 判定结论, "结论": 结论, "理由": 理由, "建单": 建单, "耗时毫秒": 条耗时})

写入(输出路径, JSON.编码(结果列表))
"""

# 幂等工作负载：跨真实子进程复用 基础设施层/存储.道 的 保存触发()（按去重键幂等）。
IDEMPOTENCY_SCRIPT = """\
// 第十一轮 C — 真 .道 保存触发幂等工作负载（由 Python 测试在 tempfile 中生成）。
从 系统 导入 取环境变量
从 文件 导入 写入
从 编码 导入 JSON
从 领域层.领域 导入 触发
从 基础设施层.存储 导入 打开存储, 保存触发, 列出触发

定义 数据库路径 = 取环境变量("GENGFU_RULE_DB", "")
定义 输出路径 = 取环境变量("GENGFU_RULE_OUTPUT", "")
定义 重复次数 = 10
打开存储(数据库路径)
定义 重复请求 = 触发("本地请求", "DUP-RULE-KEY", "T-重复投递", "维护者", "@更夫 请修复重复投递")
定义 成功次数 = 0
遍历 i 从 1 到 重复次数
    如果 保存触发(重复请求)
        成功次数 = 成功次数 + 1
定义 触发总数 = 长度(列出触发())
写入(输出路径, JSON.编码({"成功次数": 成功次数, "触发总数": 触发总数, "重复次数": 重复次数}))
"""

# ======================== 负载构造（口径同 压测.道） ========================
纯符号池 = [
    "！！！", "，。", "@@@", "###", "——", "。。。", "！！！？", "***", "///", "~~~",
    "!!!", "???", "···", "==", "++", "--", "……", "￥￥", "^^^", "&&&",
]
噪音短语池 = [
    "收到", "谢谢", "+1", "已阅", "好的", "OK", "ok", "666", "收到谢谢", "get",
    "在吗", "哈哈", "嗯嗯", "好的收到", "稍等", "了解", "赞", "收到啦", "辛苦了", "OK谢谢",
]
显式请求池 = [
    "@更夫 请修复登录缺陷", "请处理订单超时问题", "@更夫 帮我处理支付报错",
    "请修复首页样式错乱", "开工单修复搜索失败", "请帮忙排查内存泄漏",
    "@更夫 请处理接口500错误", "请修复数据同步延迟", "@更夫 请修复按钮失效",
    "请处理日志堆积问题", "帮我处理构建失败问题", "@更夫 开工单处理崩溃",
    "请修复鉴权漏洞", "@更夫 请处理慢查询", "请帮忙修复文件上传失败",
    "请处理缓存击穿问题", "@更夫 请修复并发问题", "请处理消息队列积压",
    "请修复导出失败", "请帮忙处理定时任务异常",
]


def _消息(文本: str, 来源: str, 发起人: str, 外部编号: str, 类别: str) -> dict:
    """构造一条本地事件（不是真实 webhook），字段对应 领域.道 的 触发.初始化。"""
    return {
        "文本": 文本,
        "来源": 来源,
        "发起人": 发起人,
        "外部编号": 外部编号,
        "话题编号": "T-噪音" if 类别 == "噪音" else "T-请求",
        "类别": 类别,
        "是否机器人": False,
    }


def _构造批次(轮次: int) -> list[dict]:
    """构造一轮 300 条：94 空 + 93 纯符号 + 93 噪音短语 = 280 噪音，+20 显式。"""
    批次 = []
    for i in range(94):
        批次.append(_消息("", "本地噪音", "路人", f"N-{轮次}-空-{i}", "噪音"))
    for i in range(93):
        批次.append(_消息(纯符号池[i % len(纯符号池)], "本地噪音", "路人", f"N-{轮次}-符-{i}", "噪音"))
    for i in range(93):
        批次.append(_消息(噪音短语池[i % len(噪音短语池)], "本地噪音", "路人", f"N-{轮次}-语-{i}", "噪音"))
    for i in range(20):
        批次.append(_消息(显式请求池[i], "本地请求", "维护者", f"R-{轮次}-显-{i}", "显式"))
    return 批次


def _切分(批次: list[dict], 份数: int) -> list[list[dict]]:
    """把一轮切成若干块，每块由一个独立子进程处理。"""
    块大小 = (len(批次) + 份数 - 1) // 份数
    return [批次[i:i + 块大小] for i in range(0, len(批次), 块大小)]


# ======================== 真子进程启动与回收 ========================
def _启动工作负载(脚本路径: Path, 输入路径: Path, 输出路径: Path,
                数据库路径: Path | None = None) -> subprocess.Popen:
    """用 sys.executable 启动真实 OS 子进程运行 .道 工作负载（不硬编码 .venv 路径）。"""
    环境变量 = os.environ.copy()
    环境变量["PYTHONPATH"] = str(MAIN.parent)
    环境变量[ENV_INPUT] = str(输入路径)
    环境变量[ENV_OUTPUT] = str(输出路径)
    环境变量[ENV_DB] = str(数据库路径) if 数据库路径 is not None else ""
    环境变量["GENGFU_NO_LLM"] = "1"  # 不依赖真实网络 / ollama
    return subprocess.Popen(
        [sys.executable, str(MAIN), str(脚本路径)],
        cwd=str(GENGFU_DIR),
        env=环境变量,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )


def _回收(进程: subprocess.Popen, 超时秒: float = 10) -> tuple[str, str]:
    """等待子进程结束；超时用 terminate() + fallback kill()，绝不使用 signal.SIGKILL。"""
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


def _跑一批(临时路径: Path, 脚本路径: Path, 消息列表: list[dict], 标签: str,
           数据库路径: Path | None = None, 跳过条数校验: bool = False) -> tuple[list, float]:
    """写输入 JSON → 起真子进程 → 读输出 JSON，返回 (结果, 批墙钟毫秒)。

    跳过条数校验=True 用于幂等工作负载（输出是统计字典而非逐条列表）。
    """
    输入路径 = 临时路径 / f"输入-{标签}.json"
    输出路径 = 临时路径 / f"输出-{标签}.json"
    输入路径.write_text(json.dumps(消息列表, ensure_ascii=False), encoding="utf-8")

    进程 = _启动工作负载(脚本路径, 输入路径, 输出路径, 数据库路径)
    开始 = time.perf_counter()
    _标准输出, 标准错误 = _回收(进程)
    墙钟毫秒 = (time.perf_counter() - 开始) * 1000

    assert 进程.returncode == 0, (
        f"工作负载[{标签}]退出码 {进程.returncode}；stderr={标准错误!r}"
    )
    assert 输出路径.exists(), f"工作负载[{标签}]未写出 JSON 结果文件"
    结果 = json.loads(输出路径.read_text(encoding="utf-8"))
    if not 跳过条数校验:
        assert len(结果) == len(消息列表), (
            f"工作负载[{标签}]结果条数 {len(结果)} != 输入条数 {len(消息列表)}"
        )
    return 结果, 墙钟毫秒


def _百分位(耗时列表: list[float]) -> dict:
    """与 压测.道 一致：排序后取下取整 50%/95% 位置及最大值。"""
    排序 = sorted(耗时列表)
    数量 = len(排序)
    return {
        "p50": 排序[int(0.50 * 数量)],
        "p95": 排序[int(0.95 * 数量)],
        "max": 排序[-1],
    }


@pytest.fixture(scope="module")
def 工作负载脚本路径(tmp_path_factory):
    """模块级只生成一次 .道 工作负载脚本，退出时随 tmp_path 自动清理。"""
    目录 = tmp_path_factory.mktemp("更夫规则链脚本-")
    脚本 = 目录 / "工作负载.道"
    脚本.write_text(WORKLOAD_SCRIPT, encoding="utf-8")
    幂等脚本 = 目录 / "幂等.道"
    幂等脚本.write_text(IDEMPOTENCY_SCRIPT, encoding="utf-8")
    return {"判定评估": 脚本, "幂等": 幂等脚本}


# ======================== 用例 ========================
def test_真道子进程执行准入与评估链(工作负载脚本路径):
    """最小批次验证：子进程确由真 .道 解释器跑 判定()/评估()，不是 Python 等价复刻。"""
    消息列表 = [
        _消息("", "本地噪音", "路人", "SMOKE-空-0", "噪音"),
        _消息("@更夫 请修复登录缺陷", "本地请求", "维护者", "SMOKE-显-0", "显式"),
        _消息("收到", "本地噪音", "路人", "SMOKE-语-0", "噪音"),
        _消息("请处理订单超时问题", "本地请求", "维护者", "SMOKE-显-1", "显式"),
    ]
    with tempfile.TemporaryDirectory(prefix="更夫规则链冒烟-") as 临时目录:
        结果, _ = _跑一批(Path(临时目录), 工作负载脚本路径["判定评估"], 消息列表, "冒烟")

    按编号 = {行["外部编号"]: 行 for 行 in 结果}
    assert 按编号["SMOKE-空-0"]["判定结论"] != "explicit", "空内容噪音被误判为 explicit"
    assert 按编号["SMOKE-语-0"]["判定结论"] != "explicit", "噪音短语被误判为 explicit"
    assert 按编号["SMOKE-显-0"]["判定结论"] == "explicit", "显式请求未被真 .道 准入器判为 explicit"
    assert 按编号["SMOKE-显-1"]["判定结论"] == "explicit", "显式请求未被真 .道 准入器判为 explicit"
    assert 按编号["SMOKE-显-0"]["建单"] is True, "显式请求未被真 .道 评估器建单"
    assert 按编号["SMOKE-显-1"]["建单"] is True, "显式请求未被真 .道 评估器建单"
    # 「关键词规则：」前缀只存在于 应用层/评估.道 源码中，是真规则链执行的证据。
    assert 按编号["SMOKE-显-0"]["理由"].startswith("关键词规则："), (
        "评估理由未带 评估.道 的「关键词规则：」前缀，疑似 Python 复刻"
    )


def test_噪音零误建单(工作负载脚本路径):
    """280 条噪音经真 .道 判定：判为 explicit 的数量 0、建单 0。"""
    噪音 = [消 for 消 in _构造批次(1) if 消["类别"] == "噪音"]
    assert len(噪音) == 280, "口径应为 280 条噪音"
    with tempfile.TemporaryDirectory(prefix="更夫规则链噪音-") as 临时目录:
        结果, _ = _跑一批(Path(临时目录), 工作负载脚本路径["判定评估"], 噪音, "噪音")

    assert len(结果) == 280
    显式数 = sum(1 for 行 in 结果 if 行["判定结论"] == "explicit")
    建单数 = sum(1 for 行 in 结果 if 行["建单"])
    黑洞数 = sum(1 for 行 in 结果 if 行["判定结论"] == "ignore")
    assert 显式数 == 0, f"噪音被误判为 explicit：{显式数} 条"
    assert 建单数 == 0, f"噪音被误建单：{建单数} 条"
    # 已知噪音短语/空内容/纯符号应被准入器判为 ignore；其余普通评论为 candidate 亦不算误建单。
    assert 黑洞数 > 0, "真 .道 判定结果中应存在 ignore（噪音直接忽略）"
    print(f"\n噪音校验：280 条，误判 explicit {显式数}，误建单 {建单数}，ignore {黑洞数}")


def test_显式请求全判显式且全建单(工作负载脚本路径):
    """20 条显式请求经真 .道 判定全为 explicit，且评估全 would_accept → 建单。"""
    显式 = [消 for 消 in _构造批次(1) if 消["类别"] == "显式"]
    assert len(显式) == 20, "口径应为 20 条显式"
    with tempfile.TemporaryDirectory(prefix="更夫规则链显式-") as 临时目录:
        结果, _ = _跑一批(Path(临时目录), 工作负载脚本路径["判定评估"], 显式, "显式")

    assert len(结果) == 20
    显式数 = sum(1 for 行 in 结果 if 行["判定结论"] == "explicit")
    建单数 = sum(1 for 行 in 结果 if 行["建单"] is True)
    assert 显式数 == 20, f"显式请求未全判 explicit：{显式数}/20"
    assert 建单数 == 20, f"显式请求未全建单：{建单数}/20"
    assert all(行["理由"].startswith("关键词规则：") for 行 in 结果), (
        "存在非 评估.道 产生的理由"
    )
    print(f"\n显式校验：20 条，判 explicit {显式数}，建单 {建单数}")


def test_重复投递同一去重键仅一条触发(工作负载脚本路径):
    """跨真子进程复用 保存触发() 幂等：连投 10 次仅第 1 次成功，再投仍不新增。"""
    with tempfile.TemporaryDirectory(prefix="更夫规则链幂等-") as 临时目录:
        临时路径 = Path(临时目录)
        数据库 = 临时路径 / "规则链.db"  # 每例独立，项目目录不产生 .db

        首结果, _ = _跑一批(
            临时路径, 工作负载脚本路径["幂等"], [], "幂等-首轮",
            数据库路径=数据库, 跳过条数校验=True,
        )
        assert 首结果["成功次数"] == 1, f"首轮 10 次投递应仅 1 次成功，实际 {首结果['成功次数']}"
        assert 首结果["触发总数"] == 1, f"首轮触发总数应为 1，实际 {首结果['触发总数']}"

        # 另起一个真子进程重投同一去重键：应 0 次成功、触发总数仍为 1。
        次结果, _ = _跑一批(
            临时路径, 工作负载脚本路径["幂等"], [], "幂等-次轮",
            数据库路径=数据库, 跳过条数校验=True,
        )
        assert 次结果["成功次数"] == 0, f"重复子进程投递应 0 次成功，实际 {次结果['成功次数']}"
        assert 次结果["触发总数"] == 1, f"重复投递不应新增触发，实际 {次结果['触发总数']}"

    print(
        "\n幂等校验：首轮成功 1/10、触发 1；跨进程重投成功 0/10、触发仍为 1"
    )


@pytest.fixture(scope="module")
def 五轮并发结果(工作负载脚本路径):
    """ThreadPoolExecutor 并发起 5 轮 ×4 块 = 20 个真子进程，收集全部判定结果。"""
    with tempfile.TemporaryDirectory(prefix="更夫规则链并发-") as 临时目录:
        临时路径 = Path(临时目录)
        全部批次 = [_构造批次(轮次) for 轮次 in range(1, 6)]

        任务列表 = []
        元数据 = []
        with ThreadPoolExecutor(max_workers=8) as 线程池:
            for 轮次, 批次 in enumerate(全部批次, start=1):
                for 块号, 块 in enumerate(_切分(批次, 4)):
                    标签 = f"R{轮次}C{块号}"
                    任务列表.append(
                        线程池.submit(_跑一批, 临时路径, 工作负载脚本路径["判定评估"], 块, 标签)
                    )
                    元数据.append(标签)

        全部结果 = []
        墙钟列表 = []
        for 标签, 任务 in zip(元数据, 任务列表):
            结果, 墙钟 = 任务.result()  # 子进程断言失败会在此抛出
            全部结果.extend(结果)
            墙钟列表.append(墙钟)

    return {
        "结果": 全部结果,
        "批墙钟列表": 墙钟列表,
        "子进程数": len(任务列表),
    }


def test_五轮并发硬指标与性能观测(五轮并发结果):
    """硬指标：噪音零误建单、显式 100 条全 explicit 且全建单；p50/p95/max 仅观测。"""
    结果 = 五轮并发结果["结果"]
    assert len(结果) == 1500, f"采样数应为 5 轮 × 300 条 = 1500，实际 {len(结果)}"

    噪音误判 = sum(1 for 行 in 结果 if 行["类别"] == "噪音" and 行["判定结论"] == "explicit")
    噪音建单 = sum(1 for 行 in 结果 if 行["类别"] == "噪音" and 行["建单"])
    显式显式 = sum(1 for 行 in 结果 if 行["类别"] == "显式" and 行["判定结论"] == "explicit")
    显式建单 = sum(1 for 行 in 结果 if 行["类别"] == "显式" and 行["建单"] is True)

    # —— 硬指标（与 压测.道 / 第八轮口径一致）——
    assert 噪音误判 == 0, f"噪音被判为 explicit：{噪音误判} 条"
    assert 噪音建单 == 0, f"噪音误建单：{噪音建单} 条"
    assert 显式显式 == 100, f"显式请求全判 explicit：{显式显式}/100"
    assert 显式建单 == 100, f"显式请求全建单：{显式建单}/100"

    耗时 = _百分位([行["耗时毫秒"] for 行 in 结果])
    墙钟 = 五轮并发结果["批墙钟列表"]

    print("\n================ 真 .道 规则链子进程并发压测报告 ================")
    print("实现：sys.executable 启真 OS 子进程 + ThreadPoolExecutor(8) 并发；"
          "每子进程跑 真 .道 判定()/评估()（非 Python 等价复刻）")
    print(f"负载：300 条/轮（280 噪音 + 20 显式）× 5 轮 = 1500 条；"
          f"并发子进程 {五轮并发结果['子进程数']} 个（每轮切 4 块）")
    print("【硬指标】")
    print(f"  噪音误判 explicit：{噪音误判}（目标 0）；噪音误建单：{噪音建单}（目标 0）")
    print(f"  显式判 explicit：{显式显式}/100（目标 100）；显式建单：{显式建单}/100（目标 100）")
    print("【逐条判定+评估耗时（毫秒，真 .道 解释器内计时；仅观测）】")
    print(f"  p50={耗时['p50']:.4f}  p95={耗时['p95']:.4f}  max={耗时['max']:.4f}")
    print("【每批子进程端到端墙钟（毫秒，仅观测）】")
    print(f"  最小={min(墙钟):.2f}  最大={max(墙钟):.2f}  合计={sum(墙钟):.2f}")
    print("【诚实注记】p50/p95/max 仅观测，不硬断言 p95 ≤ 基线 60%；"
          "本机真子进程并发 ≠ 生产真实流量（事件仍为本地构造、非真实 webhook）。")
    print("  PRD §12 六项 DoD 全部继续保持未勾选，本测试只证明本地可验证部分。")
    print("=============================================================")


def test_子进程回收且项目目录不留本用例临时文件(工作负载脚本路径):
    """对比真子进程运行前后的项目目录文件快照，断言本测试没有新增残留。

    快照只筛「本用例产物前缀」，不误伤既有 gitignored 产物（如其它测试生成的
    ``_测_主代理可靠性.db``）——它们不是本测试创建的，不予删除也不纳入断言。
    """
    本用例产物前缀 = ("规则链.db", "工作负载.道", "幂等.道", "输入-", "输出-")

    def 快照() -> set[str]:
        return {
            路径.name for 路径 in GENGFU_DIR.rglob("*")
            if 路径.is_file() and 路径.name.startswith(本用例产物前缀)
        }

    运行前 = 快照()
    with tempfile.TemporaryDirectory(prefix="更夫规则链清理校验-") as 临时目录:
        临时路径 = Path(临时目录)
        消息列表 = [_消息("@更夫 请修复清理校验", "本地请求", "维护者", "CLEAN-0", "显式")]
        结果, _ = _跑一批(临时路径, 工作负载脚本路径["判定评估"], 消息列表, "清理校验")
        assert 结果[0]["判定结论"] == "explicit"
    assert not 临时路径.exists(), "TemporaryDirectory 退出后未清理工作负载"

    新增 = 快照() - 运行前
    assert not 新增, f"本测试在项目目录新增残留文件：{新增}"
    assert MAIN.exists(), "源码/main.py 不存在，无法启动真 .道 子进程"
    assert (GENGFU_DIR / "应用层" / "准入.道").exists(), "真 .道 规则链源文件缺失"
    assert (GENGFU_DIR / "应用层" / "评估.道").exists(), "真 .道 规则链源文件缺失"
