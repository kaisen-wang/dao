"""进程模块：为「道」语言提供安全的子进程创建、输出捕获与生命周期管理。

命令始终以「程序名 + 参数列表」形式传给 ``subprocess``，不使用 shell 拼接字符串，
避免命令注入风险。
"""

import subprocess

from ..builtins.callables import BuiltinFunction
from ..environment import Environment
from ..errors import 类型错误, 运行时错误


class DaoProcessResult:
    """子进程执行结果，包含退出码、标准输出与标准错误。"""

    def __init__(self, 退出码, 标准输出, 标准错误):
        self.退出码 = 退出码
        self.标准输出 = 标准输出
        self.标准错误 = 标准错误

    @property
    def 成功(self):
        """子进程是否以退出码 0 结束。"""
        return self.退出码 == 0

    def __repr__(self):
        return f"<进程结果 退出码={self.退出码}>"


class DaoProcess:
    """运行中的子进程封装，提供等待、终止与通信等操作。"""

    def __init__(self, popen):
        self._popen = popen

    @property
    def 进程号(self):
        """子进程的操作系统进程号。"""
        return self._popen.pid

    def 等待(self, 超时=None):
        """等待子进程结束并返回退出码，超时则抛出运行时错误。"""
        try:
            return self._popen.wait(timeout=超时)
        except subprocess.TimeoutExpired:
            raise 运行时错误("等待进程超时")

    def 终止(self):
        """终止子进程。"""
        self._popen.terminate()

    def 是否运行(self):
        """子进程是否仍在运行。"""
        return self._popen.poll() is None

    def 退出码(self):
        """返回子进程退出码，仍在运行时返回空值。"""
        return self._popen.poll()

    def 通信(self, 输入=None, 超时=None):
        """与子进程通信，返回「标准输出」与「标准错误」组成的列表。"""
        try:
            标准输出, 标准错误 = self._popen.communicate(输入, timeout=超时)
        except subprocess.TimeoutExpired:
            raise 运行时错误("进程通信超时")
        return [标准输出, 标准错误]


def _校验命令(命令):
    """校验程序名参数。"""
    if not isinstance(命令, str) or not 命令:
        raise 类型错误("命令必须是非空文本")
    return 命令


def _校验参数(参数):
    """校验参数列表，返回字符串列表。"""
    if 参数 is None:
        return []
    if not isinstance(参数, (list, tuple)):
        raise 类型错误("参数必须是列表或元组")
    for 项 in 参数:
        if not isinstance(项, str):
            raise 类型错误("参数列表中的每一项都必须是文本")
    return list(参数)


def _校验工作目录(工作目录):
    """校验工作目录参数。"""
    if 工作目录 is not None and not isinstance(工作目录, str):
        raise 类型错误("工作目录必须是文本")
    return 工作目录


def _校验超时(超时):
    """校验超时参数。"""
    if 超时 is not None and (isinstance(超时, bool) or not isinstance(超时, (int, float)) or 超时 <= 0):
        raise 类型错误("超时必须是正数")
    return 超时


def _校验进程(进程):
    """校验 DaoProcess 对象。"""
    if not isinstance(进程, DaoProcess):
        raise 类型错误("需要进程对象")
    return 进程


def _stdlib_运行命令(命令, 参数=None, 工作目录=None, 超时=None):
    """运行子进程并捕获输出，返回含退出码、标准输出、标准错误的结果对象。"""
    _校验命令(命令)
    参数列表 = _校验参数(参数)
    _校验工作目录(工作目录)
    _校验超时(超时)
    try:
        完成结果 = subprocess.run(
            [命令, *参数列表],
            capture_output=True,
            text=True,
            cwd=工作目录,
            timeout=超时,
            check=False,
        )
    except subprocess.TimeoutExpired:
        raise 运行时错误("命令执行超时")
    except FileNotFoundError:
        raise 运行时错误(f"找不到命令: {命令}")
    except OSError as 错误:
        raise 运行时错误(f"启动进程失败: {错误}")
    return DaoProcessResult(完成结果.returncode, 完成结果.stdout, 完成结果.stderr)


def _stdlib_启动命令(命令, 参数=None, 工作目录=None):
    """启动子进程并立即返回进程对象，不等待其结束。"""
    _校验命令(命令)
    参数列表 = _校验参数(参数)
    _校验工作目录(工作目录)
    try:
        进程对象 = subprocess.Popen(
            [命令, *参数列表],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            cwd=工作目录,
        )
    except FileNotFoundError:
        raise 运行时错误(f"找不到命令: {命令}")
    except OSError as 错误:
        raise 运行时错误(f"启动进程失败: {错误}")
    return DaoProcess(进程对象)


def _stdlib_等待进程(进程, 超时=None):
    """等待子进程结束并返回退出码，可指定超时秒数。"""
    _校验进程(进程)
    _校验超时(超时)
    return 进程.等待(超时)


def _stdlib_终止进程(进程):
    """向子进程发送终止信号。"""
    _校验进程(进程)
    进程.终止()


def _stdlib_是否运行(进程):
    """判断子进程是否仍在运行。"""
    _校验进程(进程)
    return 进程.是否运行()


def _stdlib_进程退出码(进程):
    """返回子进程的退出码，若仍在运行则返回空值。"""
    _校验进程(进程)
    return 进程.退出码()


def _stdlib_进程通信(进程, 输入=None, 超时=None):
    """向子进程发送数据并读取全部输出，返回「标准输出、标准错误」列表。"""
    _校验进程(进程)
    _校验超时(超时)
    return 进程.通信(输入, 超时)


def create_module_env(interpreter=None) -> Environment:
    """创建进程模块的导出环境。"""
    env = Environment()
    导出表 = (
        ("运行命令", _stdlib_运行命令, -1),
        ("启动命令", _stdlib_启动命令, -1),
        ("等待进程", _stdlib_等待进程, -1),
        ("终止进程", _stdlib_终止进程, 1),
        ("是否运行", _stdlib_是否运行, 1),
        ("进程退出码", _stdlib_进程退出码, 1),
        ("进程通信", _stdlib_进程通信, -1),
    )
    for 名字, func, 参数个数 in 导出表:
        env.define(名字, BuiltinFunction(名字, func, 参数个数))
    env.define("进程结果", DaoProcessResult)
    env.define("进程对象", DaoProcess)
    env.exports = list(env.values.keys())
    return env
