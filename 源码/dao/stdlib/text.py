import re

from ..builtins.callables import BuiltinFunction
from ..environment import Environment
from ..errors import 类型错误, 运行时错误

_regex_cache: dict[str, re.Pattern] = {}


def _get_compiled_pattern(pattern: str) -> re.Pattern:
    if pattern not in _regex_cache:
        try:
            _regex_cache[pattern] = re.compile(pattern)
        except re.error as e:
            raise 运行时错误(f"正则表达式语法无效: {e}")
    return _regex_cache[pattern]


def _stdlib_分割(文本, 分隔符):
    if not isinstance(文本, str):
        raise 类型错误(f"期望文本类型参数，但收到{type(文本).__name__}")
    if not isinstance(分隔符, str):
        raise 类型错误("分隔符必须是文本类型")
    if 分隔符 == "":
        raise 类型错误("分隔符不能为空字符串")
    return 文本.split(分隔符)


def _stdlib_连接(列表, 连接符):
    if not isinstance(列表, list):
        raise 类型错误(f"期望列表类型参数，但收到{type(列表).__name__}")
    if not isinstance(连接符, str):
        raise 类型错误("连接符必须是文本类型")
    return 连接符.join(str(item) for item in 列表)


def _stdlib_替换(文本, 旧串, 新串, 次数=-1):
    if not isinstance(文本, str):
        raise 类型错误(f"期望文本类型参数，但收到{type(文本).__name__}")
    if 次数 < 0:
        return 文本.replace(旧串, 新串)
    return 文本.replace(旧串, 新串, 次数)


def _stdlib_包含(文本, 子串):
    if not isinstance(文本, str):
        raise 类型错误(f"期望文本类型参数，但收到{type(文本).__name__}")
    return 子串 in 文本


def _stdlib_去空格(文本):
    if not isinstance(文本, str):
        raise 类型错误(f"期望文本类型参数，但收到{type(文本).__name__}")
    return 文本.strip()


def _stdlib_查找(文本, 子串):
    if not isinstance(文本, str):
        raise 类型错误(f"期望文本类型参数，但收到{type(文本).__name__}")
    return 文本.find(子串)


def _stdlib_截取(文本, 开始, 结束=None):
    if not isinstance(文本, str):
        raise 类型错误(f"期望文本类型参数，但收到{type(文本).__name__}")
    if 结束 is None:
        return 文本[开始:]
    return 文本[开始:结束]


def _stdlib_大写(文本):
    if not isinstance(文本, str):
        raise 类型错误(f"期望文本类型参数，但收到{type(文本).__name__}")
    return 文本.upper()


def _stdlib_小写(文本):
    if not isinstance(文本, str):
        raise 类型错误(f"期望文本类型参数，但收到{type(文本).__name__}")
    return 文本.lower()


def _stdlib_正则匹配(文本, 模式):
    if not isinstance(文本, str):
        raise 类型错误(f"期望文本类型参数，但收到{type(文本).__name__}")
    compiled = _get_compiled_pattern(模式)
    return compiled.findall(文本)


def _stdlib_分割全部(文本, 模式):
    if not isinstance(文本, str):
        raise 类型错误(f"期望文本类型参数，但收到{type(文本).__name__}")
    compiled = _get_compiled_pattern(模式)
    return compiled.split(文本)


def _stdlib_替换全部(文本, 模式, 替换):
    if not isinstance(文本, str):
        raise 类型错误(f"期望文本类型参数，但收到{type(文本).__name__}")
    compiled = _get_compiled_pattern(模式)
    return compiled.sub(替换, 文本)


def create_module_env(interpreter=None) -> Environment:
    env = Environment()
    env.define("分割", BuiltinFunction("分割", _stdlib_分割, 2))
    env.define("连接", BuiltinFunction("连接", _stdlib_连接, 2))
    env.define("替换", BuiltinFunction("替换", _stdlib_替换, -1))
    env.define("包含", BuiltinFunction("包含", _stdlib_包含, 2))
    env.define("去空格", BuiltinFunction("去空格", _stdlib_去空格, 1))
    env.define("查找", BuiltinFunction("查找", _stdlib_查找, 2))
    env.define("截取", BuiltinFunction("截取", _stdlib_截取, -1))
    env.define("大写", BuiltinFunction("大写", _stdlib_大写, 1))
    env.define("小写", BuiltinFunction("小写", _stdlib_小写, 1))
    env.define("正则匹配", BuiltinFunction("正则匹配", _stdlib_正则匹配, 2))
    env.define("分割全部", BuiltinFunction("分割全部", _stdlib_分割全部, 2))
    env.define("替换全部", BuiltinFunction("替换全部", _stdlib_替换全部, 3))
    env.exports = list(env.values.keys())
    return env