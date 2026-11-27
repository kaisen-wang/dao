"""
基础内置函数
===========

"道"语言的基础内置函数实现（无需解释器引用的纯函数）。
这些函数在解释器初始化时注册到全局环境中。
"""

import sys

from ..errors import 类型错误, 运行时错误
from .callables import BuiltinFunction, DaoCallable, DaoFunction, InterpreterBuiltin
from .oop_types import BoundMethod, DaoClass, DaoInstance


def _转输出文本(arg) -> str:
    """把一个值按道语言的中文显示规则转换为文本。"""
    if arg is None:
        return "空"
    if isinstance(arg, bool):
        return "真" if arg else "假"
    if isinstance(arg, (DaoInstance, DaoClass)):
        return repr(arg)
    return str(arg)


def _收集输出文本(args, sep) -> str:
    """用指定分隔符拼接多个值的中文文本表示。"""
    return sep.join(_转输出文本(arg) for arg in args)


def _builtin_打印(*args, **kwargs):
    """打印函数：输出内容到控制台

    命名参数：分隔符、结尾、刷新（为真时立即刷新输出缓冲区，用于流式输出）。
    """
    sep = kwargs.get("分隔符", " ")
    end = kwargs.get("结尾", "\n")
    flush = kwargs.get("刷新", False)
    print(_收集输出文本(args, sep), end=end, flush=bool(flush))
    return None


def _builtin_错误输出(*args, **kwargs):
    """错误输出函数：输出内容到标准错误流

    命名参数：分隔符、结尾、刷新，语义与 ``打印`` 一致。
    """
    sep = kwargs.get("分隔符", " ")
    end = kwargs.get("结尾", "\n")
    flush = kwargs.get("刷新", False)
    sys.stderr.write(_收集输出文本(args, sep) + str(end))
    if flush:
        sys.stderr.flush()


def _builtin_读字节(n):
    """读字节函数：从标准输入读取指定字节数并返回字节数据"""
    if isinstance(n, bool) or not isinstance(n, int):
        raise 类型错误(f"读字节() 的字节数必须是整数，收到: {type(n).__name__}")
    if n <= 0:
        raise 运行时错误("读字节() 的字节数必须为正整数")
    return sys.stdin.buffer.read(n)


def _builtin_字节长度(文本):
    """字节长度函数：返回文本的 UTF-8 编码字节数"""
    if not isinstance(文本, str):
        raise 类型错误(f"字节长度() 的参数必须是文本，收到: {type(文本).__name__}")
    return len(文本.encode("utf-8"))


def _builtin_诊断源码(源码字符串):
    """诊断源码函数：分析源码并返回词法与语法错误诊断列表"""
    # 延迟导入，避免与词法/语法分析器形成循环导入。
    from ..errors import 词法错误, 语法错误, 道错误
    from ..lexer import Lexer
    from ..parser import Parser

    if not isinstance(源码字符串, str):
        raise 类型错误(f"诊断源码() 的参数必须是文本，收到: {type(源码字符串).__name__}")

    def _转诊断(error):
        if isinstance(error, 词法错误):
            类型 = "词法错误"
        elif isinstance(error, 语法错误):
            类型 = "语法错误"
        else:
            类型 = type(error).__name__ or "编译错误"
        return {
            "行": max(1, int(error.line or 0)),
            "列": max(1, int(error.column or 0)),
            "类型": 类型,
            "消息": str(error.message),
        }

    try:
        tokens = Lexer(源码字符串).tokenize()
    except 道错误 as error:
        # 词法错误优先，命中一条即可返回，无需继续解析。
        return [_转诊断(error)]
    try:
        Parser(tokens, 源码字符串).parse()
    except 道错误 as error:
        return [_转诊断(error)]
    return []


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
    if len(args) == 1 and hasattr(args[0], "__iter__") and not isinstance(args[0], str):
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
    if len(args) == 1 and hasattr(args[0], "__iter__"):
        return max(args[0])
    return max(args)


def _builtin_最小值(*args):
    """求最小值"""
    if len(args) == 1 and hasattr(args[0], "__iter__"):
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


def _builtin_下一个(iterator):
    """获取迭代器的下一个值"""
    try:
        return next(iterator)
    except StopIteration:
        from ..errors import 运行时错误

        raise 运行时错误("迭代器已耗尽")


def _builtin_互斥锁():
    """创建互斥锁"""
    from ..concurrency import Mutex

    return Mutex()


def _builtin_原子整数(initial_value=0):
    """创建原子整数"""
    from ..concurrency import AtomicInt

    return AtomicInt(initial_value)


def _builtin_原子布尔(initial_value=False):
    """创建原子布尔"""
    from ..concurrency import AtomicBool

    return AtomicBool(initial_value)


def _builtin_开始事件循环():
    """开始事件循环"""
    import asyncio

    loop = asyncio.get_event_loop()
    return loop


