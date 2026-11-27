"""二进制模块：为「道」语言提供安全、可预期的二进制序列化能力。

包含三类能力：

* ``struct`` 定长打包/解包与整数、浮点和字节的互转；
* 基于 JSON 加类型标签的「安全序列化」，只识别白名单内的基础类型，
  可替代不可信数据场景下的 pickle；
* 字节文件读写，以及对 pickle 的显式拒绝/白名单加载封装。

安全约定：``Pickle解包`` 默认拒绝任何 pickle 数据，只有显式给出可信类型
白名单时才允许加载，且自定义 ``find_class`` 会拦截白名单外的类。
"""

import base64
import io
import json
import os
import pickle
import struct
import sys

from ..builtins.callables import BuiltinFunction
from ..environment import Environment
from ..errors import 类型错误, 运行时错误


def _校验文本(值, 名字):
    """校验参数为文本类型并返回它。"""
    if not isinstance(值, str):
        raise 类型错误(f"{名字}必须是文本类型")
    return 值


def _校验字节(值, 名字):
    """校验参数为字节类型并返回它。"""
    if not isinstance(值, (bytes, bytearray)):
        raise 类型错误(f"{名字}必须是字节类型")
    return bytes(值)


def _字节序(字节序):
    """把中文或英文字节序名称转换为 struct 使用的符号。"""
    _校验文本(字节序, "字节序")
    映射 = {
        "大端": ">", "小端": "<",
        "big": ">", "little": "<",
        ">": ">", "<": "<", "!": "!", "=": "=",
    }
    if 字节序 not in 映射:
        raise 运行时错误("字节序只支持 '大端' 或 '小端'")
    return 映射[字节序]


def _结构格式(格式):
    """校验 struct 格式字符串并返回它。"""
    _校验文本(格式, "格式")
    if not 格式:
        raise 运行时错误("格式字符串不能为空")
    return 格式


def _字节序名称(字节序):
    """把中文或英文字节序名称转换为 to_bytes 使用的名称。"""
    符号 = _字节序(字节序)
    if 符号 == "<":
        return "little"
    if 符号 == "=":
        return sys.byteorder
    return "big"


def _stdlib_定长打包(格式, 值):
    """按 struct 格式字符串把数值打包为定长字节串。

    参数：值为单个数值时按单元素处理；为列表时按列表元素依次打包。
    """
    格式 = _结构格式(格式)
    列表 = list(值) if isinstance(值, (list, tuple)) else [值]
    try:
        return struct.pack(格式, *列表)
    except struct.error as 错误:
        raise 运行时错误(f"定长打包失败: {错误}")


def _stdlib_定长解包(格式, 数据):
    """按 struct 格式字符串把定长字节串解包为数值列表。"""
    格式 = _结构格式(格式)
    数据 = _校验字节(数据, "数据")
    try:
        return list(struct.unpack(格式, 数据))
    except struct.error as 错误:
        raise 运行时错误(f"定长解包失败: {错误}")


def _stdlib_计算大小(格式):
    """返回 struct 格式字符串对应的字节数。"""
    try:
        return struct.calcsize(_结构格式(格式))
    except (struct.error, UnicodeError, ValueError) as 错误:
        raise 运行时错误(f"无效的格式字符串: {错误}")


def _stdlib_整数转字节(整数, 长度=4, 字节序="大端", 有符号=False):
    """把整数转换为固定长度的字节串。"""
    if not isinstance(整数, int) or isinstance(整数, bool):
        raise 类型错误("整数转字节需要一个整数")
    if not isinstance(长度, int) or isinstance(长度, bool) or 长度 < 1:
        raise 运行时错误("长度必须是正整数")
    try:
        return 整数.to_bytes(长度, byteorder=_字节序名称(字节序), signed=bool(有符号))
    except OverflowError as 错误:
        raise 运行时错误(f"整数超出指定字节长度: {错误}")


def _stdlib_字节转整数(数据, 字节序="大端", 有符号=False):
    """把字节串转换回整数。"""
    数据 = _校验字节(数据, "数据")
    return int.from_bytes(数据, byteorder=_字节序名称(字节序), signed=bool(有符号))


