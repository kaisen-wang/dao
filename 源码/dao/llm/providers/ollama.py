"""Ollama Provider：通过 Ollama 原生 HTTP API 提供同步与流式对话能力。

仅使用标准库 ``urllib`` 发起请求，不引入任何第三方依赖。所有网络/HTTP/
解析异常统一转换为 ``ProviderError``；流式回调自身抛出的异常则原样上抛。
"""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from typing import Any

from ..base import OnChunk, Provider
from ..factory import register_provider
from ..types import ChatRequest, ChatResponse, ProviderError, StreamChunk, Usage

_默认主机 = "http://localhost:11434"
_默认模型 = "gemma4:e4b"
_默认超时 = 120

# Ollama 响应中属于后端特有的指标，统一放入 Usage.extra。
_额外用量字段 = (
    "total_duration",
    "load_duration",
    "prompt_eval_duration",
    "eval_duration",
    "created_at",
)


class _回调透传异常(Exception):
    """内部信号：携带回调函数自身抛出的原始异常，以便原样向上传递。"""

    def __init__(self, 原始异常: BaseException) -> None:
        super().__init__(str(原始异常))
        self.原始异常 = 原始异常


def _提取用量(data: dict[str, Any]) -> Usage:
    """从 Ollama 响应字典中提取 token 用量与后端特有指标。"""
    提示 = int(data.get("prompt_eval_count") or 0)
    生成 = int(data.get("eval_count") or 0)
    总数 = data.get("total_tokens")
    总数 = int(总数) if 总数 is not None else 提示 + 生成
    额外 = {字段: data[字段] for 字段 in _额外用量字段 if 字段 in data}
    return Usage(prompt_tokens=提示, completion_tokens=生成, total_tokens=总数, extra=额外)


def _含统计字段(data: dict[str, Any]) -> bool:
    """判断一行响应是否携带用量统计，避免中间行把已累积统计清零。"""
    return any(
        字段 in data
        for 字段 in ("eval_count", "prompt_eval_count", "total_tokens", "total_duration")
    )


