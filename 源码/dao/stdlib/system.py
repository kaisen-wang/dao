import os
import subprocess
import sys

from ..builtins.callables import BuiltinFunction
from ..builtins.functions import get_builtins
from ..builtins.hof import get_interpreter_builtins
from ..environment import Environment
from ..errors import 运行时错误
from ..tokens import KEYWORDS
from .registry import STDLIB_REGISTRY


def _stdlib_取环境变量(名称, 默认值=None):
    """读取指定名称的环境变量，可提供默认值。

    参数：未提供默认值且变量不存在时抛出运行时错误。
    """
    if 默认值 is not None:
        return os.environ.get(名称, 默认值)
    value = os.environ.get(名称)
    if value is None:
        raise 运行时错误(f"环境变量 '{名称}' 不存在")
    return value


def _stdlib_设环境变量(名称, 值):
    """设置指定名称的环境变量值。"""
    os.environ[名称] = 值


def _stdlib_命令行参数():
    """返回当前进程的命令行参数列表。"""
    return sys.argv.copy()


def _stdlib_执行命令(命令):
    """执行系统命令并返回标准输出文本。"""
    try:
        result = subprocess.run(
            命令,
            shell=True,
            capture_output=True,
            text=True,
            timeout=60,
        )
        if result.returncode != 0:
            raise 运行时错误(f"命令执行失败，退出码: {result.returncode}\n{result.stderr}")
        return result.stdout
    except subprocess.TimeoutExpired:
        raise 运行时错误("命令执行超时")
    except FileNotFoundError:
        raise 运行时错误(f"找不到命令: {命令}")


def _stdlib_当前目录():
    """返回当前工作目录路径。"""
    return os.getcwd()


def _stdlib_切换目录(路径):
    """把当前工作目录切换到指定路径。"""
    if not os.path.isdir(路径):
        raise 运行时错误(f"目录不存在: {路径}")
    os.chdir(路径)


def _stdlib_退出(退出码=0):
    """以指定退出码结束当前进程。"""
    sys.exit(退出码)


def _stdlib_关键字表():
    """关键字表：返回道语言全部保留关键字的名称列表。"""
    return list(KEYWORDS)


def _stdlib_内置函数名():
    """内置函数名：返回全局内置函数与高阶内置函数的名称列表。"""
    return list(get_builtins()) + list(get_interpreter_builtins())


def _stdlib_标准库模块名():
    """标准库模块名：返回已注册的全部标准库模块名称列表。"""
    return list(STDLIB_REGISTRY.keys())


def create_module_env(interpreter=None) -> Environment:
    """创建系统模块的导出环境。"""
    env = Environment()
    env.define("取环境变量", BuiltinFunction("取环境变量", _stdlib_取环境变量, -1))
    env.define("设环境变量", BuiltinFunction("设环境变量", _stdlib_设环境变量, 2))
    env.define("命令行参数", BuiltinFunction("命令行参数", _stdlib_命令行参数, 0))
    env.define("执行命令", BuiltinFunction("执行命令", _stdlib_执行命令, 1))
    env.define("当前目录", BuiltinFunction("当前目录", _stdlib_当前目录, 0))
    env.define("切换目录", BuiltinFunction("切换目录", _stdlib_切换目录, 1))
    env.define("退出", BuiltinFunction("退出", _stdlib_退出, -1))
    env.define("平台", sys.platform)
    env.define("关键字表", BuiltinFunction("关键字表", _stdlib_关键字表, 0))
    env.define("内置函数名", BuiltinFunction("内置函数名", _stdlib_内置函数名, 0))
    env.define("标准库模块名", BuiltinFunction("标准库模块名", _stdlib_标准库模块名, 0))
    env.exports = list(env.values.keys())
    return env
