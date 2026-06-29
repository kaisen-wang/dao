import math
import random
import statistics

from ..builtins.callables import BuiltinFunction
from ..environment import Environment
from ..errors import 运行时错误


def _stdlib_正弦(x):
    return math.sin(x)


def _stdlib_余弦(x):
    return math.cos(x)


def _stdlib_正切(x):
    return math.tan(x)


def _stdlib_反正弦(x):
    try:
        return math.asin(x)
    except ValueError:
        raise 运行时错误("数学函数参数超出定义域")


def _stdlib_反余弦(x):
    try:
        return math.acos(x)
    except ValueError:
        raise 运行时错误("数学函数参数超出定义域")


def _stdlib_反正切(x):
    return math.atan(x)


def _stdlib_随机整数(最小, 最大):
    if 最小 > 最大:
        raise 运行时错误("随机整数的最小值不得大于最大值")
    return random.randint(最小, 最大)


def _stdlib_随机小数():
    return random.random()


def _stdlib_随机选择(列表):
    if not isinstance(列表, list) or len(列表) == 0:
        raise 运行时错误("随机选择需要非空列表")
    return random.choice(列表)


def _stdlib_打乱(列表):
    if not isinstance(列表, list):
        raise 运行时错误("打乱需要列表类型参数")
    result = 列表.copy()
    random.shuffle(result)
    return result


def _stdlib_平均值(列表):
    if not isinstance(列表, list) or len(列表) == 0:
        raise 运行时错误("无法对空列表计算平均值")
    return sum(列表) / len(列表)


def _stdlib_中位数(列表):
    if not isinstance(列表, list) or len(列表) == 0:
        raise 运行时错误("无法对空列表计算中位数")
    return statistics.median(列表)


def _stdlib_标准差(列表):
    if not isinstance(列表, list) or len(列表) < 2:
        raise 运行时错误("标准差至少需要2个数据点")
    return statistics.stdev(列表)


def _stdlib_向上取整(x):
    return math.ceil(x)


def _stdlib_向下取整(x):
    return math.floor(x)


def _stdlib_四舍五入(x):
    return round(x)


def _stdlib_幂(底, 指):
    return math.pow(底, 指)


def _stdlib_自然对数(x):
    try:
        return math.log(x)
    except ValueError:
        raise 运行时错误("自然对数的参数必须为正数")


def _stdlib_对数(x, 底):
    try:
        return math.log(x, 底)
    except ValueError:
        raise 运行时错误("对数的参数无效")


def create_module_env(interpreter=None) -> Environment:
    env = Environment()
    env.define("正弦", BuiltinFunction("正弦", _stdlib_正弦, 1))
    env.define("余弦", BuiltinFunction("余弦", _stdlib_余弦, 1))
    env.define("正切", BuiltinFunction("正切", _stdlib_正切, 1))
    env.define("反正弦", BuiltinFunction("反正弦", _stdlib_反正弦, 1))
    env.define("反余弦", BuiltinFunction("反余弦", _stdlib_反余弦, 1))
    env.define("反正切", BuiltinFunction("反正切", _stdlib_反正切, 1))
    env.define("随机整数", BuiltinFunction("随机整数", _stdlib_随机整数, 2))
    env.define("随机小数", BuiltinFunction("随机小数", _stdlib_随机小数, 0))
    env.define("随机选择", BuiltinFunction("随机选择", _stdlib_随机选择, 1))
    env.define("打乱", BuiltinFunction("打乱", _stdlib_打乱, 1))
    env.define("平均值", BuiltinFunction("平均值", _stdlib_平均值, 1))
    env.define("中位数", BuiltinFunction("中位数", _stdlib_中位数, 1))
    env.define("标准差", BuiltinFunction("标准差", _stdlib_标准差, 1))
    env.define("向上取整", BuiltinFunction("向上取整", _stdlib_向上取整, 1))
    env.define("向下取整", BuiltinFunction("向下取整", _stdlib_向下取整, 1))
    env.define("四舍五入", BuiltinFunction("四舍五入", _stdlib_四舍五入, 1))
    env.define("幂", BuiltinFunction("幂", _stdlib_幂, 2))
    env.define("自然对数", BuiltinFunction("自然对数", _stdlib_自然对数, 1))
    env.define("对数", BuiltinFunction("对数", _stdlib_对数, 2))
    env.define("圆周率", math.pi)
    env.define("自然常数", math.e)
    env.exports = list(env.values.keys())
    return env