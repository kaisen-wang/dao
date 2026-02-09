"""
高阶内置函数
===========

需要解释器引用的高阶内置函数实现：映射、筛选、折叠、排序 等。
这些函数接受用户自定义函数作为参数，需要通过解释器来调用它们。
"""

from .callables import InterpreterBuiltin


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
    }
