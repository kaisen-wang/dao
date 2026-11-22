"""大模型模块：把 Python 侧的大模型接口层暴露为道语言标准库。

提供消息构造、客户端创建、单次对话、流式对话与模型列举五个函数。
所有交给道语言的字典（消息、响应、增量块）均使用中文键。
"""

from ..builtins.callables import BuiltinFunction, DaoCallable, InterpreterBuiltin
from ..environment import Environment
from ..errors import 类型错误, 运行时错误
from ..llm import (
    ChatMessage,
    ChatRequest,
    LLMError,
    create_provider,
)


def _stdlib_消息(角色, 内容):
    """构造一条中文键消息字典，供「对话」与「流式对话」使用。"""
    return {"角色": 角色, "内容": 内容}


def _stdlib_创建客户端(提供者, 配置字典):
    """按提供者名称创建大模型客户端。

    配置字典的键作为 provider 的配置项传入（如 ollama 的 host / model /
    timeout，openai 的 api_key / base_url / model）；配置缺失或提供者未知
    时抛出中文运行时错误。
    """
    if not isinstance(提供者, str):
        raise 类型错误("创建客户端的提供者必须是文本类型")
    if 配置字典 is None:
        配置字典 = {}
    if not isinstance(配置字典, dict):
        raise 类型错误("创建客户端的配置字典必须是字典类型")
    try:
        return create_provider(提供者, **配置字典)
    except LLMError as 错误:
        raise 运行时错误(f"创建大模型客户端失败：{错误}") from None
    except TypeError as 错误:
        raise 运行时错误(f"创建大模型客户端失败：配置项键必须是文本：{错误}") from None


# 中文键 → ChatRequest 字段名的映射（英文键同名，直接按英文键读取）
_选项键映射 = {"模型": "model", "温度": "temperature", "最大token": "max_tokens"}
# 消息中文键 → 英文键的映射
_消息键映射 = {"角色": "role", "内容": "content", "思考": "thinking", "名称": "name"}
_消息英文键 = ("role", "content", "thinking", "name", "tool_call_id", "tool_calls")


def _转消息列表(消息列表):
    """把消息列表统一转换为 ChatMessage 列表。

    元素可以是中文键字典（角色 / 内容）、英文键字典（role / content），
    或已经是 ChatMessage 实例。
    """
    结果 = []
    for 元素 in 消息列表:
        if isinstance(元素, ChatMessage):
            结果.append(元素)
            continue
        if not isinstance(元素, dict):
            raise 类型错误("消息列表的元素必须是字典")
        数据 = {}
        for 中文键, 英文键 in _消息键映射.items():
            if 中文键 in 元素:
                数据[英文键] = 元素[中文键]
        for 英文键 in _消息英文键:
            if 英文键 in 元素:
                数据[英文键] = 元素[英文键]
        try:
            结果.append(ChatMessage.from_dict(数据))
        except ValueError as 错误:
            raise 类型错误(f"消息角色非法：{错误}") from None
    return 结果


def _构造请求(消息列表, 选项字典):
    """根据消息列表与选项字典构造 ChatRequest。

    选项支持中文键（模型 / 温度 / 最大token）或英文键
    （model / temperature / max_tokens），中文键优先。
    """
    if 消息列表 is None:
        消息列表 = []
    if not isinstance(消息列表, (list, tuple)):
        raise 类型错误("对话的消息列表必须是列表")
    if 选项字典 is None:
        选项字典 = {}
    if not isinstance(选项字典, dict):
        raise 类型错误("对话的选项字典必须是字典")

    参数 = {}
    for 中文键, 英文键 in _选项键映射.items():
        if 中文键 in 选项字典:
            参数[英文键] = 选项字典[中文键]
        elif 英文键 in 选项字典:
            参数[英文键] = 选项字典[英文键]
    return ChatRequest(messages=_转消息列表(消息列表), **参数)


def _错误字典(错误):
    """把大模型异常转成道语言可消费的失败字典。"""
    return {"成功": False, "错误": str(错误)}


def _stdlib_对话(客户端, 消息列表, 选项字典):
    """发起一次同步对话，返回中文键的完整响应字典。

    消息列表支持中文键或英文键，选项字典支持模型 / 温度 / 最大token
    或对应的英文键；调用失败时返回含「成功」为假的字典，不抛异常。
    """
    请求 = _构造请求(消息列表, 选项字典)
    try:
        响应 = 客户端.chat(请求)
    except LLMError as 错误:
        return _错误字典(错误)
    return 响应.to_dict()


def _流式对话实现(interpreter, 客户端, 消息列表, 回调函数, 选项字典):
    """流式对话：逐块把增量交给道语言回调，返回累积后的中文键响应。

    回调收到一个含「内容 / 思考 / 完成」的块字典，返回「假」表示提前终止。
    选项字典的键与「对话」相同；调用失败时返回含「成功」为假的字典。
    """
    if interpreter is None:
        raise 运行时错误("流式对话无法获取解释器上下文")
    if not isinstance(回调函数, DaoCallable):
        raise 类型错误("流式对话的回调函数必须是函数")
    请求 = _构造请求(消息列表, 选项字典)

    def 转交(块):
        """把 StreamChunk 转成中文键字典交给回调；返回是否继续。"""
        结果 = interpreter.call_function(回调函数, [块.to_dict()])
        return 结果 is not False

    try:
        响应 = 客户端.chat_stream(请求, 转交)
    except LLMError as 错误:
        return _错误字典(错误)
    return 响应.to_dict()


def _stdlib_列出模型(客户端):
    """列出客户端后端可用的模型名；失败时返回含「成功」为假的字典。"""
    try:
        return 客户端.list_models()
    except LLMError as 错误:
        return _错误字典(错误)


def create_module_env(interpreter=None) -> Environment:
    """创建大模型模块的导出环境。"""
    env = Environment()
    env.define("消息", BuiltinFunction("消息", _stdlib_消息, 2))
    env.define("创建客户端", BuiltinFunction("创建客户端", _stdlib_创建客户端, 2))
    env.define("对话", BuiltinFunction("对话", _stdlib_对话, 3))
    env.define("列出模型", BuiltinFunction("列出模型", _stdlib_列出模型, 1))

    # 回调型内置需要解释器上下文才能调用道语言函数；func 定义在模块级，
    # 保证工厂重复调用时元数据稳定（docgen 依赖此约束）。
    流式对话 = InterpreterBuiltin("流式对话", _流式对话实现, 4)
    if interpreter is not None:
        流式对话.set_interpreter(interpreter)
    env.define("流式对话", 流式对话)

    env.exports = list(env.values.keys())
    return env
