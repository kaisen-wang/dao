"""弧一致性（AC-3）域缩减算法
============================

本模块提供与具体约束求解器解耦的通用 AC-3 实现：

- :class:`Domain`：变量的候选值域（一组已解包的候选值）
- :func:`revise`：对单条弧做一致性修订，裁掉无支持的值
- :func:`ac3`：反复修订直到达到弧一致；若出现空域则提前失败

设计要点
--------

* 不依赖 ``constraints.core`` 中的约束类，只依赖约束对象的两个属性：
  ``constraint_type.value``（类型字符串）与 ``get_variables()``，
  因此不会产生循环导入。
* 二元约束通过 ``variable1`` / ``variable2`` 区分方向（仅"小于"约束有序）。
* 所有用户可见的错误消息使用中文。
"""

from collections import deque
from collections.abc import Iterable
from typing import Any

# 一条弧表示为 (约束, Xi, Xj)；Xj 为 None 表示一元约束
Arc = tuple[Any, Any, Any | None]


def unwrap_value(value: Any) -> Any:
    """把 ``LogicAtom`` 解包成原生值，便于在域中比较。

    这里延迟导入 ``LogicAtom``，避免本模块与 ``constraints.core`` 循环导入。
    """
    from ..core import LogicAtom

    while isinstance(value, LogicAtom):
        value = value.value
    return value


class Domain:
    """变量的候选值域。

    内部保存已解包（``LogicAtom`` → 原生值）的候选值集合。
    候选值必须可哈希，以便进行集合运算；的典型值包括整数、浮点数、
    字符串等。

    属性:
        values: 候选值的不可变集合（``frozenset``）。
    """

    def __init__(self, values: Iterable[Any]):
        try:
            self.values = frozenset(unwrap_value(v) for v in values)
        except TypeError as exc:  # pragma: no cover - 保护性分支
            raise TypeError("域中的候选值必须可哈希") from exc

    def is_empty(self) -> bool:
        """域是否为空。"""
        return not self.values

    def copy(self) -> "Domain":
        """返回本域的浅拷贝（候选值集合不可变，安全共享）。"""
        return Domain(self.values)

    def __eq__(self, other: object) -> bool:
        return isinstance(other, Domain) and self.values == other.values

    def __hash__(self) -> int:
        return hash(("Domain", self.values))

    def __repr__(self) -> str:
        items = ", ".join(repr(v) for v in sorted(self.values, key=repr))
        return f"Domain({{{items}}})"


def _in_range(constraint: Any, value: Any) -> bool:
    """值是否落在数值范围内（与 ``NumericRangeConstraint.is_satisfied`` 一致）。"""
    if isinstance(value, bool):
        return False
    try:
        numeric = float(value)
    except (TypeError, ValueError):
        return False
    return constraint.min_value <= numeric <= constraint.max_value


def _has_type(constraint: Any, value: Any) -> bool:
    """值是否符合类型约束。"""
    return isinstance(value, constraint.expected_type)


def _less_than_ok(constraint: Any, xi: Any, vi: Any, xj: Any, vj: Any) -> bool:
    """判断"小于"约束在 ``xi=vi, xj=vj`` 时是否有支持。

    ``LessThanConstraint(variable1, variable2)`` 表示 ``variable1 < variable2``，
    因此需要根据当前弧的方向决定比较顺序。
    """
    left = getattr(constraint, "variable1", None)
    right = getattr(constraint, "variable2", None)
    try:
        if xi == left and xj == right:
            return vi < vj
        if xi == right and xj == left:
            return vj < vi
    except TypeError:
        return False
    # 方向未知时保守允许，避免误裁剪
    return True


