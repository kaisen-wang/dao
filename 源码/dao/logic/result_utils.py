"""查询结果的格式化与导出工具
============================

本模块只依赖 ``QueryResult`` 的公开接口（``to_dict``），通过延迟导入避免与
:mod:`dao.logic.solver` 形成循环依赖。它同时服务于 Python API 与
``dao/builtins/functions.py`` 中注册的 ``格式化结果()`` 等内置函数。
"""

from __future__ import annotations

from typing import Any

from ..errors import 类型错误

__all__ = ["展示变量值", "格式化结果", "结果转列表", "结果转字典"]


def _规范化结果(结果: Any) -> list[dict[str, Any]]:
    """把 QueryResult / QueryResult 列表 / 字典 / 字典列表统一为字典列表。"""
    if 结果是单个结果(结果):
        项列表 = [结果]
    elif isinstance(结果, (list, tuple)):
        项列表 = list(结果)
    else:
        raise 类型错误(
            "查询结果必须是逻辑查询结果、字典或由它们组成的列表，"
            f"收到: {type(结果).__name__}"
        )

    字典列表: list[dict[str, Any]] = []
    for 项 in 项列表:
        if hasattr(项, "to_dict") and callable(项.to_dict):
            字典列表.append(项.to_dict())
        elif isinstance(项, dict):
            字典列表.append(dict(项))
        else:
            raise 类型错误(
                "查询结果中的每一项必须是逻辑查询结果或字典，"
                f"收到: {type(项).__name__}"
            )
    return 字典列表


def 结果是单个结果(结果: Any) -> bool:
    """判断是否为单个查询结果（QueryResult 或字典）。"""
    from .solver import QueryResult

    return isinstance(结果, (QueryResult, dict))


def _收集变量名(字典列表: list[dict[str, Any]]) -> list[str]:
    """按首次出现顺序收集所有绑定变量名。"""
    变量名: list[str] = []
    for 字典 in 字典列表:
        for 键 in 字典:
            if 键 not in 变量名:
                变量名.append(键)
    return 变量名


def 展示变量值(值: Any) -> str:
    """按道语言的中文显示规则把绑定值转成可读文本。"""
    if 值 is None:
        return "未绑定"
    if isinstance(值, bool):
        return "真" if 值 else "假"
    if isinstance(值, str):
        return 值
    return str(值)


def _表格文本(字典列表: list[dict[str, Any]], 变量名: list[str]) -> str:
    表头 = ["解"] + 变量名
    行数据 = [["解" + str(序号)] + [展示变量值(行.get(名)) for 名 in 变量名] for 序号, 行 in enumerate(字典列表, 1)]

    列宽 = [
        max(len(展示变量值(单元格)) for 单元格 in [行[列] for 行 in 行数据] + [表头[列]])
        for 列 in range(len(表头))
    ]

    def 拼接(单元格列表: list[str]) -> str:
        return " | ".join(单元格.ljust(列宽[序号]) for 序号, 单元格 in enumerate(单元格列表))

    分隔线 = "-+-".join("-" * 宽度 for 宽度 in 列宽)
    return "\n".join([拼接(表头), 分隔线] + [拼接(行) for 行 in 行数据])


def _简洁文本(字典列表: list[dict[str, Any]], 变量名: list[str]) -> str:
    行列表 = []
    for 序号, 行 in enumerate(字典列表, 1):
        绑定 = ", ".join(f"{名}={展示变量值(行.get(名))}" for 名 in 变量名)
        行列表.append(f"解{序号}: {绑定}")
    return "\n".join(行列表)


def 格式化结果(结果: Any, 格式: str = "表格") -> str:
    """把查询结果格式化为中文可读文本。

    Args:
        结果: ``QueryResult``、字典，或由它们组成的列表。
        格式: ``"表格"``（默认）/ ``"简洁"``（每行一个解）。

    Returns:
        中文文本。无匹配结果时返回 ``"无匹配结果"``。

    Raises:
        类型错误: 结果类型不支持，或格式名未知。
    """
    if 格式 not in ("表格", "简洁", "单行"):
        raise 类型错误(f"未知的结果格式 '{格式}'，支持: 表格、简洁、单行")

    字典列表 = _规范化结果(结果)
    if not 字典列表:
        return "无匹配结果"

    变量名 = _收集变量名(字典列表)
    if not 变量名:
        return f"共 {len(字典列表)} 个解（无绑定变量）"

    标题 = f"共 {len(字典列表)} 个解："
    if 格式 == "表格":
        表格 = _表格文本(字典列表, 变量名)
    else:
        表格 = _简洁文本(字典列表, 变量名)
    return f"{标题}\n{表格}"


def 结果转字典(结果: Any) -> list[dict[str, Any]]:
    """把查询结果导出为道语言原生的列表/字典（每项一个解的 ``{?变量: 值}``）。"""
    return _规范化结果(结果)


def 结果转列表(结果: Any, 含变量名: bool = True) -> list[list[Any]]:
    """把查询结果导出为道语言原生的二维列表。

    Args:
        含变量名: 为真时每行是 ``[变量名, 值]`` 对；为假时每行只含值。
    """
    字典列表 = _规范化结果(结果)
    变量名 = _收集变量名(字典列表)
    if 含变量名:
        return [[[名, 行.get(名)] for 名 in 变量名] for 行 in 字典列表]
    return [[行.get(名) for 名 in 变量名] for 行 in 字典列表]
