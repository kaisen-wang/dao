"""大模型接口层的统一数据模型。

屏蔽 Ollama / OpenAI / Anthropic 等后端在消息与响应结构上的差异，
向上层（道语言桥接、Agent 业务）提供稳定的 Python 数据结构。

凡需交给道语言消费的字典，一律使用中文键（见 ``to_dict`` 方法）。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

有效角色 = frozenset({"system", "user", "assistant", "tool"})


class LLMError(Exception):
    """大模型接口层异常基类。"""


class ProviderError(LLMError):
    """Provider 调用失败（网络、HTTP 错误或响应格式异常）。"""


class ConfigError(LLMError):
    """Provider 配置缺失或非法。"""


class UnsupportedError(LLMError):
    """Provider 不支持所请求的能力（如工具调用）。"""


@dataclass
class ChatMessage:
    """一条聊天消息，字段对齐主流 Provider 的通用语义。

    ``thinking`` 用于承载 gemma4 等模型的思考过程；``tool_calls`` /
    ``tool_call_id`` 为后续 Function Calling / Tool Use 预留。
    """

    role: str
    content: str
    thinking: str | None = None
    name: str | None = None
    tool_call_id: str | None = None
    tool_calls: list[dict[str, Any]] | None = None

    def __post_init__(self) -> None:
        if self.role not in 有效角色:
            raise ValueError(f"未知的消息角色：{self.role}")

    def to_dict(self) -> dict[str, Any]:
        """转换为英文键字典，便于直接作为 Provider 的请求体字段。"""
        data: dict[str, Any] = {"role": self.role, "content": self.content}
        if self.thinking:
            data["thinking"] = self.thinking
        if self.name is not None:
            data["name"] = self.name
        if self.tool_call_id is not None:
            data["tool_call_id"] = self.tool_call_id
        if self.tool_calls:
            data["tool_calls"] = self.tool_calls
        return data

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ChatMessage:
        """从英文键字典还原消息；缺失字段取安全默认值。"""
        return cls(
            role=str(data.get("role", "user")),
            content=str(data.get("content", "")),
            thinking=data.get("thinking"),
            name=data.get("name"),
            tool_call_id=data.get("tool_call_id"),
            tool_calls=data.get("tool_calls"),
        )


def user(content: str) -> ChatMessage:
    """构造一条用户消息。"""
    return ChatMessage(role="user", content=content)


def system(content: str) -> ChatMessage:
    """构造一条系统消息。"""
    return ChatMessage(role="system", content=content)


def assistant(content: str) -> ChatMessage:
    """构造一条助手消息。"""
    return ChatMessage(role="assistant", content=content)


@dataclass
class ToolDefinition:
    """一个可调用工具的定义（与具体 Provider 无关）。

    ``parameters`` 使用英文键的 JSON Schema（type / properties / required）；
    ``to_dict`` 输出 OpenAI 风格的 function tool 字典，供 ``ChatRequest.tools`` 使用。
    """

    name: str
    description: str = ""
    parameters: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """转换为 OpenAI 风格 tool 字典。"""
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.parameters,
            },
        }


@dataclass
class ToolCall:
    """模型请求调用一次工具，参数已解析为字典。"""

    id: str
    name: str
    arguments: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """转成中文键字典，供道语言桥接层直接消费。"""
        return {"编号": self.id, "名称": self.name, "参数": self.arguments}


@dataclass
class Usage:
    """一次调用的 token 用量；``extra`` 承载后端特有指标。"""

    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
    extra: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """转成中文键字典。"""
        return {
            "提示token": self.prompt_tokens,
            "生成token": self.completion_tokens,
            "总token": self.total_tokens,
            **self.extra,
        }


@dataclass
class ChatRequest:
    """一次对话请求，与 Provider 无关。"""

    messages: list[ChatMessage]
    model: str | None = None
    temperature: float | None = None
    top_p: float | None = None
    max_tokens: int | None = None
    stream: bool = False
    stop: list[str] | None = None
    tools: list[dict[str, Any]] | None = None
    options: dict[str, Any] = field(default_factory=dict)

    def add_message(self, message: ChatMessage) -> None:
        """追加一条消息。"""
        self.messages.append(message)


@dataclass
class ChatResponse:
    """一次对话的完整响应。

    ``raw`` 保留后端原始响应，便于调试与统计；``to_dict`` 提供道语言
    可直接消费的中文键视图。
    """

    content: str
    model: str = ""
    role: str = "assistant"
    thinking: str | None = None
    usage: Usage = field(default_factory=Usage)
    finish_reason: str | None = None
    tool_calls: list[dict[str, Any]] | None = None
    raw: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """转成中文键字典，供道语言桥接层直接返回。"""
        return {
            "内容": self.content,
            "模型": self.model,
            "角色": self.role,
            "思考": self.thinking or "",
            "完成原因": self.finish_reason or "",
            "用量": self.usage.to_dict(),
            "成功": True,
            "工具调用": [
                {
                    "编号": 调用.get("id", ""),
                    "名称": 调用.get("name", ""),
                    "参数": 调用.get("arguments", {}),
                }
                for 调用 in (self.tool_calls or [])
            ],
            "原始": self.raw,
        }


@dataclass
class StreamChunk:
    """流式对话的一个增量块。"""

    content: str = ""
    thinking: str = ""
    done: bool = False
    raw: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """转成中文键字典，供道语言回调消费。"""
        return {"内容": self.content, "思考": self.thinking, "完成": self.done}