def _stdlib_浮点转字节(浮点, 字节序="大端"):
    """把浮点数转换为 8 字节的 IEEE 754 双精度字节串。"""
    if not isinstance(浮点, (int, float)) or isinstance(浮点, bool):
        raise 类型错误("浮点转字节需要一个数值")
    return struct.pack(_字节序(字节序) + "d", float(浮点))


def _stdlib_字节转浮点(数据, 字节序="大端"):
    """把 8 字节的 IEEE 754 双精度字节串转换回浮点数。"""
    数据 = _校验字节(数据, "数据")
    if len(数据) != 8:
        raise 运行时错误("字节转浮点需要恰好 8 个字节")
    return struct.unpack(_字节序(字节序) + "d", 数据)[0]


def _标签编码(值):
    """把受支持的 Python 值编码为带类型标签的可 JSON 结构。"""
    if 值 is None:
        return {"t": "none"}
    if isinstance(值, bool):
        return {"t": "bool", "v": 值}
    if isinstance(值, int):
        return {"t": "int", "v": str(值)}
    if isinstance(值, float):
        return {"t": "float", "v": repr(值)}
    if isinstance(值, str):
        return {"t": "str", "v": 值}
    if isinstance(值, (bytes, bytearray)):
        return {"t": "bytes", "v": base64.b64encode(bytes(值)).decode("ascii")}
    if isinstance(值, (list, tuple)):
        标签 = "list" if isinstance(值, list) else "tuple"
        return {"t": 标签, "v": [_标签编码(元素) for 元素 in 值]}
    if isinstance(值, dict):
        条目 = []
        for 键, 值项 in 值.items():
            if not isinstance(键, (str, int, float, bool, type(None), bytes)):
                raise 类型错误("安全序列化只支持字符串、数值、字节等基础类型作为字典键")
            条目.append([_标签编码(键), _标签编码(值项)])
        return {"t": "dict", "v": 条目}
    raise 类型错误(f"安全序列化不支持类型: {type(值).__name__}")


def _标签解码(标签):
    """把类型标签结构还原为 Python 值，未知标签一律拒绝。"""
    if not isinstance(标签, dict) or "t" not in 标签:
        raise 运行时错误("安全序列化数据格式无效")
    类型 = 标签["t"]
    if 类型 == "none":
        return None
    if 类型 == "bool":
        return bool(标签.get("v"))
    if 类型 == "int":
        return int(标签["v"])
    if 类型 == "float":
        return float(标签["v"])
    if 类型 == "str":
        return str(标签["v"])
    if 类型 == "bytes":
        return base64.b64decode(标签["v"])
    if 类型 in ("list", "tuple"):
        值列表 = [_标签解码(元素) for 元素 in 标签["v"]]
        return 值列表 if 类型 == "list" else tuple(值列表)
    if 类型 == "dict":
        结果 = {}
        for 键标签, 值标签 in 标签["v"]:
            结果[_标签解码(键标签)] = _标签解码(值标签)
        return 结果
    raise 运行时错误(f"拒绝加载未知类型标签: {类型}")


def _stdlib_安全序列化(数据):
    """把数据以 JSON 类型标签格式安全序列化为字节串。

    支持空值、布尔、整数、浮点、文本、字节、列表、元组与字典；
    不调用 pickle，也不会执行任何对象构造逻辑。
    """
    try:
        return json.dumps(_标签编码(数据), ensure_ascii=False).encode("utf-8")
    except (TypeError, ValueError) as 错误:
        raise 运行时错误(f"安全序列化失败: {错误}")


