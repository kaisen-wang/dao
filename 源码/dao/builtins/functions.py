"""
基础内置函数
===========

"道"语言的基础内置函数实现（无需解释器引用的纯函数）。
这些函数在解释器初始化时注册到全局环境中。
"""

from ..errors import 运行时错误, 类型错误
from .callables import BuiltinFunction, InterpreterBuiltin, DaoFunction
from .oop_types import DaoClass, DaoInstance, BoundMethod


def _builtin_打印(*args, **kwargs):
    """打印函数：输出内容到控制台"""
    sep = kwargs.get("分隔符", " ")
    end = kwargs.get("结尾", "\n")
    output_parts = []
    for arg in args:
        if arg is None:
            output_parts.append("空")
        elif isinstance(arg, bool):
            output_parts.append("真" if arg else "假")
        elif isinstance(arg, DaoInstance):
            output_parts.append(repr(arg))
        elif isinstance(arg, DaoClass):
            output_parts.append(repr(arg))
        else:
            output_parts.append(str(arg))
    print(sep.join(output_parts), end=end)
    return None


def _builtin_输入(prompt=""):
    """输入函数：从控制台读取用户输入"""
    return input(str(prompt))


def _builtin_长度(obj):
    """长度函数：获取集合或字符串的长度"""
    if isinstance(obj, (str, list, dict, tuple, set)):
        return len(obj)
    raise 类型错误(f"类型 '{type(obj).__name__}' 不支持求长度操作")


def _builtin_取类型(obj):
    """取类型函数：获取值的类型名称"""
    if isinstance(obj, DaoInstance):
        return obj.klass.name
    if isinstance(obj, DaoClass):
        return "类型"
    if isinstance(obj, (BuiltinFunction, InterpreterBuiltin, DaoFunction, BoundMethod)):
        return "函数"
    type_map = {
        int: "数值",
        float: "数值",
        str: "文本",
        bool: "布尔",
        list: "列表",
        dict: "字典",
        tuple: "元组",
        set: "集合",
        type(None): "空",
    }
    return type_map.get(type(obj), type(obj).__name__)


def _builtin_范围(*args):
    """范围函数：生成整数范围列表"""
    if len(args) == 1:
        return list(range(int(args[0])))
    elif len(args) == 2:
        return list(range(int(args[0]), int(args[1]) + 1))
    elif len(args) == 3:
        return list(range(int(args[0]), int(args[1]) + 1, int(args[2])))
    raise 运行时错误("范围() 需要 1 到 3 个参数")


def _builtin_整数(value):
    """整数转换"""
    try:
        return int(value)
    except (ValueError, TypeError):
        raise 类型错误(f"无法将 '{value}' 转换为整数")


def _builtin_小数(value):
    """浮点数转换"""
    try:
        return float(value)
    except (ValueError, TypeError):
        raise 类型错误(f"无法将 '{value}' 转换为小数")


def _builtin_文本(value):
    """字符串转换"""
    if value is None:
        return "空"
    if isinstance(value, bool):
        return "真" if value else "假"
    return str(value)


def _builtin_交集(set_a, set_b):
    """集合交集"""
    a = set(set_a) if not isinstance(set_a, set) else set_a
    b = set(set_b) if not isinstance(set_b, set) else set_b
    return a & b


def _builtin_并集(set_a, set_b):
    """集合并集"""
    a = set(set_a) if not isinstance(set_a, set) else set_a
    b = set(set_b) if not isinstance(set_b, set) else set_b
    return a | b


def _builtin_集合(*args):
    """创建集合"""
    if len(args) == 0:
        return set()
    if len(args) == 1 and hasattr(args[0], '__iter__') and not isinstance(args[0], str):
        return set(args[0])
    return set(args)


def _builtin_追加(lst, item):
    """向列表末尾追加元素"""
    if not isinstance(lst, list):
        raise 类型错误("追加() 的第一个参数必须是列表")
    lst.append(item)
    return lst


def _builtin_反转(obj):
    """反转列表或字符串"""
    if isinstance(obj, list):
        return list(reversed(obj))
    if isinstance(obj, str):
        return obj[::-1]
    raise 类型错误(f"类型 '{type(obj).__name__}' 不支持反转")


def _builtin_包含(collection, item):
    """检查集合是否包含元素"""
    return item in collection


def _builtin_最大值(*args):
    """求最大值"""
    if len(args) == 1 and hasattr(args[0], '__iter__'):
        return max(args[0])
    return max(args)


def _builtin_最小值(*args):
    """求最小值"""
    if len(args) == 1 and hasattr(args[0], '__iter__'):
        return min(args[0])
    return min(args)


def _builtin_绝对值(x):
    """绝对值"""
    return abs(x)


def _builtin_是实例(obj, cls):
    """检查对象是否是某个类型的实例"""
    if not isinstance(cls, DaoClass):
        raise 类型错误("是实例() 第二个参数必须是类型")
    klass = obj.klass if isinstance(obj, DaoInstance) else None
    while klass:
        if klass is cls:
            return True
        klass = klass.parent
    return False


# ========================================================
# 注册表
# ========================================================

def get_builtins() -> dict[str, BuiltinFunction]:
    """返回所有基础内置函数"""
    return {
        "打印": BuiltinFunction("打印", _builtin_打印),
        "输入": BuiltinFunction("输入", _builtin_输入, 1),
        "长度": BuiltinFunction("长度", _builtin_长度, 1),
        "取类型": BuiltinFunction("取类型", _builtin_取类型, 1),
        "范围": BuiltinFunction("范围", _builtin_范围),
        "整数": BuiltinFunction("整数", _builtin_整数, 1),
        "小数": BuiltinFunction("小数", _builtin_小数, 1),
        "文本": BuiltinFunction("文本", _builtin_文本, 1),
        "交集": BuiltinFunction("交集", _builtin_交集, 2),
        "并集": BuiltinFunction("并集", _builtin_并集, 2),
        "集合": BuiltinFunction("集合", _builtin_集合),
        "追加": BuiltinFunction("追加", _builtin_追加, 2),
        "反转": BuiltinFunction("反转", _builtin_反转, 1),
        "包含": BuiltinFunction("包含", _builtin_包含, 2),
        "最大值": BuiltinFunction("最大值", _builtin_最大值),
        "最小值": BuiltinFunction("最小值", _builtin_最小值),
        "绝对值": BuiltinFunction("绝对值", _builtin_绝对值, 1),
        "是实例": BuiltinFunction("是实例", _builtin_是实例, 2),
    }
