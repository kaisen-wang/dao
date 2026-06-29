"""
高阶内置函数
==========

需要解释器引用的高阶内置函数实现：映射、筛选、折叠、排序 等。
这些函数接受用户自定义函数作为参数，需要通过解释器来调用它们。
"""

from .callables import InterpreterBuiltin, CurriedFunction, DaoCallable


def _hof_柯里化(interpreter, func):
    """柯里化函数：将多参数函数转换为单参数函数链"""
    if not isinstance(func, DaoCallable):
        from ..errors import 类型错误
        raise 类型错误("柯里化() 参数必须是函数")
    curried = CurriedFunction(func)
    curried.interpreter = interpreter
    return curried


def _hof_组合(interpreter, *funcs):
    """函数组合：组合(f, g) 返回函数 f(g(x)) - 从右到左应用（传统数学定义）"""
    if not funcs:
        from ..errors import 运行时错误
        raise 运行时错误("组合() 至少需要一个函数")
    for func in funcs:
        if not isinstance(func, DaoCallable):
            from ..errors import 类型错误
            raise 类型错误("组合() 所有参数都必须是函数")
    if len(funcs) == 1:
        return funcs[0]
    def composed(*args, **kwargs):
        result = interpreter.call_function(funcs[-1], args, kwargs)
        for func in reversed(funcs[:-1]):
            result = interpreter.call_function(func, [result])
        return result
    from .callables import BuiltinFunction
    return BuiltinFunction("组合函数", composed)


def _hof_管道组合(interpreter, *funcs):
    """管道组合：管道组合(f, g, h) 等价于 x => h(g(f(x))) - 从左到右应用"""
    if not funcs:
        from ..errors import 运行时错误
        raise 运行时错误("管道组合() 至少需要一个函数")
    for func in funcs:
        if not isinstance(func, DaoCallable):
            from ..errors import 类型错误
            raise 类型错误("管道组合() 所有参数都必须是函数")
    if len(funcs) == 1:
        return funcs[0]
    def composed(*args, **kwargs):
        result = interpreter.call_function(funcs[0], args, kwargs)
        for func in funcs[1:]:
            result = interpreter.call_function(func, [result])
        return result
    from .callables import BuiltinFunction
    return BuiltinFunction("管道组合函数", composed)


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
        if isinstance(key, list):
            key = tuple(key)
        if key not in groups:
            groups[key] = []
        groups[key].append(item)
    return groups


def _hof_映射流(interpreter, stream, func):
    """映射流：对流惰性映射，返回新流"""
    from .oop_types import DaoStream

    if not isinstance(stream, DaoStream):
        stream = DaoStream(stream)

    return DaoStream(
        iterable=stream,
        transform=lambda value: interpreter.call_function(func, [value]),
    )


def _hof_筛选流(interpreter, stream, func):
    """筛选流：对流惰性筛选，返回新流"""
    from .oop_types import DaoStream

    if not isinstance(stream, DaoStream):
        stream = DaoStream(stream)

    return DaoStream(
        iterable=stream,
        predicate=lambda value: interpreter._is_truthy(
            interpreter.call_function(func, [value])
        ),
    )


def _hof_取(interpreter, stream, n):
    """取：从流中取前 n 个值，返回列表"""
    from .oop_types import DaoStream

    if not isinstance(stream, DaoStream):
        stream = DaoStream(stream)

    result = []
    for i, value in enumerate(stream):
        if i >= n:
            break
        result.append(value)
    return result


# ========================================================
# 注册表
# ========================================================

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
        "映射流": InterpreterBuiltin("映射流", _hof_映射流, 2),
        "筛选流": InterpreterBuiltin("筛选流", _hof_筛选流, 2),
        "取": InterpreterBuiltin("取", _hof_取, 2),
        "柯里化": InterpreterBuiltin("柯里化", _hof_柯里化, 1),
        "组合": InterpreterBuiltin("组合", _hof_组合),
        "管道组合": InterpreterBuiltin("管道组合", _hof_管道组合),
    }