def _builtin_运行异步(func):
    """运行异步函数"""
    import asyncio

    loop = asyncio.get_event_loop()

    # 使用完整的解释器实例，因为它继承了所有需要的功能
    from dao.interpreter.core import Interpreter

    interpreter = Interpreter()

    if func is None:
        return None
    elif hasattr(func, "is_async") and func.is_async:
        # 如果是 DaoAsyncFunction 类型
        coro = interpreter.eval_async_function_call(func, [], {})
        return loop.run_until_complete(coro)
    elif hasattr(func, "__call__"):
        # 如果是可调用对象，先调用获取 coroutine
        result = func()
        if hasattr(result, "__await__"):
            return loop.run_until_complete(result)
        return result
    elif hasattr(func, "__await__"):
        # 已经是 coroutine
        return loop.run_until_complete(func)
    else:
        raise 类型错误(f"运行异步期望接收异步函数或协程，但收到: {type(func).__name__}")


# ========================================================
# 注册表
# ========================================================


def _builtin_睡眠(秒数):
    """睡眠指定秒数"""
    import time

    time.sleep(秒数)


def _builtin_添加事实(kb, predicate, *args):
    """向知识库动态添加事实"""
    from ..logic.core import KnowledgeBase, LogicStruct, normalize_term

    if not isinstance(kb, KnowledgeBase):
        raise 类型错误("添加事实() 的第一个参数必须是知识库")
    normalized_args = [normalize_term(arg) for arg in args]
    fact = LogicStruct(predicate, normalized_args)
    kb.add_fact(fact)
    return None


def _builtin_删除事实(kb, predicate, *args):
    """从知识库动态删除事实"""
    from ..logic.core import KnowledgeBase, LogicStruct, normalize_term

    if not isinstance(kb, KnowledgeBase):
        raise 类型错误("删除事实() 的第一个参数必须是知识库")
    normalized_args = [normalize_term(arg) for arg in args]
    fact = LogicStruct(predicate, normalized_args)
    kb.remove_fact(fact)
    return None


def _builtin_时间戳():
    import time as _time
    return _time.perf_counter()


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
        "str": BuiltinFunction("str", _builtin_文本, 1),
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
        "下一个": BuiltinFunction("下一个", _builtin_下一个, 1),
        "互斥锁": BuiltinFunction("互斥锁", _builtin_互斥锁, 0),
        "原子整数": BuiltinFunction("原子整数", _builtin_原子整数, 1),
        "原子布尔": BuiltinFunction("原子布尔", _builtin_原子布尔, 1),
        "开始事件循环": BuiltinFunction("开始事件循环", _builtin_开始事件循环, 0),
        "运行异步": BuiltinFunction("运行异步", _builtin_运行异步, 1),
        "睡眠": BuiltinFunction("睡眠", _builtin_睡眠, 1),
        "添加事实": BuiltinFunction("添加事实", _builtin_添加事实),
        "删除事实": BuiltinFunction("删除事实", _builtin_删除事实),
        "时间戳": BuiltinFunction("时间戳", _builtin_时间戳, 0),
        "读字节": BuiltinFunction("读字节", _builtin_读字节, 1),
        "字节长度": BuiltinFunction("字节长度", _builtin_字节长度, 1),
        "错误输出": BuiltinFunction("错误输出", _builtin_错误输出),
        "诊断源码": BuiltinFunction("诊断源码", _builtin_诊断源码, 1),
    }


# ========================================================
# Python 互操作桥（追加，不改动上方既有函数）
# ========================================================

# 延迟导入，避免内置函数模块与互操作包形成循环依赖。
from ..interop import bridge as _互操作桥  # noqa: E402


def _builtin_列出Python模块():
    """列出所有可通过互操作桥加载的白名单 Python 模块名称。"""
    return _互操作桥.列出可用模块()


def _builtin_载入Python模块(模块名):
    """载入白名单内的 Python 模块，返回供 调用Python函数() 使用的不透明句柄。"""
    return _互操作桥.载入模块(模块名)


def _builtin_调用Python函数(模块句柄, 函数名, *参数, **命名参数):
    """通过模块句柄调用白名单允许的 Python 函数，或读取白名单常量。"""
    return _互操作桥.调用模块函数(模块句柄, 函数名, *参数, **命名参数)


# 以包装方式扩展注册表，保持上方 get_builtins 原样不动。
_原_get_builtins = get_builtins


def get_builtins() -> dict[str, BuiltinFunction]:
    """返回所有基础内置函数（含 Python 互操作桥）。"""
    内置表 = _原_get_builtins()
    内置表.update(
        {
            "列出Python模块": BuiltinFunction("列出Python模块", _builtin_列出Python模块, 0),
            "载入Python模块": BuiltinFunction("载入Python模块", _builtin_载入Python模块, 1),
            "调用Python函数": BuiltinFunction("调用Python函数", _builtin_调用Python函数),
        }
    )
    return 内置表


