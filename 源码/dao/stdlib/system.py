import os
import subprocess
import sys

from ..builtins.callables import BuiltinFunction
from ..builtins.functions import get_builtins
from ..builtins.hof import get_interpreter_builtins
from ..environment import Environment
from ..errors import 类型错误, 运行时错误
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


def _选项定义列表(选项定义):
    """把选项定义归一化为字典规格列表。

    接受「规格字典列表」或「名称 -> 规格」字典两种写法。
    """
    if 选项定义 is None:
        return []
    if isinstance(选项定义, dict):
        结果 = []
        for 名称, 定义 in 选项定义.items():
            if not isinstance(名称, str) or not 名称:
                raise 运行时错误("选项名称必须是非空文本")
            if isinstance(定义, dict):
                项 = dict(定义)
                项.setdefault("名称", 名称)
            elif isinstance(定义, str):
                项 = {"名称": 名称, "长": 名称, "类型": 定义}
            else:
                项 = {"名称": 名称, "长": 名称}
            结果.append(项)
        return 结果
    if isinstance(选项定义, (list, tuple)):
        return [dict(项) if isinstance(项, dict) else {"名称": str(项), "长": str(项)} for 项 in 选项定义]
    raise 类型错误("选项定义必须是列表或字典")


def _选项索引(规格):
    """构建短选项与长选项的查找表，并校验定义完整性。"""
    短映射 = {}
    长映射 = {}
    for 项 in 规格:
        名称 = 项.get("名称")
        if not isinstance(名称, str) or not 名称:
            raise 运行时错误("选项定义缺少合法的名称")
        短 = 项.get("短")
        长 = 项.get("长")
        if not 短 and not 长:
            raise 运行时错误(f"选项 {名称} 至少需要一个短选项或长选项")
        if 短 is not None:
            if not isinstance(短, str) or len(短) != 1:
                raise 运行时错误(f"选项 {名称} 的短选项必须是一个字符")
            if 短 in 短映射:
                raise 运行时错误(f"短选项冲突: -{短}")
            短映射[短] = 项
        if 长 is not None:
            if not isinstance(长, str) or not 长:
                raise 运行时错误(f"选项 {名称} 的长选项必须是非空文本")
            if 长 in 长映射:
                raise 运行时错误(f"长选项冲突: --{长}")
            长映射[长] = 项
    return 短映射, 长映射


def _转换选项值(值, 类型, 选项名):
    """按选项声明的类型把文本转换为整数、浮点、开关或保持文本。"""
    if 类型 in (None, "", "文本", "字符串"):
        return 值
    if 类型 == "整数":
        try:
            return int(值)
        except (TypeError, ValueError):
            raise 运行时错误(f"选项 {选项名} 需要整数值")
    if 类型 == "浮点":
        try:
            return float(值)
        except (TypeError, ValueError):
            raise 运行时错误(f"选项 {选项名} 需要浮点数值")
    if 类型 == "开关":
        if isinstance(值, bool):
            return 值
        真值 = ("true", "1", "yes", "on", "真")
        假值 = ("false", "0", "no", "off", "假")
        文本 = str(值).strip().lower()
        if 文本 in 真值:
            return True
        if 文本 in 假值:
            return False
        raise 运行时错误(f"选项 {选项名} 需要布尔值")
    raise 运行时错误(f"选项 {选项名} 使用了不支持的类型: {类型}")


