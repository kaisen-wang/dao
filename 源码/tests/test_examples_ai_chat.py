"""AI 对话示例的回归测试
========================

用 mock 拦住 urllib.request.urlopen，模拟本机 ollama 的 /api/tags 与 /api/chat，
验证 示例/AI对话/ 下三个 .道 示例的语法与逻辑，不依赖真实 ollama 服务。

设置环境变量 DAO_AI_LIVE=1 时，会额外跑一次真实服务对话（默认跳过）。
"""

import io
import json
import os
import sys
import urllib.error
from contextlib import redirect_stdout
from unittest.mock import patch

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from dao.interpreter import Interpreter
from dao.lexer import Lexer
from dao.parser import Parser

示例目录 = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "..", "示例", "AI对话")
)

_标签数据 = {
    "models": [
        {
            "name": "gemma4:e4b",
            "size": 6583656505,
            "details": {
                "parameter_size": "7.5B",
                "quantization_level": "Q4_K_M",
                "context_length": 131072,
            },
        },
        {
            "name": "lfm3-omni:latest",
            "size": 2049482162,
            "details": {
                "parameter_size": "1.7B",
                "quantization_level": "Q4_K_M",
                "context_length": 128000,
            },
        },
    ]
}


class _假响应:
    """模拟 urlopen 返回的上下文管理器对象。"""

    def __init__(self, 状态码=200, 数据=None, 文本=None):
        self.status = 状态码
        self.headers = {"Content-Type": "application/json"}
        if 文本 is not None:
            self._体 = 文本.encode("utf-8")
        elif 数据 is not None:
            self._体 = json.dumps(数据, ensure_ascii=False).encode("utf-8")
        else:
            self._体 = b""

    def read(self):
        return self._体

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False


class _假流式响应:
    """模拟 ollama 的流式响应，支持逐行 readline()。"""

    def __init__(self, 行列表):
        self.status = 200
        self.headers = {"Content-Type": "application/x-ndjson"}
        self._队列 = list(行列表)

    def readline(self):
        if not self._队列:
            return b""
        return self._队列.pop(0).encode("utf-8")

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False


def _聊天数据(回复, 思考="", token数=20, 耗时=1500000000):
    消息 = {"role": "assistant", "content": 回复}
    if 思考:
        消息["thinking"] = 思考
    return {
        "model": "gemma4:e4b",
        "message": 消息,
        "done": True,
        "eval_count": token数,
        "total_duration": 耗时,
    }


class _假Ollama:
    """按 URL 分派的假 ollama 服务，并记录收到的 /api/chat 请求。"""

    def __init__(self, 回复列表=None, 思考="", 聊天状态码=200,
                 标签数据=None, 标签状态码=200, 全部失败=False):
        self.回复列表 = 回复列表 or ["这是模型的回答"]
        self.思考 = 思考
        self.聊天状态码 = 聊天状态码
        self.标签数据 = 标签数据 if 标签数据 is not None else _标签数据
        self.标签状态码 = 标签状态码
        self.全部失败 = 全部失败
        self.聊天请求 = []
        self.标签请求数 = 0

    def __call__(self, req, **kwargs):
        if self.全部失败:
            raise urllib.error.URLError("Connection refused")
        url = req.full_url
        if url.endswith("/api/tags"):
            self.标签请求数 += 1
            return _假响应(状态码=self.标签状态码, 数据=self.标签数据)
        if url.endswith("/api/chat"):
            数据 = json.loads(req.data.decode("utf-8")) if req.data else {}
            self.聊天请求.append({
                "方法": req.get_method(),
                "数据": 数据,
                "请求头": dict(req.header_items()),
            })
            if 数据.get("stream") is True:
                序号 = min(len(self.聊天请求) - 1, len(self.回复列表) - 1)
                return _假流式响应(self._生成流式行(self.回复列表[序号]))
            if self.聊天状态码 != 200:
                return _假响应(状态码=self.聊天状态码,
                               文本='{"error": "模型不存在或请求无效"}')
            序号 = min(len(self.聊天请求) - 1, len(self.回复列表) - 1)
            return _假响应(数据=_聊天数据(self.回复列表[序号], 思考=self.思考))
        return _假响应(状态码=404, 文本="未找到路由")

    def _生成流式行(self, 回复):
        """模拟 NDJSON 流：thinking 块 + 两个 content 块 + done 块。"""
        return [
            json.dumps({"model": "gemma4:e4b",
                        "message": {"role": "assistant", "thinking": "先想一下"},
                        "done": False}, ensure_ascii=False),
            json.dumps({"model": "gemma4:e4b",
                        "message": {"role": "assistant", "content": 回复[:1]},
                        "done": False}, ensure_ascii=False),
            json.dumps({"model": "gemma4:e4b",
                        "message": {"role": "assistant", "content": 回复[1:]},
                        "done": False}, ensure_ascii=False),
            json.dumps({"model": "gemma4:e4b",
                        "message": {"role": "assistant", "content": ""},
                        "done": True, "eval_count": 42,
                        "total_duration": 2000000000}, ensure_ascii=False),
        ]


