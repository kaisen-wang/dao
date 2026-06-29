import os
import subprocess
import sys

from ..builtins.callables import BuiltinFunction
from ..environment import Environment
from ..errors import 运行时错误


def _stdlib_取环境变量(名称, 默认值=None):
    if 默认值 is not None:
        return os.environ.get(名称, 默认值)
    value = os.environ.get(名称)
    if value is None:
        raise 运行时错误(f"环境变量 '{名称}' 不存在")
    return value


def _stdlib_设环境变量(名称, 值):
    os.environ[名称] = 值


def _stdlib_命令行参数():
    return sys.argv.copy()


def _stdlib_执行命令(命令):
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
    return os.getcwd()


def _stdlib_切换目录(路径):
    if not os.path.isdir(路径):
        raise 运行时错误(f"目录不存在: {路径}")
    os.chdir(路径)


def _stdlib_退出(退出码=0):
    sys.exit(退出码)


def create_module_env(interpreter=None) -> Environment:
    env = Environment()
    env.define("取环境变量", BuiltinFunction("取环境变量", _stdlib_取环境变量, -1))
    env.define("设环境变量", BuiltinFunction("设环境变量", _stdlib_设环境变量, 2))
    env.define("命令行参数", BuiltinFunction("命令行参数", _stdlib_命令行参数, 0))
    env.define("执行命令", BuiltinFunction("执行命令", _stdlib_执行命令, 1))
    env.define("当前目录", BuiltinFunction("当前目录", _stdlib_当前目录, 0))
    env.define("切换目录", BuiltinFunction("切换目录", _stdlib_切换目录, 1))
    env.define("退出", BuiltinFunction("退出", _stdlib_退出, -1))
    env.define("平台", sys.platform)
    env.exports = list(env.values.keys())
    return env