def _stdlib_解析参数(参数列表=None, 选项定义=None, 描述=""):
    """解析命令行参数，返回含位置参数、选项与帮助标记的结果字典。

    支持 ``-o 值`` / ``--output 值`` / ``--output=值`` 以及开关选项；
    遇到 ``-h`` 或 ``--help`` 时立即返回帮助标记。未知选项、缺少取值
    与类型转换失败都会抛出运行时错误。
    """
    if 参数列表 is None:
        参数列表 = sys.argv[1:]
    if not isinstance(参数列表, (list, tuple)):
        raise 类型错误("参数列表必须是文本列表")
    if not all(isinstance(项, str) for 项 in 参数列表):
        raise 类型错误("参数列表必须是文本列表")
    if not isinstance(描述, str):
        raise 类型错误("描述必须是文本")
    规格 = _选项定义列表(选项定义)
    短映射, 长映射 = _选项索引(规格)
    参数列表 = list(参数列表)

    if any(项 in ("-h", "--help") for 项 in 参数列表):
        return {"帮助": True, "位置参数": [], "选项": {}}

    选项结果 = {}
    for 项 in 规格:
        if "默认" in 项:
            选项结果[项["名称"]] = 项["默认"]
        elif 项.get("类型") == "开关":
            选项结果[项["名称"]] = False

    位置参数 = []
    索引 = 0
    仅位置 = False
    while 索引 < len(参数列表):
        当前 = 参数列表[索引]
        索引 += 1
        if 仅位置:
            位置参数.append(当前)
            continue
        if 当前 == "--":
            仅位置 = True
            continue
        if 当前.startswith("--"):
            主体 = 当前[2:]
            if not 主体:
                位置参数.append(当前)
                continue
            if "=" in 主体:
                名称, 取值 = 主体.split("=", 1)
                显式取值 = True
            else:
                名称, 取值, 显式取值 = 主体, None, False
            项 = 长映射.get(名称)
            if 项 is None:
                raise 运行时错误(f"未知的长选项: --{名称}")
            if 项.get("类型") == "开关":
                选项结果[项["名称"]] = _转换选项值(True if not 显式取值 else 取值, "开关", 名称)
                continue
            if not 显式取值:
                if 索引 >= len(参数列表):
                    raise 运行时错误(f"选项 --{名称} 缺少取值")
                取值 = 参数列表[索引]
                索引 += 1
            选项结果[项["名称"]] = _转换选项值(取值, 项.get("类型"), 名称)
            continue
        if 当前.startswith("-") and len(当前) > 1:
            主体 = 当前[1:]
            短名 = 主体[0]
            项 = 短映射.get(短名)
            if 项 is None:
                raise 运行时错误(f"未知的短选项: -{短名}")
            if 项.get("类型") == "开关":
                选项结果[项["名称"]] = True
                continue
            剩余 = 主体[1:]
            if 剩余.startswith("="):
                剩余 = 剩余[1:]
            if 剩余:
                取值 = 剩余
            else:
                if 索引 >= len(参数列表):
                    raise 运行时错误(f"选项 -{短名} 缺少取值")
                取值 = 参数列表[索引]
                索引 += 1
            选项结果[项["名称"]] = _转换选项值(取值, 项.get("类型"), 项["名称"])
            continue
        位置参数.append(当前)

    for 项 in 规格:
        if 项.get("必填") and 项["名称"] not in 选项结果:
            raise 运行时错误(f"缺少必填选项: {项['名称']}")
    return {"帮助": False, "位置参数": 位置参数, "选项": 选项结果}


def _stdlib_生成帮助文本(程序名="程序", 选项定义=None, 描述=""):
    """生成包含用法、选项说明与默认值的帮助文本。"""
    if not isinstance(程序名, str) or not 程序名:
        raise 类型错误("程序名必须是非空文本")
    if not isinstance(描述, str):
        raise 类型错误("描述必须是文本")
    规格 = _选项定义列表(选项定义)
    _选项索引(规格)
    行 = [f"用法: {程序名} [选项] [参数]"]
    if 描述:
        行 += ["", 描述]
    if 规格:
        行 += ["", "选项:"]
        for 项 in 规格:
            标志 = []
            if 项.get("短"):
                标志.append(f"-{项['短']}")
            if 项.get("长"):
                标志.append(f"--{项['长']}")
            类型 = 项.get("类型", "文本")
            if 类型 and 类型 != "开关":
                标志.append(f"<{类型}>")
            说明 = 项.get("说明", "")
            if not isinstance(说明, str):
                raise 类型错误(f"选项 {项['名称']} 的说明必须是文本")
            行.append(f"  {', '.join(标志)}  {说明}".rstrip())
            if "默认" in 项:
                行.append(f"    （默认: {项['默认']}）")
    行 += ["", "  -h, --help  显示帮助信息"]
    return "\n".join(行)


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
    env.define("解析参数", BuiltinFunction("解析参数", _stdlib_解析参数, -1))
    env.define("生成帮助文本", BuiltinFunction("生成帮助文本", _stdlib_生成帮助文本, -1))
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
