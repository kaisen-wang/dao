"""路径模块：为「道」语言提供路径拼接、拆分、判断、遍历与匹配能力。

所有函数仅依赖 Python 标准库，路径分隔符使用 ``os.path`` 以兼容不同平台。
"""

import glob as _glob
import os

from ..builtins.callables import BuiltinFunction
from ..environment import Environment
from ..errors import 类型错误, 运行时错误


def _校验路径(值, 名字="路径"):
    """校验路径参数为文本类型。"""
    if not isinstance(值, str):
        raise 类型错误(f"{名字}必须是文本类型")
    return 值


def _stdlib_拼接(*片段):
    """把多个路径片段拼接为一个路径，绝对路径片段会覆盖之前的相对片段。"""
    if not 片段:
        raise 运行时错误("拼接至少需要一个路径片段")
    for 片段项 in 片段:
        _校验路径(片段项, "路径片段")
    return os.path.join(*片段)


def _stdlib_取文件名(路径):
    """返回路径最后一段的文件名（含扩展名），目录路径返回末尾目录名。"""
    _校验路径(路径)
    return os.path.basename(路径)


def _stdlib_取主名(路径):
    """返回路径最后一段去掉扩展名后的主文件名。"""
    _校验路径(路径)
    return os.path.splitext(os.path.basename(路径))[0]


def _stdlib_取扩展名(路径):
    """返回路径最后一段的扩展名（含前导点），没有扩展名时返回空文本。"""
    _校验路径(路径)
    return os.path.splitext(os.path.basename(路径))[1]


def _stdlib_取父目录(路径):
    """返回路径的父目录部分，没有父目录时返回空文本。"""
    _校验路径(路径)
    return os.path.dirname(路径)


def _stdlib_分割(路径):
    """把路径拆分为「父目录」与「文件名」两部分组成的列表。"""
    _校验路径(路径)
    return list(os.path.split(路径))


def _stdlib_绝对路径(路径):
    """把路径转换为基于当前工作目录的规范化绝对路径。"""
    _校验路径(路径)
    return os.path.abspath(路径)


def _stdlib_规范化(路径):
    """规范化路径，合并冗余分隔符与 ``.`` / ``..`` 段。"""
    _校验路径(路径)
    return os.path.normpath(路径)


def _stdlib_相对路径(路径, 起点=None):
    """返回路径相对于起点目录的相对路径，起点省略时相对当前工作目录。"""
    _校验路径(路径)
    if 起点 is None:
        起点 = os.getcwd()
    else:
        _校验路径(起点, "起点")
    return os.path.relpath(路径, 起点)


def _stdlib_存在(路径):
    """判断路径是否存在，存在返回真，否则返回假。"""
    _校验路径(路径)
    return os.path.exists(路径)


def _stdlib_是文件(路径):
    """判断路径是否指向一个已存在的文件。"""
    _校验路径(路径)
    return os.path.isfile(路径)


def _stdlib_是目录(路径):
    """判断路径是否指向一个已存在的目录。"""
    _校验路径(路径)
    return os.path.isdir(路径)


def _stdlib_列出(路径):
    """列出目录下的条目名称，按字典序排序返回。"""
    _校验路径(路径)
    if not os.path.isdir(路径):
        raise 运行时错误(f"目录不存在: {路径}")
    return sorted(os.listdir(路径))


def _stdlib_遍历(路径):
    """递归遍历目录，返回其中所有文件与子目录的完整路径列表。"""
    _校验路径(路径)
    if not os.path.isdir(路径):
        raise 运行时错误(f"目录不存在: {路径}")
    结果 = []
    for 当前目录, 子目录列表, 文件列表 in os.walk(路径):
        for 名称 in 子目录列表:
            结果.append(os.path.join(当前目录, 名称))
        for 名称 in 文件列表:
            结果.append(os.path.join(当前目录, 名称))
    return sorted(结果)


def _stdlib_匹配(模式, 递归=False):
    """按通配符模式匹配路径并返回排序后的路径列表，递归为真时启用 ``**``。"""
    _校验路径(模式, "模式")
    if not isinstance(递归, bool):
        raise 类型错误("递归必须是布尔类型")
    return sorted(_glob.glob(模式, recursive=递归))


def create_module_env(interpreter=None) -> Environment:
    """创建路径模块的导出环境。"""
    env = Environment()
    导出表 = (
        ("拼接", _stdlib_拼接, -1),
        ("取文件名", _stdlib_取文件名, 1),
        ("取主名", _stdlib_取主名, 1),
        ("取扩展名", _stdlib_取扩展名, 1),
        ("取父目录", _stdlib_取父目录, 1),
        ("分割", _stdlib_分割, 1),
        ("绝对路径", _stdlib_绝对路径, 1),
        ("规范化", _stdlib_规范化, 1),
        ("相对路径", _stdlib_相对路径, -1),
        ("存在", _stdlib_存在, 1),
        ("是文件", _stdlib_是文件, 1),
        ("是目录", _stdlib_是目录, 1),
        ("列出", _stdlib_列出, 1),
        ("遍历", _stdlib_遍历, 1),
        ("匹配", _stdlib_匹配, -1),
    )
    for 名字, func, 参数个数 in 导出表:
        env.define(名字, BuiltinFunction(名字, func, 参数个数))
    env.exports = list(env.values.keys())
    return env
