import os
import shutil

from ..builtins.callables import BuiltinFunction
from ..environment import Environment
from ..errors import 运行时错误


class DaoLineIterator:
    def __init__(self, file_path: str):
        self._file_path = file_path
        self._file = None
        self._exhausted = False

    def __iter__(self):
        try:
            self._file = open(self._file_path, "r", encoding="utf-8")
            for line in self._file:
                yield line.rstrip("\n")
        except FileNotFoundError:
            raise 运行时错误(f"文件不存在: {self._file_path}")
        finally:
            if self._file:
                self._file.close()
                self._file = None
            self._exhausted = True

    def __del__(self):
        if self._file:
            self._file.close()


def _stdlib_读取(路径):
    if not isinstance(路径, str):
        raise 运行时错误("读取需要文本类型路径参数")
    try:
        with open(路径, "r", encoding="utf-8") as f:
            return f.read()
    except FileNotFoundError:
        raise 运行时错误(f"文件不存在: {路径}")
    except PermissionError:
        raise 运行时错误(f"权限不足，无法读取文件: {路径}")


def _stdlib_写入(路径, 内容):
    if not isinstance(路径, str):
        raise 运行时错误("写入需要文本类型路径参数")
    try:
        with open(路径, "w", encoding="utf-8") as f:
            f.write(内容)
    except PermissionError:
        raise 运行时错误(f"权限不足，无法写入文件: {路径}")


def _stdlib_追加(路径, 内容):
    if not isinstance(路径, str):
        raise 运行时错误("追加需要文本类型路径参数")
    try:
        with open(路径, "a", encoding="utf-8") as f:
            f.write(内容)
    except PermissionError:
        raise 运行时错误(f"权限不足，无法写入文件: {路径}")


def _stdlib_存在(路径):
    return os.path.exists(路径)


def _stdlib_列出目录(路径):
    if not isinstance(路径, str):
        raise 运行时错误("列出目录需要文本类型路径参数")
    if not os.path.exists(路径):
        raise 运行时错误(f"目录不存在: {路径}")
    if not os.path.isdir(路径):
        raise 运行时错误(f"路径不是目录: {路径}")
    return os.listdir(路径)


def _stdlib_逐行读取(路径):
    if not isinstance(路径, str):
        raise 运行时错误("逐行读取需要文本类型路径参数")
    return DaoLineIterator(路径)


def _stdlib_复制(源, 目标):
    try:
        shutil.copy2(源, 目标)
    except FileNotFoundError:
        raise 运行时错误(f"源文件不存在: {源}")
    except PermissionError:
        raise 运行时错误("权限不足，无法复制文件")


def _stdlib_移动(源, 目标):
    try:
        shutil.move(源, 目标)
    except FileNotFoundError:
        raise 运行时错误(f"源文件不存在: {源}")
    except PermissionError:
        raise 运行时错误("权限不足，无法移动文件")


def _stdlib_删除(路径):
    if not os.path.exists(路径):
        raise 运行时错误(f"文件不存在: {路径}")
    try:
        os.remove(路径)
    except PermissionError:
        raise 运行时错误(f"权限不足，无法删除文件: {路径}")


def _stdlib_创建目录(路径):
    try:
        os.makedirs(路径, exist_ok=True)
    except PermissionError:
        raise 运行时错误(f"权限不足，无法创建目录: {路径}")


def _stdlib_文件信息(路径):
    if not os.path.exists(路径):
        raise 运行时错误(f"文件不存在: {路径}")
    stat = os.stat(路径)
    return {
        "大小": stat.st_size,
        "修改时间": stat.st_mtime,
        "是否目录": os.path.isdir(路径),
        "是否文件": os.path.isfile(路径),
    }


def create_module_env(interpreter=None) -> Environment:
    env = Environment()
    env.define("读取", BuiltinFunction("读取", _stdlib_读取, 1))
    env.define("写入", BuiltinFunction("写入", _stdlib_写入, 2))
    env.define("追加", BuiltinFunction("追加", _stdlib_追加, 2))
    env.define("存在", BuiltinFunction("存在", _stdlib_存在, 1))
    env.define("列出目录", BuiltinFunction("列出目录", _stdlib_列出目录, 1))
    env.define("逐行读取", BuiltinFunction("逐行读取", _stdlib_逐行读取, 1))
    env.define("复制", BuiltinFunction("复制", _stdlib_复制, 2))
    env.define("移动", BuiltinFunction("移动", _stdlib_移动, 2))
    env.define("删除", BuiltinFunction("删除", _stdlib_删除, 1))
    env.define("创建目录", BuiltinFunction("创建目录", _stdlib_创建目录, 1))
    env.define("文件信息", BuiltinFunction("文件信息", _stdlib_文件信息, 1))
    env.exports = list(env.values.keys())
    return env