def _读取示例(文件名):
    with open(os.path.join(示例目录, 文件名), "r", encoding="utf-8") as f:
        return f.read()


def _执行示例(文件名, 输入序列=None, 服务=None, 环境变量=None):
    """执行一个示例，返回 (标准输出文本, 假服务实例)。"""
    源码 = _读取示例(文件名)
    环境 = {"OLLAMA_HOST": "http://localhost:11434", "OLLAMA_MODEL": "gemma4:e4b"}
    if 环境变量:
        环境.update(环境变量)
    输出 = io.StringIO()
    处理器 = 服务 or _假Ollama()
    with patch.dict(os.environ, 环境), \
            patch("builtins.input", side_effect=输入序列 if 输入序列 is not None else []), \
            patch("urllib.request.urlopen", side_effect=处理器), \
            redirect_stdout(输出):
        tokens = Lexer(源码).tokenize()
        ast = Parser(tokens).parse()
        Interpreter().execute(ast)
    return 输出.getvalue(), 处理器


class Test单次问答:
    def test_成功返回回答(self):
        服务 = _假Ollama(回复列表=["道可道，非常道。"])
        输出, 服务 = _执行示例("单次问答.道", 服务=服务)
        assert "模型：gemma4:e4b" in 输出
        assert "问题：用一句话说说你对「道」的理解。" in 输出
        assert "道可道，非常道。" in 输出
        assert "生成 token 数：20" in 输出
        assert len(服务.聊天请求) == 1
        请求 = 服务.聊天请求[0]
        assert 请求["方法"] == "POST"
        assert 请求["数据"]["model"] == "gemma4:e4b"
        assert 请求["数据"]["stream"] is False
        assert 请求["数据"]["messages"][0]["role"] == "user"
        assert "application/json" in 请求["请求头"].get("Content-type", "")

    def test_服务不可用给出中文提示(self):
        输出, _ = _执行示例("单次问答.道", 服务=_假Ollama(全部失败=True))
        assert "无法连接 ollama" in 输出
        assert "ollama serve" in 输出
        assert "ollama pull gemma4:e4b" in 输出

    def test_HTTP错误不抛异常(self):
        输出, _ = _执行示例("单次问答.道", 服务=_假Ollama(聊天状态码=404))
        assert "请求失败，HTTP 状态码：404" in 输出

    def test_环境变量可切换模型与地址(self):
        服务 = _假Ollama()
        输出, 服务 = _执行示例(
            "单次问答.道", 服务=服务,
            环境变量={"OLLAMA_HOST": "http://127.0.0.1:12345",
                      "OLLAMA_MODEL": "qwen2.5:latest"},
        )
        assert len(服务.聊天请求) == 1
        assert 服务.聊天请求[0]["数据"]["model"] == "qwen2.5:latest"
        assert "模型：gemma4:e4b" in 输出


