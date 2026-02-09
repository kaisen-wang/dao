"""
内置函数与核心类型
=================

"道"语言的内置函数和面向对象核心类型定义。

内置函数无需导入即可直接使用。
核心类型（DaoClass, DaoInstance 等）由解释器用于 OOP 支持。
"""

from .errors import 运行时错误, 类型错误, 名称错误


# ========================================================
# 可调用对象体系
# ========================================================

class DaoCallable:
    """可调用对象的基类"""

    def call(self, args: list, kwargs: dict) -> object:
        raise NotImplementedError

    def arity(self) -> int:
        """返回参数个数，-1 表示可变参数"""
        return -1


class BuiltinFunction(DaoCallable):
    """内置函数包装器（纯 Python 函数）"""

    def __init__(self, name: str, func, param_count: int = -1):
        self.name = name
        self.func = func
        self.param_count = param_count

    def call(self, args: list, kwargs: dict) -> object:
        return self.func(*args, **kwargs)

    def arity(self) -> int:
        return self.param_count

    def __repr__(self) -> str:
        return f"<内置函数 {self.name}>"


class InterpreterBuiltin(DaoCallable):
    """需要解释器引用的内置函数（用于高阶函数等）"""

    def __init__(self, name: str, func, param_count: int = -1):
        self.name = name
        self.func = func
        self.param_count = param_count
        self.interpreter = None  # 由 Interpreter.__init__ 设置

    def call(self, args: list, kwargs: dict) -> object:
        return self.func(self.interpreter, *args, **kwargs)

    def arity(self) -> int:
        return self.param_count

    def __repr__(self) -> str:
        return f"<内置函数 {self.name}>"


class DaoFunction(DaoCallable):
    """用户自定义函数"""

    def __init__(self, name: str, params: list[str], default_values: dict,
                 body: list, closure_env):
        self.name = name
        self.params = params
        self.default_values = default_values
        self.body = body
        self.closure_env = closure_env

    def arity(self) -> int:
        return len(self.params)

    def __repr__(self) -> str:
        return f"<函数 {self.name}>"


# ========================================================
# 面向对象核心类型
# ========================================================

class DaoClass(DaoCallable):
    """道语言类型 (class)"""

    def __init__(self, name: str, parent: "DaoClass | None",
                 methods: dict[str, DaoFunction]):
        self.name = name
        self.parent = parent
        self.methods = methods

    def find_method(self, name: str) -> DaoFunction | None:
        """查找方法（沿继承链向上搜索）"""
        if name in self.methods:
            return self.methods[name]
        if self.parent:
            return self.parent.find_method(name)
        return None

    def arity(self) -> int:
        init = self.find_method("初始化")
        return init.arity() if init else 0

    def call(self, args: list, kwargs: dict) -> object:
        raise NotImplementedError("类型实例化由解释器处理")

    def __repr__(self) -> str:
        return f"<类型 {self.name}>"


class DaoInstance:
    """道语言对象实例"""

    def __init__(self, klass: DaoClass):
        self.klass = klass
        self.fields: dict[str, object] = {}

    def get_field(self, name: str):
        """获取实例字段或绑定方法"""
        if name in self.fields:
            return self.fields[name]
        method = self.klass.find_method(name)
        if method is not None:
            return BoundMethod(self, method)
        return None

    def set_field(self, name: str, value: object):
        """设置实例字段"""
        self.fields[name] = value

    def __repr__(self) -> str:
        return f"<{self.klass.name} 实例>"

    def __eq__(self, other):
        if isinstance(other, DaoInstance):
            return self is other
        return NotImplemented

    def __hash__(self):
        return id(self)


class BoundMethod(DaoCallable):
    """绑定到实例的方法"""

    def __init__(self, instance: DaoInstance, method: DaoFunction):
        self.instance = instance
        self.method = method

    def arity(self) -> int:
        return self.method.arity()

    def call(self, args: list, kwargs: dict) -> object:
        raise NotImplementedError("绑定方法调用由解释器处理")

    def __repr__(self) -> str:
        return f"<方法 {self.instance.klass.name}.{self.method.name}>"


class SuperProxy:
    """父对象代理，用于通过父类调用方法"""

    def __init__(self, instance: DaoInstance, parent_class: DaoClass):
        self.instance = instance
        self.parent_class = parent_class


# ========================================================
# 内置函数实现 — 基础
# ========================================================

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
# 高阶内置函数（需要解释器引用）
# ========================================================

def _hof_映射(interpreter, collection, func):
    """映射：对每个元素应用函数，返回新列表"""
    return [interpreter.call_function(func, [item]) for item in collection]


def _hof_筛选(interpreter, collection, func):
    """筛选：保留满足条件的元素"""
    return [item for item in collection
            if interpreter._is_truthy(interpreter.call_function(func, [item]))]


def _hof_折叠(interpreter, collection, initial, func):
    """折叠：从初始值开始，逐个合并元素"""
    result = initial
    for item in collection:
        result = interpreter.call_function(func, [result, item])
    return result


def _hof_每个满足(interpreter, collection, func):
    """每个满足：所有元素是否都满足条件"""
    return all(
        interpreter._is_truthy(interpreter.call_function(func, [item]))
        for item in collection
    )


def _hof_存在满足(interpreter, collection, func):
    """存在满足：是否有元素满足条件"""
    return any(
        interpreter._is_truthy(interpreter.call_function(func, [item]))
        for item in collection
    )


def _hof_查找(interpreter, collection, func):
    """查找：找到第一个满足条件的元素"""
    for item in collection:
        if interpreter._is_truthy(interpreter.call_function(func, [item])):
            return item
    return None


def _hof_排序(interpreter, collection, 键=None, 降序=False):
    """排序：对集合排序"""
    if 键 is not None:
        return sorted(
            collection,
            key=lambda item: interpreter.call_function(键, [item]),
            reverse=bool(降序),
        )
    return sorted(collection, reverse=bool(降序))


def _hof_展平映射(interpreter, collection, func):
    """展平映射：映射后展平一层"""
    result = []
    for item in collection:
        mapped = interpreter.call_function(func, [item])
        if isinstance(mapped, list):
            result.extend(mapped)
        else:
            result.append(mapped)
    return result


def _hof_分组(interpreter, collection, func):
    """分组：按函数返回值分组"""
    groups = {}
    for item in collection:
        key = interpreter.call_function(func, [item])
        # 使字典键可哈希
        if isinstance(key, list):
            key = tuple(key)
        if key not in groups:
            groups[key] = []
        groups[key].append(item)
    return groups


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


def get_interpreter_builtins() -> dict[str, InterpreterBuiltin]:
    """返回所有需要解释器引用的高阶内置函数"""
    return {
        "映射": InterpreterBuiltin("映射", _hof_映射, 2),
        "筛选": InterpreterBuiltin("筛选", _hof_筛选, 2),
        "折叠": InterpreterBuiltin("折叠", _hof_折叠, 3),
        "每个满足": InterpreterBuiltin("每个满足", _hof_每个满足, 2),
        "存在满足": InterpreterBuiltin("存在满足", _hof_存在满足, 2),
        "查找": InterpreterBuiltin("查找", _hof_查找, 2),
        "排序": InterpreterBuiltin("排序", _hof_排序),
        "展平映射": InterpreterBuiltin("展平映射", _hof_展平映射, 2),
        "分组": InterpreterBuiltin("分组", _hof_分组, 2),
    }