def _stdlib_安全反序列化(数据):
    """从安全序列化的字节串还原数据，遇到未知类型标签即拒绝。"""
    数据 = _校验字节(数据, "数据")
    try:
        标签 = json.loads(数据.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as 错误:
        raise 运行时错误(f"安全反序列化失败: {错误}")
    return _标签解码(标签)


def _stdlib_写入字节(路径, 数据):
    """把字节串写入文件，返回写入的字节数。"""
    _校验文本(路径, "路径")
    数据 = _校验字节(数据, "数据")
    try:
        with open(路径, "wb") as 文件:
            return 文件.write(数据)
    except OSError as 错误:
        raise 运行时错误(f"写入字节失败: {错误}")


def _stdlib_读取字节(路径):
    """从文件读取全部字节并返回字节串。"""
    _校验文本(路径, "路径")
    if not os.path.isfile(路径):
        raise 运行时错误(f"文件不存在: {路径}")
    try:
        with open(路径, "rb") as 文件:
            return 文件.read()
    except OSError as 错误:
        raise 运行时错误(f"读取字节失败: {错误}")


def _stdlib_序列化到文件(数据, 路径):
    """把数据安全序列化后写入文件，返回写入的字节数。"""
    return _stdlib_写入字节(路径, _stdlib_安全序列化(数据))


def _stdlib_反序列化自文件(路径):
    """从文件读取字节并进行安全反序列化。"""
    return _stdlib_安全反序列化(_stdlib_读取字节(路径))


def _stdlib_Pickle打包(数据):
    """用 pickle 序列化可信数据（仅建议用于完全可信的来源）。"""
    try:
        return pickle.dumps(数据, protocol=pickle.HIGHEST_PROTOCOL)
    except (TypeError, pickle.PicklingError) as 错误:
        raise 运行时错误(f"Pickle 打包失败: {错误}")


class _白名单Unpickler(pickle.Unpickler):
    """仅允许加载白名单中显式列出的模块与类。"""

    def __init__(self, *args, 白名单=(), **kwargs):
        super().__init__(*args, **kwargs)
        self.白名单 = frozenset(白名单)

    def find_class(self, 模块, 名称):
        """拦截未列入白名单的类加载请求。"""
        全名 = f"{模块}.{名称}"
        if 全名 in self.白名单:
            return super().find_class(模块, 名称)
        raise 运行时错误(f"拒绝加载未列入白名单的类型: {全名}")


def _stdlib_Pickle解包(数据, 白名单=None):
    """加载 pickle 字节串；默认拒绝，提供白名单后仅允许指定类型。

    参数：白名单为「模块.类名」字符串列表，例如 ``["builtins.set"]``。
    """
    数据 = _校验字节(数据, "数据")
    if 白名单 is None:
        raise 运行时错误("拒绝加载不可信的 pickle 数据；如需加载请显式提供类型白名单")
    if not isinstance(白名单, (list, tuple)) or not all(isinstance(x, str) for x in 白名单):
        raise 类型错误("白名单必须是文本列表")
    try:
        return _白名单Unpickler(io.BytesIO(数据), 白名单=白名单).load()
    except 运行时错误:
        raise
    except (pickle.UnpicklingError, EOFError, AttributeError, ImportError, ValueError) as 错误:
        raise 运行时错误(f"Pickle 解包失败: {错误}")


def create_module_env(interpreter=None) -> Environment:
    """创建二进制模块的导出环境。"""
    env = Environment()
    导出表 = (
        ("定长打包", _stdlib_定长打包, 2),
        ("定长解包", _stdlib_定长解包, 2),
        ("计算大小", _stdlib_计算大小, 1),
        ("整数转字节", _stdlib_整数转字节, -1),
        ("字节转整数", _stdlib_字节转整数, -1),
        ("浮点转字节", _stdlib_浮点转字节, -1),
        ("字节转浮点", _stdlib_字节转浮点, -1),
        ("安全序列化", _stdlib_安全序列化, 1),
        ("安全反序列化", _stdlib_安全反序列化, 1),
        ("写入字节", _stdlib_写入字节, 2),
        ("读取字节", _stdlib_读取字节, 1),
        ("序列化到文件", _stdlib_序列化到文件, 2),
        ("反序列化自文件", _stdlib_反序列化自文件, 1),
        ("Pickle打包", _stdlib_Pickle打包, 1),
        ("Pickle解包", _stdlib_Pickle解包, -1),
    )
    for 名字, func, 参数个数 in 导出表:
        env.define(名字, BuiltinFunction(名字, func, 参数个数))
    env.exports = list(env.values.keys())
    return env