class Test模型列表:
    def test_列出本机模型并确认目标就绪(self):
        输出, 服务 = _执行示例("模型列表.道")
        assert "已安装 2 个模型" in 输出
        assert "gemma4:e4b" in 输出
        assert "7.5B" in 输出
        assert "Q4_K_M" in 输出
        assert "✅ gemma4:e4b 已就绪" in 输出
        assert 服务.标签请求数 == 1
        assert 服务.聊天请求 == []

    def test_缺少目标模型时提示拉取(self):
        数据 = {"models": [{"name": "qwen2.5:latest", "size": 1000, "details": {}}]}
        输出, _ = _执行示例("模型列表.道", 服务=_假Ollama(标签数据=数据))
        assert "未知" in 输出  # 容错取字段生效
        assert "未找到 gemma4:e4b" in 输出
        assert "ollama pull gemma4:e4b" in 输出

    def test_服务不可用给出中文提示(self):
        输出, _ = _执行示例("模型列表.道", 服务=_假Ollama(全部失败=True))
        assert "无法连接 ollama" in 输出
        assert "ollama serve" in 输出

    def test_标签接口返回错误状态(self):
        输出, _ = _执行示例("模型列表.道", 服务=_假Ollama(标签状态码=503))
        assert "查询失败，HTTP 状态码：503" in 输出


class Test多轮对话:
    def test_命令分发与退出(self):
        输出, 服务 = _执行示例(
            "对话.道",
            输入序列=["/帮助", "/模型", "/历史", "/清空", "/历史", "/退出"],
        )
        assert "模型 gemma4:e4b 已就绪" in 输出
        assert "可用命令：" in 输出
        assert "当前模型：gemma4:e4b" in 输出
        assert "已清空对话历史。" in 输出
        assert "对话结束：共 0 轮" in 输出
        assert 服务.聊天请求 == []  # 纯命令不应触发 /api/chat

    def test_多轮对话与思考过程(self):
        服务 = _假Ollama(回复列表=["第一句回答", "第二句回答"], 思考="先想一下……")
        输出, 服务 = _执行示例(
            "对话.道", 服务=服务,
            输入序列=["/思考", "第一个问题", "第二个问题", "/退出"],
        )
        assert "已开启思考过程显示。" in 输出
        assert "第一句回答" in 输出
        assert "第二句回答" in 输出
        assert "[思考过程] 先想一下……" in 输出
        assert "对话结束：共 2 轮，累计生成 40 token。" in 输出
        assert len(服务.聊天请求) == 2
        第二轮消息 = 服务.聊天请求[1]["数据"]["messages"]
        assert 第二轮消息[0]["role"] == "system"
        assert 第二轮消息[1] == {"role": "user", "content": "第一个问题"}
        assert 第二轮消息[2] == {"role": "assistant", "content": "第一句回答"}
        assert 第二轮消息[3] == {"role": "user", "content": "第二个问题"}
        # gemma4 多轮历史不能把 thinking 带回下一轮
        for 消息 in 第二轮消息:
            assert "thinking" not in 消息

    def test_输入结束自动退出(self):
        输出, _ = _执行示例("对话.道", 输入序列=EOFError("EOF when reading a line"))
        assert "输入结束，对话退出" in 输出
        assert "对话结束：共 0 轮" in 输出

    def test_请求失败回滚历史(self):
        输出, 服务 = _执行示例(
            "对话.道", 服务=_假Ollama(聊天状态码=500),
            输入序列=["一个问题", "/历史", "/退出"],
        )
        assert "调用失败：HTTP 500" in 输出
        assert "当前历史消息 1 条，已完成 0 轮对话" in 输出
        assert len(服务.聊天请求) == 1

    def test_未知命令提示帮助(self):
        输出, _ = _执行示例("对话.道", 输入序列=["/乱写", "/退出"])
        assert "未知命令：/乱写" in 输出
        assert "/帮助 查看可用命令" in 输出

    def test_思考开关可关闭(self):
        服务 = _假Ollama(回复列表=["回答"], 思考="内部推理")
        输出, _ = _执行示例(
            "对话.道", 服务=服务,
            输入序列=["/思考", "问题甲", "/思考", "问题乙", "/退出"],
        )
        assert "已开启思考过程显示。" in 输出
        assert "已关闭思考过程显示。" in 输出
        assert 输出.count("[思考过程] 内部推理") == 1