@register_provider("ollama")
class OllamaProvider(Provider):
    """Ollama 后端实现，对接 ``/api/chat`` 与 ``/api/tags``。

    构造配置（``**config``）：

    - ``host``：服务地址，默认 ``http://localhost:11434``，可由 ``OLLAMA_HOST`` 兜底。
    - ``model``：默认模型名，默认 ``gemma4:e4b``，可由 ``OLLAMA_MODEL`` 兜底。
    - ``timeout``：请求超时秒数，默认 120。
    """

    def __init__(self, **config: Any) -> None:
        super().__init__(**config)
        主机 = config.get("host") or os.environ.get("OLLAMA_HOST") or _默认主机
        模型 = config.get("model") or os.environ.get("OLLAMA_MODEL") or _默认模型
        self._host = str(主机).rstrip("/")
        self._model = str(模型)
        self._timeout = config.get("timeout", _默认超时)

    def _地址(self, 路径: str) -> str:
        """拼接服务地址与 API 路径。"""
        return f"{self._host}{路径}"

    def _请求体(self, request: ChatRequest, stream: bool) -> dict[str, Any]:
        """把统一的 ChatRequest 转换成 Ollama /api/chat 的请求体。"""
        选项 = dict(request.options)
        if request.temperature is not None:
            选项["temperature"] = request.temperature
        if request.top_p is not None:
            选项["top_p"] = request.top_p
        if request.max_tokens is not None:
            选项["num_predict"] = request.max_tokens
        if request.stop:
            选项["stop"] = request.stop
        return {
            "model": request.model or self._model,
            "messages": [{"role": m.role, "content": m.content} for m in request.messages],
            "stream": stream,
            "options": 选项,
        }

    @staticmethod
    def _关闭(response: Any) -> None:
        """安全关闭响应对象（兼容未实现 close 的测试替身）。"""
        关闭 = getattr(response, "close", None)
        if callable(关闭):
            关闭()

    def _打开响应(self, url: str, 请求体: dict[str, Any]) -> Any:
        """向指定 URL POST JSON 请求体，返回响应对象；失败转 ProviderError。"""
        try:
            数据 = json.dumps(请求体).encode("utf-8")
            req = urllib.request.Request(url, data=数据, method="POST")
            req.add_header("Content-Type", "application/json")
            response = urllib.request.urlopen(req, timeout=self._timeout)
        except urllib.error.HTTPError as exc:
            体 = exc.read().decode("utf-8", errors="replace") if exc.fp else ""
            消息 = f"Ollama 请求失败：HTTP {exc.code} {exc.reason}"
            raise ProviderError(f"{消息} {体}".rstrip()) from None
        except urllib.error.URLError as exc:
            raise ProviderError(f"Ollama 请求失败：{exc.reason}") from None
        except Exception as exc:  # noqa: BLE001 - 兜底转成中文 ProviderError
            raise ProviderError(f"Ollama 请求异常：{exc}") from None
        状态码 = getattr(response, "status", None)
        if isinstance(状态码, int) and 状态码 != 200:
            self._关闭(response)
            raise ProviderError(f"Ollama 请求失败：HTTP {状态码}")
        return response

    @staticmethod
    def _读取文本(response: Any) -> str:
        """从响应对象读取完整文本，兼容返回 bytes 或 str 的实现。"""
        原文 = response.read()
        return 原文.decode("utf-8", errors="replace") if isinstance(原文, bytes) else str(原文)

    def chat(self, request: ChatRequest) -> ChatResponse:
        """同步对话：向 /api/chat 发起非流式请求并返回完整响应。"""
        response = self._打开响应(self._地址("/api/chat"), self._请求体(request, False))
        try:
            data = json.loads(self._读取文本(response))
        except json.JSONDecodeError as exc:
            raise ProviderError(f"Ollama 响应不是合法 JSON：{exc}") from None
        except urllib.error.URLError as exc:
            raise ProviderError(f"Ollama 读取响应失败：{exc.reason}") from None
        except Exception as exc:  # noqa: BLE001 - 兜底转成中文 ProviderError
            raise ProviderError(f"Ollama 响应异常：{exc}") from None
        finally:
            self._关闭(response)
        if not isinstance(data, dict):
            raise ProviderError("Ollama 响应格式异常：期望 JSON 对象")
        if data.get("error"):
            raise ProviderError(f"Ollama 返回错误：{data['error']}")
        消息 = data.get("message") or {}
        return ChatResponse(
            content=消息.get("content") or "",
            thinking=消息.get("thinking"),
            usage=_提取用量(data),
            model=data.get("model") or "",
            finish_reason=data.get("done_reason"),
            raw=data,
        )

    def chat_stream(self, request: ChatRequest, on_chunk: OnChunk) -> ChatResponse:
        """流式对话：逐行读取 NDJSON，增量回调 on_chunk 并累积完整响应。

        回调返回 ``False`` 时提前停止读取；回调自身抛出的异常原样向上传递。
        """
        if not callable(on_chunk):
            raise ProviderError("Ollama 流式对话需要一个可调用的回调函数")
        response = self._打开响应(self._地址("/api/chat"), self._请求体(request, True))
        内容片段: list[str] = []
        思考片段: list[str] = []
        用量 = Usage()
        末行: dict[str, Any] = {}
        try:
            while True:
                try:
                    原始行 = response.readline()
                except Exception as exc:  # noqa: BLE001 - 兜底转成中文 ProviderError
                    raise ProviderError(f"Ollama 读取流式响应失败：{exc}") from None
                if not 原始行:
                    break
                行 = 原始行.decode("utf-8", errors="replace") if isinstance(原始行, bytes) else str(原始行)
                行 = 行.strip()
                if not 行:
                    continue
                try:
                    data = json.loads(行)
                    if not isinstance(data, dict):
                        raise TypeError("期望 JSON 对象")
                except (ValueError, TypeError) as exc:
                    raise ProviderError(f"Ollama 流式响应行不是合法 JSON：{exc}") from None
                if data.get("error"):
                    raise ProviderError(f"Ollama 返回错误：{data['error']}")
                消息 = data.get("message") or {}
                内容增量 = 消息.get("content") or ""
                思考增量 = 消息.get("thinking") or ""
                内容片段.append(内容增量)
                思考片段.append(思考增量)
                if _含统计字段(data):
                    用量 = _提取用量(data)
                末行 = data
                块 = StreamChunk(
                    content=内容增量,
                    thinking=思考增量,
                    done=bool(data.get("done", False)),
                    raw=data,
                )
                try:
                    结果 = on_chunk(块)
                except Exception as exc:
                    raise _回调透传异常(exc) from exc
                if 结果 is False:
                    break
        except _回调透传异常 as exc:
            raise exc.原始异常 from None
        except ProviderError:
            raise
        except Exception as exc:  # noqa: BLE001 - 兜底转成中文 ProviderError
            raise ProviderError(f"Ollama 流式响应异常：{exc}") from None
        finally:
            self._关闭(response)
        return ChatResponse(
            content="".join(内容片段),
            thinking="".join(思考片段) or None,
            usage=用量,
            model=末行.get("model") or "",
            finish_reason=末行.get("done_reason"),
            raw=末行,
        )

    def list_models(self) -> list[str]:
        """列出 Ollama 本地已安装模型的名称。"""
        try:
            req = urllib.request.Request(self._地址("/api/tags"), method="GET")
            response = urllib.request.urlopen(req, timeout=self._timeout)
        except urllib.error.HTTPError as exc:
            raise ProviderError(f"Ollama 查询模型失败：HTTP {exc.code} {exc.reason}") from None
        except urllib.error.URLError as exc:
            raise ProviderError(f"Ollama 查询模型失败：{exc.reason}") from None
        except Exception as exc:  # noqa: BLE001 - 兜底转成中文 ProviderError
            raise ProviderError(f"Ollama 查询模型异常：{exc}") from None
        try:
            data = json.loads(self._读取文本(response))
        except (ValueError, TypeError) as exc:
            raise ProviderError(f"Ollama 模型列表不是合法 JSON：{exc}") from None
        except Exception as exc:  # noqa: BLE001 - 兜底转成中文 ProviderError
            raise ProviderError(f"Ollama 模型列表异常：{exc}") from None
        finally:
            self._关闭(response)
        if not isinstance(data, dict):
            raise ProviderError("Ollama 模型列表格式异常：期望 JSON 对象")
        模型组 = data.get("models") or []
        return [str(m.get("name")) for m in 模型组 if isinstance(m, dict) and m.get("name")]
