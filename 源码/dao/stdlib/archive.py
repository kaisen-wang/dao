"""归档模块：为「道」语言提供 zip/tar 打包、解包与成员列举能力。

解包时校验成员路径，拒绝绝对路径与 ``..`` 穿越，避免归档文件写到目标目录之外。
"""

import os
import tarfile
import zipfile

from ..builtins.callables import BuiltinFunction
from ..environment import Environment
from ..errors import 类型错误, 运行时错误


def _校验文本(值, 名字):
    """校验路径或模式参数为文本类型。"""
    if not isinstance(值, str):
        raise 类型错误(f"{名字}必须是文本类型")
    return 值


def _收集文件(源路径):
    """把文件或目录路径展开为「磁盘路径, 归档内名称」列表。"""
    _校验文本(源路径, "源路径")
    if os.path.islink(源路径):
        raise 运行时错误(f"不支持打包符号链接: {源路径}")
    if os.path.isfile(源路径):
        return [(源路径, os.path.basename(源路径))]
    if not os.path.isdir(源路径):
        raise 运行时错误(f"源路径不存在: {源路径}")
    结果 = []
    根目录 = os.path.abspath(源路径)
    for 当前目录, 子目录列表, 文件列表 in os.walk(根目录):
        子目录列表[:] = [名称 for 名称 in 子目录列表 if not os.path.islink(os.path.join(当前目录, 名称))]
        for 名称 in 文件列表:
            完整路径 = os.path.join(当前目录, 名称)
            if os.path.islink(完整路径):
                continue
            归档名 = os.path.relpath(完整路径, 根目录)
            结果.append((完整路径, 归档名))
    return 结果


def _安全成员路径(目标目录, 成员名):
    """校验归档成员路径不会越出目标目录，返回解析后的绝对路径。"""
    _校验文本(成员名, "成员名")
    规范目标 = os.path.realpath(目标目录)
    if os.path.isabs(成员名) or 成员名.startswith(("/", "\\")):
        raise 运行时错误(f"归档包含绝对路径成员: {成员名}")
    if ".." in 成员名.replace("\\", "/").split("/"):
        raise 运行时错误(f"归档包含越界成员: {成员名}")
    解析后 = os.path.realpath(os.path.join(规范目标, 成员名))
    if 解析后 != 规范目标 and not 解析后.startswith(规范目标 + os.sep):
        raise 运行时错误(f"归档成员路径越界: {成员名}")
    return 解析后


def _校验压缩包存在(路径, 名字):
    """校验压缩包路径存在且为文件。"""
    _校验文本(路径, 名字)
    if not os.path.isfile(路径):
        raise 运行时错误(f"归档文件不存在: {路径}")
    return 路径


def _stdlib_打包ZIP(源路径, 目标路径):
    """把文件或目录打包为 zip 归档，目录内容按相对路径存放。"""
    _校验文本(目标路径, "目标路径")
    文件列表 = _收集文件(源路径)
    try:
        with zipfile.ZipFile(目标路径, "w", zipfile.ZIP_DEFLATED) as 归档:
            for 磁盘路径, 归档名 in 文件列表:
                归档.write(磁盘路径, 归档名)
    except OSError as 错误:
        raise 运行时错误(f"创建 zip 归档失败: {错误}")
    return 目标路径


def _stdlib_解包ZIP(压缩包路径, 目标目录):
    """把 zip 归档解压到目标目录，拒绝路径穿越成员。"""
    _校验压缩包存在(压缩包路径, "压缩包路径")
    _校验文本(目标目录, "目标目录")
    try:
        with zipfile.ZipFile(压缩包路径, "r") as 归档:
            成员列表 = 归档.namelist()
            for 成员名 in 成员列表:
                _安全成员路径(目标目录, 成员名)
            归档.extractall(目标目录)
    except zipfile.BadZipFile:
        raise 运行时错误("无效的 zip 归档")
    except OSError as 错误:
        raise 运行时错误(f"解压 zip 归档失败: {错误}")
    return 目标目录


def _stdlib_列出ZIP(压缩包路径):
    """列出 zip 归档中的全部成员名称。"""
    _校验压缩包存在(压缩包路径, "压缩包路径")
    try:
        with zipfile.ZipFile(压缩包路径, "r") as 归档:
            return 归档.namelist()
    except zipfile.BadZipFile:
        raise 运行时错误("无效的 zip 归档")


def _stdlib_打包TAR(源路径, 目标路径, 压缩=None):
    """把文件或目录打包为 tar 归档；压缩可为 gz、bz2、xz 或空值。"""
    _校验文本(目标路径, "目标路径")
    if 压缩 is not None and 压缩 not in ("gz", "bz2", "xz"):
        raise 运行时错误("压缩方式只支持 gz、bz2、xz 或空值")
    模式 = "w" if 压缩 is None else f"w:{压缩}"
    文件列表 = _收集文件(源路径)
    try:
        with tarfile.open(目标路径, 模式) as 归档:
            for 磁盘路径, 归档名 in 文件列表:
                归档.add(磁盘路径, arcname=归档名, recursive=False)
    except OSError as 错误:
        raise 运行时错误(f"创建 tar 归档失败: {错误}")
    return 目标路径


def _stdlib_解包TAR(压缩包路径, 目标目录):
    """把 tar 归档解压到目标目录，拒绝绝对路径与路径穿越成员。"""
    _校验压缩包存在(压缩包路径, "压缩包路径")
    _校验文本(目标目录, "目标目录")
    try:
        with tarfile.open(压缩包路径, "r:*") as 归档:
            成员列表 = 归档.getmembers()
            for 成员 in 成员列表:
                _安全成员路径(目标目录, 成员.name)
            归档.extractall(目标目录, members=成员列表, filter="data")
    except tarfile.ReadError:
        raise 运行时错误("无效的 tar 归档")
    except (ValueError, OSError) as 错误:
        raise 运行时错误(f"解压 tar 归档失败: {错误}")
    return 目标目录


def _stdlib_列出TAR(压缩包路径):
    """列出 tar 归档中的全部成员名称。"""
    _校验压缩包存在(压缩包路径, "压缩包路径")
    try:
        with tarfile.open(压缩包路径, "r:*") as 归档:
            return 归档.getnames()
    except tarfile.ReadError:
        raise 运行时错误("无效的 tar 归档")


def create_module_env(interpreter=None) -> Environment:
    """创建归档模块的导出环境。"""
    env = Environment()
    导出表 = (
        ("打包ZIP", _stdlib_打包ZIP, 2),
        ("解包ZIP", _stdlib_解包ZIP, 2),
        ("列出ZIP", _stdlib_列出ZIP, 1),
        ("打包TAR", _stdlib_打包TAR, -1),
        ("解包TAR", _stdlib_解包TAR, 2),
        ("列出TAR", _stdlib_列出TAR, 1),
    )
    for 名字, func, 参数个数 in 导出表:
        env.define(名字, BuiltinFunction(名字, func, 参数个数))
    env.exports = list(env.values.keys())
    return env
