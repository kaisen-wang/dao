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
    ToolDefinition,
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
_消息键映射 = {
    "角色": "role",
    "内容": "content",
    "思考": "thinking",
    "名称": "name",
    "调用编号": "tool_call_id",
}
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


# 中文键 JSON Schema → 英文键的映射
_模式键映射 = {
    "类型": "type",
    "描述": "description",
    "必填": "required",
    "属性": "properties",
    "条目": "items",
    "枚举": "enum",
}


def _规范化参数模式(参数模式):
    """把中文键或英文键的参数模式统一成英文键 JSON Schema。"""
    if 参数模式 is None:
        return {"type": "object", "properties": {}}
    if not isinstance(参数模式, dict):
        raise 类型错误("参数模式必须是字典")
    if "type" in 参数模式 or "properties" in 参数模式:
        return 参数模式
    结果 = {}
    for 键, 值 in 参数模式.items():
        英文键 = _模式键映射.get(键, 键)
        if 英文键 == "properties" and isinstance(值, dict):
            属性 = {}
            for 名称, 定义 in 值.items():
                if isinstance(定义, dict):
                    属性[名称] = {
                        _模式键映射.get(子键, 子键): 子值 for 子键, 子值 in 定义.items()
                    }
                elif isinstance(定义, str):
                    属性[名称] = {"type": 定义}
                else:
                    属性[名称] = 定义
            结果[英文键] = 属性
        elif 英文键 == "required" and isinstance(值, (list, tuple)):
            结果[英文键] = list(值)
        else:
            结果[英文键] = 值
    结果.setdefault("type", "object")
    return 结果


def _stdlib_工具定义(名称, 描述=None, 参数模式=None):
    """声明一个可调用工具，返回 OpenAI 风格 tool 字典供「工具对话」使用。

    名称须为非空文本；描述为给模型看的中文说明；参数模式支持中文键
    （属性/必填/类型/描述）或标准英文 JSON Schema。
    """
    if not isinstance(名称, str) or not 名称.strip():
        raise 类型错误("工具定义的名称必须是非空文本")
    if 描述 is None:
        描述 = ""
    if not isinstance(描述, str):
        raise 类型错误("工具定义的描述必须是文本")
    return ToolDefinition(
        name=名称,
        description=描述,
        parameters=_规范化参数模式(参数模式),
    ).to_dict()


def _stdlib_工具结果(调用编号, 内容):
    """构造一条 role=tool 的消息字典，供手动多轮工具对话追加结果。"""
    if not isinstance(调用编号, str):
        raise 类型错误("工具结果的调用编号必须是文本")
    return {"角色": "tool", "内容": 内容, "调用编号": 调用编号}


def _转工具列表(工具列表):
    """把工具列表统一成 OpenAI 风格 tool 字典列表。"""
    if 工具列表 is None:
        return []
    if not isinstance(工具列表, (list, tuple)):
        raise 类型错误("工具列表必须是列表")
    结果 = []
    for 工具 in 工具列表:
        if isinstance(工具, ToolDefinition):
            结果.append(工具.to_dict())
        elif isinstance(工具, dict):
            if "名称" in 工具:
                结果.append(
                    _stdlib_工具定义(
                        工具["名称"], 工具.get("描述", ""), 工具.get("参数模式")
                    )
                )
            else:
                结果.append(工具)
        else:
            raise 类型错误("工具列表的元素必须是工具定义或字典")
    return 结果


def _工具对话实现(interpreter, 客户端, 消息列表, 工具列表, 回调函数, 选项字典):
    """工具对话：自动多轮调用模型并执行工具回调，返回中文键的完整记录。

    每轮把模型返回的 tool_calls 逐个交给道语言回调（参数：名称、参数字典），
    把返回值作为 tool 消息追加，再进入下一轮，直到模型不再请求工具或达到
    「最大轮次」。任一轮失败返回含「成功」为假的字典，不抛异常。
    """
    if interpreter is None:
        raise 运行时错误("工具对话无法获取解释器上下文")
    if not isinstance(回调函数, DaoCallable):
        raise 类型错误("工具对话的回调函数必须是函数")
    if 选项字典 is None:
        选项字典 = {}
    if not isinstance(选项字典, dict):
        raise 类型错误("工具对话的选项字典必须是字典")
    最大轮次 = 选项字典.get("最大轮次", 5)
    if isinstance(最大轮次, bool) or not isinstance(最大轮次, int) or 最大轮次 < 1:
        return {"成功": False, "错误": "最大轮次必须是正整数"}

    请求 = _构造请求(消息列表, 选项字典)
    请求.tools = _转工具列表(工具列表)
    记录 = []
    用量 = {"提示token": 0, "生成token": 0, "总token": 0}

    for 轮次 in range(1, 最大轮次 + 1):
        try:
            响应 = 客户端.chat_with_tools(请求)
        except LLMError as 错误:
            return {
                "成功": False,
                "错误": str(错误),
                "工具调用记录": 记录,
                "用量": 用量,
                "轮次": 轮次 - 1,
            }

        本轮用量 = 响应.usage.to_dict()
        for 键 in ("提示token", "生成token", "总token"):
            用量[键] += 本轮用量.get(键, 0)

        调用列表 = 响应.tool_calls or []
        if not 调用列表:
            return {
                "成功": True,
                "内容": 响应.content or "",
                "工具调用记录": 记录,
                "用量": 用量,
                "轮次": 轮次,
            }

        请求.add_message(
            ChatMessage(role="assistant", content=响应.content or "", tool_calls=调用列表)
        )
        for 调用 in 调用列表:
            名称 = 调用.get("name", "")
            参数 = 调用.get("arguments", {}) or {}
            调用编号 = 调用.get("id", "")
            try:
                结果 = interpreter.call_function(回调函数, [名称, 参数])
            except Exception as 错误:  # noqa: BLE001  工具回调失败降级为错误文本，不中断对话
                结果 = f"工具执行失败：{错误}"
            if not isinstance(结果, str):
                结果 = str(结果) if 结果 is not None else ""
            记录.append({"名称": 名称, "参数": 参数, "结果": 结果})
            请求.add_message(
                ChatMessage(role="tool", content=结果, tool_call_id=调用编号)
            )

    return {
        "成功": False,
        "错误": f"工具对话达到最大轮次 {最大轮次}，仍未得到最终答复",
        "工具调用记录": 记录,
        "用量": 用量,
        "轮次": 最大轮次,
    }


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
    env.define("工具定义", BuiltinFunction("工具定义", _stdlib_工具定义, -1))
    env.define("工具结果", BuiltinFunction("工具结果", _stdlib_工具结果, 2))

    # 回调型内置需要解释器上下文才能调用道语言函数；func 定义在模块级，
    # 保证工厂重复调用时元数据稳定（docgen 依赖此约束）。
    流式对话 = InterpreterBuiltin("流式对话", _流式对话实现, 4)
    if interpreter is not None:
        流式对话.set_interpreter(interpreter)
    env.define("流式对话", 流式对话)

    工具对话 = InterpreterBuiltin("工具对话", _工具对话实现, 5)
    if interpreter is not None:
        工具对话.set_interpreter(interpreter)
    env.define("工具对话", 工具对话)

    env.exports = list(env.values.keys())
    return env