# ========================================================
# 逻辑编程集成（追加，不改动上方既有函数）
# ========================================================


def _builtin_逻辑查询(知识库, 目标, **命名参数):
    """便捷逻辑查询：支持嵌套结构、合取/析取、排序分页的字符串查询。

    返回字典列表（键为 ``"?变量"``）；命名参数 ``结果对象`` 为真时返回
    ``QueryResult`` 列表。
    """
    from ..logic.core import KnowledgeBase
    from ..logic.solver import query as _query

    if not isinstance(知识库, KnowledgeBase):
        raise 类型错误("逻辑查询() 的第一个参数必须是知识库")
    if not isinstance(目标, str):
        raise 类型错误("逻辑查询() 的查询目标必须是文本")

    支持参数 = {
        "变量": "variables",
        "排序": "排序",
        "降序": "降序",
        "偏移": "偏移",
        "限制": "限制",
        "结果对象": "结果对象",
        "sort_by": "sort_by",
        "descending": "descending",
        "offset": "offset",
        "limit": "limit",
    }
    参数 = {}
    for 键, 值 in 命名参数.items():
        if 键 not in 支持参数:
            raise 类型错误(f"逻辑查询() 不支持命名参数 '{键}'")
        参数[支持参数[键]] = 值
    return _query(知识库, 目标, **参数)


def _builtin_格式化结果(结果, 格式="表格"):
    """把逻辑查询结果格式化为中文可读文本（表格 / 简洁）。"""
    from ..logic.result_utils import 格式化结果 as _格式化结果

    return _格式化结果(结果, 格式)


def _builtin_结果转列表(结果, 含变量名=True):
    """把查询结果导出为道语言二维列表。"""
    from ..logic.result_utils import 结果转列表 as _结果转列表

    return _结果转列表(结果, 含变量名=bool(含变量名))


def _builtin_结果转字典(结果):
    """把查询结果导出为道语言列表/字典。"""
    from ..logic.result_utils import 结果转字典 as _结果转字典

    return _结果转字典(结果)


def _builtin_逻辑变量(名字):
    """把文本（``x`` 或 ``?x``）转换为逻辑变量，实现逻辑变量与道语言变量互操作。"""
    from ..logic.core import LogicVariable

    if isinstance(名字, LogicVariable):
        return 名字
    if not isinstance(名字, str) or not 名字:
        raise 类型错误("逻辑变量() 的参数必须是非空文本")
    return LogicVariable(名字 if 名字.startswith("?") else "?" + 名字)


def _builtin_转逻辑项(值):
    """把道语言值（文本/数值/布尔/列表/字典）转换为逻辑项。"""
    from ..logic.core import normalize_term

    if isinstance(值, (list, tuple)):
        return tuple(normalize_term(元素) for 元素 in 值)
    return normalize_term(值)


def _builtin_取绑定(结果, 变量名):
    """从单个查询结果的指定绑定变量读取值（兼容有/无 ``?`` 前缀）。"""
    from ..logic.core import LogicVariable

    if isinstance(变量名, LogicVariable):
        变量名 = 变量名.name
    if not isinstance(变量名, str) or not 变量名:
        raise 类型错误("取绑定() 的变量名必须是非空文本")
    规范名 = 变量名 if 变量名.startswith("?") else "?" + 变量名

    if hasattr(结果, "get_binding") and callable(结果.get_binding):
        return 结果.get_binding(规范名)
    if isinstance(结果, dict):
        if 规范名 in 结果:
            return 结果[规范名]
        return 结果.get(变量名)
    raise 类型错误("取绑定() 的结果必须是逻辑查询结果或字典")


# 以包装方式再次扩展注册表，保持上方既有函数原样不动。
_原_get_builtins_含互操作 = get_builtins


def get_builtins() -> dict[str, BuiltinFunction]:
    """返回所有基础内置函数（含逻辑编程集成）。"""
    内置表 = _原_get_builtins_含互操作()
    内置表.update(
        {
            "逻辑查询": BuiltinFunction("逻辑查询", _builtin_逻辑查询),
            "格式化结果": BuiltinFunction("格式化结果", _builtin_格式化结果),
            "结果转列表": BuiltinFunction("结果转列表", _builtin_结果转列表),
            "结果转字典": BuiltinFunction("结果转字典", _builtin_结果转字典),
            "逻辑变量": BuiltinFunction("逻辑变量", _builtin_逻辑变量, 1),
            "转逻辑项": BuiltinFunction("转逻辑项", _builtin_转逻辑项, 1),
            "取绑定": BuiltinFunction("取绑定", _builtin_取绑定, 2),
        }
    )
    return 内置表
    return 内置表
