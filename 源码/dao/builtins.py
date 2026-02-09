"""
内置函数
=======

"道"语言的内置函数实现。这些函数无需导入即可直接使用。

第一阶段提供的内置函数：
- 打印(...) : 输出内容到控制台
- 输入(提示) : 从控制台读取用户输入
- 长度(集合) : 获取集合或字符串的长度
- 类型(值)   : 获取值的类型名称
- 范围(起始, 结束, 步长) : 生成整数范围列表
- 整数(值)   : 转换为整数
- 小数(值)   : 转换为浮点数
- 文本(值)   : 转换为字符串
"""

from .errors import 运行时错误, 类型错误


class DaoCallable:
    """可调用对象的基类"""

    def call(self, args: list, kwargs: dict) -> object:
        raise NotImplementedError

    def arity(self) -> int:
        """返回参数个数，-1 表示可变参数"""
        return -1


class BuiltinFunction(DaoCallable):
    """内置函数包装器"""

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


# ========================
# 内置函数实现
# ========================

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


def _builtin_类型(obj):
    """类型函数：获取值的类型名称"""
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


# ========================
# 注册所有内置函数
# ========================

def get_builtins() -> dict[str, BuiltinFunction]:
    """返回所有内置函数的字典"""
    return {
        "打印": BuiltinFunction("打印", _builtin_打印),
        "输入": BuiltinFunction("输入", _builtin_输入, 1),
        "长度": BuiltinFunction("长度", _builtin_长度, 1),
        "类型": BuiltinFunction("类型", _builtin_类型, 1),
        "范围": BuiltinFunction("范围", _builtin_范围),
        "整数": BuiltinFunction("整数", _builtin_整数, 1),
        "小数": BuiltinFunction("小数", _builtin_小数, 1),
        "文本": BuiltinFunction("文本", _builtin_文本, 1),
        "交集": BuiltinFunction("交集", _builtin_交集, 2),
        "并集": BuiltinFunction("并集", _builtin_并集, 2),
        "集合": BuiltinFunction("集合", _builtin_集合),
    }