class Test流式对话:
    def test_逐块拼接与打字机输出(self):
        服务 = _假Ollama(回复列表=["流式回答内容"])
        输出, 服务 = _执行示例("流式对话.道", 输入序列=["你好", "/退出"], 服务=服务)
        assert "〔思考〕先想一下" in 输出
        assert "〔回答〕流式回答内容" in 输出
        assert "本轮 4 块 / 42 token / 2 秒" in 输出
        assert "对话结束：共 1 轮，累计生成 42 token。" in 输出
        assert len(服务.聊天请求) == 1
        assert 服务.聊天请求[0]["数据"]["stream"] is True

    def test_关闭思考过程显示(self):
        输出, _ = _执行示例(
            "流式对话.道", 输入序列=["/思考", "你好", "/退出"],
            服务=_假Ollama(回复列表=["流式回答内容"]),
        )
        assert "已关闭思考过程显示。" in 输出
        assert "〔思考〕" not in 输出
        assert "〔回答〕流式回答内容" in 输出

    def test_多轮历史只带最终回答(self):
        服务 = _假Ollama(回复列表=["第一轮回复", "第二轮回复"])
        输出, 服务 = _执行示例(
            "流式对话.道", 输入序列=["问题甲", "问题乙", "/退出"], 服务=服务,
        )
        assert "第一轮回复" in 输出
        assert "第二轮回复" in 输出
        assert len(服务.聊天请求) == 2
        第二轮 = 服务.聊天请求[1]["数据"]["messages"]
        assert 第二轮[1] == {"role": "user", "content": "问题甲"}
        assert 第二轮[2] == {"role": "assistant", "content": "第一轮回复"}
        for 消息 in 第二轮:
            assert "thinking" not in 消息

    def test_服务不可用友好降级(self):
        输出, _ = _执行示例(
            "流式对话.道", 输入序列=["你好", "/退出"],
            服务=_假Ollama(全部失败=True),
        )
        assert "流式请求失败" in 输出
        assert "ollama serve" in 输出
        assert "对话结束：共 0 轮" in 输出

    def test_命令与退出(self):
        输出, 服务 = _执行示例(
            "流式对话.道", 输入序列=["/帮助", "/模型", "/清空", "/退出"],
        )
        assert "共 0 轮" in 输出
        assert 服务.聊天请求 == []

    def test_输入结束自动退出(self):
        输出, _ = _执行示例("流式对话.道", 输入序列=EOFError("EOF"))
        assert "输入结束，对话退出" in 输出
        assert "共 0 轮" in 输出


@pytest.mark.skipif(os.environ.get("DAO_AI_LIVE") != "1",
                    reason="设置 DAO_AI_LIVE=1 且本机启动 ollama 时才跑真实模型")
def test_真实服务_单次问答():
    """可选：用本机真实 gemma4:e4b 跑一次单次问答。"""
    源码 = _读取示例("单次问答.道")
    输出 = io.StringIO()
    with patch.dict(os.environ, {
        "OLLAMA_HOST": os.environ.get("OLLAMA_HOST", "http://localhost:11434"),
        "OLLAMA_MODEL": os.environ.get("OLLAMA_MODEL", "gemma4:e4b"),
    }), redirect_stdout(输出):
        tokens = Lexer(源码).tokenize()
        ast = Parser(tokens).parse()
        Interpreter().execute(ast)
    文本 = 输出.getvalue()
    assert "模型：gemma4:e4b" in 文本
    assert "生成 token 数：" in 文本
    assert "无法连接 ollama" not in 文本


@pytest.mark.skipif(os.environ.get("DAO_AI_LIVE") != "1",
                    reason="设置 DAO_AI_LIVE=1 且本机启动 ollama 时才跑真实模型")
def test_真实服务_流式对话():
    """可选：用本机真实 gemma4:e4b 跑一次流式对话。"""
    源码 = _读取示例("流式对话.道")
    输出 = io.StringIO()
    with patch.dict(os.environ, {
        "OLLAMA_HOST": os.environ.get("OLLAMA_HOST", "http://localhost:11434"),
        "OLLAMA_MODEL": os.environ.get("OLLAMA_MODEL", "gemma4:e4b"),
    }), patch("builtins.input", side_effect=["用一句话介绍道语言", "/退出"]), \
            redirect_stdout(输出):
        tokens = Lexer(源码).tokenize()
        ast = Parser(tokens).parse()
        Interpreter().execute(ast)
    文本 = 输出.getvalue()
    assert "〔回答〕" in 文本
    assert "本轮" in 文本
    assert "流式请求失败" not in 文本