def revise(
    constraint: Any,
    xi: Any,
    domain_i: Domain,
    xj: Any | None = None,
    domain_j: Domain | None = None,
) -> Domain:
    """用约束 ``constraint`` 对弧 ``(Xi, Xj)`` 做一致性修订。

    返回 ``Xi`` 的新域：只保留那些在 ``Xj`` 的域中存在"支持值"的候选值。
    对一元约束，直接按约束过滤 ``Xi`` 的域。

    参数:
        constraint: 约束对象，需提供 ``constraint_type`` 与属性。
        xi: 被修订的变量。
        domain_i: ``xi`` 当前的域。
        xj: 弧的另一端变量；一元约束时为 ``None``。
        domain_j: ``xj`` 当前的域；一元约束时为 ``None``。
    """
    ctype = constraint.constraint_type.value
    values_i = domain_i.values

    # 一元约束：直接过滤
    if ctype == "numeric_range":
        return Domain(v for v in values_i if _in_range(constraint, v))
    if ctype == "type":
        return Domain(v for v in values_i if _has_type(constraint, v))

    # 一元约束或缺少另一端域：无需裁剪
    if domain_j is None:
        return domain_i.copy()

    values_j = domain_j.values
    if ctype == "equality":
        kept = [v for v in values_i if any(v == w for w in values_j)]
    elif ctype == "inequality":
        # InequalityConstraint 与 AllDifferentConstraint 同属 INEQUALITY，
        # 二者对任一变量对都要求"值不相等"，因此修订逻辑一致。
        kept = [v for v in values_i if any(v != w for w in values_j)]
    elif ctype == "less_than":
        kept = [
            v for v in values_i if any(_less_than_ok(constraint, xi, v, xj, w) for w in values_j)
        ]
    else:
        # 未知约束类型：保留原有行为，不做裁剪（fallback）
        kept = list(values_i)

    return Domain(kept)


def build_arcs(constraints: Iterable[Any]) -> list[Arc]:
    """从约束集合构建 AC-3 需要检查的弧列表。

    一元约束产生一条弧 ``(c, X, None)``；n 元约束对每一对有序变量
    产生一条弧 ``(c, Xi, Xj)``。
    """
    arcs: list[Arc] = []
    for constraint in constraints:
        variables = constraint.get_variables()
        if len(variables) == 1:
            arcs.append((constraint, variables[0], None))
        else:
            for vi in variables:
                for vj in variables:
                    if vi != vj:
                        arcs.append((constraint, vi, vj))
    return arcs


def ac3(
    constraints: Iterable[Any],
    domains: dict[Any, Domain],
    counter: list[int] | None = None,
) -> dict[Any, Domain] | None:
    """运行 AC-3 直到达到弧一致。

    参数:
        constraints: 约束列表。
        domains: 变量到初始域的映射（不会被修改）。
        counter: 可选的单元素列表，用于统计 ``revise`` 调用次数。

    返回:
        裁剪后的域字典（新对象）；若任一变量域被裁为空则返回 ``None``，
        表示约束系统不可满足，调用方可据此提前失败。
    """
    constraints = list(constraints)
    pruned = {var: domain.copy() for var, domain in domains.items()}

    arcs = build_arcs(constraints)
    # 索引：当 Xi 的域发生变化时，需要把"指向 Xi"的弧重新入队
    incoming: dict[Any, list[Arc]] = {}
    for arc in arcs:
        xj = arc[2]
        if xj is not None:
            incoming.setdefault(xj, []).append(arc)

    queue = deque(arcs)
    while queue:
        constraint, xi, xj = queue.popleft()
        if counter is not None:
            counter[0] += 1

        domain_i = pruned.get(xi)
        if domain_i is None:
            continue
        domain_j = pruned.get(xj) if xj is not None else None
        if xj is not None and domain_j is None:
            continue

        new_domain = revise(constraint, xi, domain_i, xj, domain_j)
        if new_domain.is_empty():
            # 出现空域：约束系统不可满足，提前失败
            return None
        if new_domain != domain_i:
            pruned[xi] = new_domain
            # 域缩减可能破坏其它弧的一致性，重新入队所有指向 xi 的弧
            for arc in incoming.get(xi, []):
                queue.append(arc)

    return pruned
