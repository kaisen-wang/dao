from collections.abc import Generator
from typing import Any

from .core import (
    KnowledgeBase,
    LogicAtom,
    LogicStruct,
    LogicVariable,
    Substitution,
    normalize_term,
)
from .exceptions import QueryError
from .unification import apply_substitution


class QueryResult:
    def __init__(self, substitution, variables: list[str] = None):
        self.substitution = substitution
        self.variables = variables or []

    def get_binding(self, var_name: str) -> Any:
        # 查询变量与规则头变量同名时 unify 不产生绑定；不同名时会产生
        # 「?查询变量 -> ?规则头变量」的链式绑定，最终值挂在规则头变量上。
        # 必须走 get_value 递归解引用，否则结果字典只能拿到中间变量名。
        value = self.substitution.get_value(LogicVariable(var_name))
        if value is None:
            return var_name
        return value

    def to_dict(self) -> dict[str, Any]:
        result = {}
        if self.variables:
            for var_name in self.variables:
                result[var_name] = self._format_value(self.get_binding(var_name))
        else:
            for var_name in self.substitution.keys():
                if var_name.startswith("?"):
                    result[var_name] = self._format_value(self.get_binding(var_name))
        return result

    def _format_value(self, value: Any) -> Any:
        if isinstance(value, LogicStruct):
            return str(value)
        elif isinstance(value, LogicVariable):
            return value.name
        elif isinstance(value, LogicAtom):
            return value.value
        else:
            return value

    def to_list(self, 含变量名: bool = True) -> list:
        """导出为道语言列表。为真时每行是 ``[变量名, 值]`` 对，否则只有值。"""
        from .result_utils import 结果转列表

        return 结果转列表(self, 含变量名=含变量名)[0]

    def 格式化(self, 格式: str = "表格") -> str:
        """把本结果格式化为中文可读文本。"""
        from .result_utils import 格式化结果

        return 格式化结果(self, 格式)

    # ---- 字典式协议：让查询结果能像道语言字典一样被下标访问 ----
    def __getitem__(self, key: str) -> Any:
        return self.to_dict()[key]

    def get(self, key: str, default: Any = None) -> Any:
        return self.to_dict().get(key, default)

    def keys(self):
        return self.to_dict().keys()

    def values(self):
        return self.to_dict().values()

    def items(self):
        return self.to_dict().items()

    def __iter__(self):
        return iter(self.to_dict())

    def __len__(self) -> int:
        return len(self.to_dict())

    def __repr__(self) -> str:
        items = ", ".join(f"{k}={v!r}" for k, v in self.to_dict().items())
        return f"{{{items}}}"

    def __str__(self) -> str:
        items = ", ".join(f"{k}={v}" for k, v in self.to_dict().items())
        return f"{{{items}}}"


class Solver:
    def __init__(
        self, knowledge_base: KnowledgeBase, constraints: list | None = None
    ):
        self.kb = knowledge_base
        from .backtracking import Backtracker

        self.backtracker = Backtracker(knowledge_base, constraints)
        from .constraints.core import ConstraintSolver

        self.constraint_solver = ConstraintSolver(constraints or [])
        self._cut_active = False

    def solve(
        self, goal: Any, variables: list[str] = None, max_solutions: int = 0
    ) -> list[QueryResult]:
        goal = normalize_term(goal)
        results = []
        count = 0
        for substitution in self.backtracker.search(goal):
            # 应用约束传播
            propagated_subst = self.constraint_solver.propagate_constraints(
                substitution
            )
            if self.constraint_solver.check_constraints(propagated_subst):
                result = QueryResult(propagated_subst, variables)
                results.append(result)
                count += 1
                if max_solutions > 0 and count >= max_solutions:
                    break
        return results

    def solve_one(
        self, goal: Any, variables: list[str] = None
    ) -> QueryResult | None:
        results = self.solve(goal, variables, max_solutions=1)
        return results[0] if results else None

    def exists(self, goal: Any) -> bool:
        return self.solve_one(goal) is not None

    def solve_generator(
        self, goal: Any, variables: list[str] = None
    ) -> Generator[QueryResult, None, None]:
        goal = normalize_term(goal)
        for substitution in self.backtracker.search(goal):
            # 应用约束传播
            propagated_subst = self.constraint_solver.propagate_constraints(
                substitution
            )
            if self.constraint_solver.check_constraints(propagated_subst):
                yield QueryResult(propagated_subst, variables)

    def solve_negation(self, goal: Any) -> bool:
        new_solver = Solver(self.kb)
        result = new_solver.solve_one(goal)
        return result is None

    def solve_negation_with_subst(self, goal: Any, substitution: Substitution) -> bool:
        goal = apply_substitution(goal, substitution)
        return not self.exists(goal)

    def add_constraint(self, constraint):
        """添加约束"""
        self.constraint_solver.add_constraint(constraint)
        from .backtracking import Backtracker

        self.backtracker = Backtracker(self.kb, self.constraint_solver.constraints)

    def remove_constraint(self, constraint):
        """移除约束"""
        self.constraint_solver.remove_constraint(constraint)
        from .backtracking import Backtracker

        self.backtracker = Backtracker(self.kb, self.constraint_solver.constraints)

    def clear_constraints(self):
        """清除所有约束"""
        self.constraint_solver.clear_constraints()
        from .backtracking import Backtracker

        self.backtracker = Backtracker(self.kb, [])

    def get_constraints(self):
        """获取所有约束"""
        return self.constraint_solver.constraints

    def has_constraints(self):
        """检查是否有约束"""
        return self.constraint_solver.has_constraints()

    def solve_conjunction(
        self, goals: list[Any], variables: list[str] = None
    ) -> list[QueryResult]:
        if not goals:
            return [QueryResult(Substitution(), variables)]
        first = goals[0]
        rest = goals[1:]
        if not rest:
            return self.solve(first, variables)
        results = []
        for result in self.solve(first):
            for rest_result in self._solve_with_subst(
                rest, result.substitution, variables
            ):
                results.append(rest_result)
        return results

    def _solve_with_subst(
        self, goals: list[Any], substitution: Substitution, variables: list[str] = None
    ) -> list[QueryResult]:
        if not goals:
            return [QueryResult(substitution, variables)]
        first = goals[0]
        rest = goals[1:]
        first = apply_substitution(first, substitution)
        results = []
        for subst in self.backtracker.search(first, substitution):
            merged_subst = Substitution()
            merged_subst.update(substitution)
            merged_subst.update(subst)
            if rest:
                for result in self._solve_with_subst(rest, merged_subst, variables):
                    results.append(result)
            else:
                results.append(QueryResult(merged_subst, variables))
        return results

    def solve_disjunction(
        self, goals: list[Any], variables: list[str] = None
    ) -> list[QueryResult]:
        all_results = []
        for goal in goals:
            results = self.solve(goal, variables)
            all_results.extend(results)
        return all_results

    def count_solutions(self, goal: Any, max_count: int = 1000) -> int:
        count = 0
        for _ in self.solve_generator(goal):
            count += 1
            if count >= max_count:
                break
        return count

    def explain_solution(self, result: QueryResult, goal: Any) -> str:
        lines = []
        lines.append(f"Query: {goal}")
        lines.append(f"Solution: {result}")
        if result.to_dict():
            lines.append("Variable bindings:")
            for var_name, value in result.to_dict().items():
                lines.append(f"  {var_name} = {value}")
        else:
            lines.append("No variable bindings (constant query)")
        result_str = ""
        for line in lines:
            result_str += line + " "
        return result_str


def solve(
    knowledge_base: KnowledgeBase, goal: Any, variables: list[str] = None
) -> list[QueryResult]:
    solver = Solver(knowledge_base)
    return solver.solve(goal, variables)


def _规范变量名(名称: str) -> str:
    """把变量名统一为带 ``?`` 前缀的规范形式（结果字典的键约定）。"""
    return 名称 if 名称.startswith("?") else "?" + 名称


def _排序键(值: Any) -> tuple:
    """为混合类型的值生成可比较的排序键：空 < 布尔 < 数值 < 其他。"""
    if 值 is None:
        return (0, 0)
    if isinstance(值, bool):
        return (1, int(值))
    if isinstance(值, (int, float)):
        return (2, 值)
    return (3, str(值))


def _应用排序分页(
    结果列表: list[QueryResult],
    排序: Any,
    降序: bool,
    偏移: int,
    限制: int | None,
) -> list[QueryResult]:
    """按绑定变量排序，再做偏移/限制分页。"""
    if 排序 is not None:
        if isinstance(排序, str):
            排序变量 = [排序]
        elif isinstance(排序, (list, tuple)):
            排序变量 = list(排序)
        else:
            raise QueryError("排序参数必须是变量名或变量名列表")
        if not 排序变量 or any(not isinstance(名, str) or not 名 for 名 in 排序变量):
            raise QueryError("排序参数中的变量名必须是非空文本")
        规范排序变量 = [_规范变量名(名) for 名 in 排序变量]

        def 排序键(结果: QueryResult) -> tuple:
            字典 = 结果.to_dict()
            return tuple(_排序键(字典.get(名)) for 名 in 规范排序变量)

        结果列表 = sorted(结果列表, key=排序键, reverse=bool(降序))

    for 名称, 值 in (("偏移", 偏移), ("限制", 限制)):
        if 值 is None:
            continue
        if isinstance(值, bool) or not isinstance(值, int) or 值 < 0:
            raise QueryError(f"{名称}必须是非负整数，收到: {值!r}")

    if 偏移:
        结果列表 = 结果列表[偏移:]
    if 限制 is not None:
        结果列表 = 结果列表[:限制]
    return 结果列表


def _求解子句(
    solver: "Solver",
    目标列表: list,
    变量: list[str],
    substitution: Substitution | None = None,
):
    """按顺序求解一个合取子句，逐目标传递绑定，支持否定目标。"""
    if substitution is None:
        substitution = Substitution()

    if not 目标列表:
        传播后 = solver.constraint_solver.propagate_constraints(substitution)
        if solver.constraint_solver.check_constraints(传播后):
            yield QueryResult(传播后, 变量)
        return

    目标 = 目标列表[0]
    当前项 = apply_substitution(目标.term, substitution)
    if 目标.negated:
        if not solver.exists(当前项):
            yield from _求解子句(solver, 目标列表[1:], 变量, substitution)
        return

    for 新替换 in solver.backtracker.search(当前项, substitution):
        传播后 = solver.constraint_solver.propagate_constraints(新替换)
        if not solver.constraint_solver.check_constraints(传播后):
            continue
        yield from _求解子句(solver, 目标列表[1:], 变量, 传播后)


def query(
    knowledge_base: KnowledgeBase,
    goal_str: str,
    variables: list[str] | tuple[str, ...] | None = None,
    *,
    排序: str | list[str] | None = None,
    降序: bool = False,
    偏移: int = 0,
    限制: int | None = None,
    sort_by: str | list[str] | None = None,
    descending: bool | None = None,
    offset: int | None = None,
    limit: int | None = None,
    结果对象: bool = False,
) -> list[dict[str, Any]] | list[QueryResult]:
    """解析并执行逻辑查询（支持嵌套结构、合取/析取、排序分页）。

    Args:
        knowledge_base: 知识库。
        goal_str: 查询字符串，例如 ``"父母(?x, '小明')"``、
            ``"祖孙(grandparent(?x), ?y) 并且 城市(?y, '北京')"``
            或 ``"颜色(?x) 或者 尺寸(?x, 大)"``。
        variables: 需要展示/显式声明为变量的名称（``x`` 与 ``?x`` 等价）。
        排序: 绑定变量名（或变量名列表），按该变量的值升序排列。
        降序: 与 ``排序`` 配合，倒序排列。
        偏移: 跳过前 N 个解。
        限制: 最多返回 N 个解。
        sort_by/descending/offset/limit: 上述参数的英文别名。
        结果对象: 为真时返回 ``QueryResult`` 列表，默认返回字典列表。

    Returns:
        默认 ``list[dict]``（键为 ``"?变量"``）；``结果对象=True`` 时为
        ``list[QueryResult]``。

    Raises:
        QueryError: 查询语法错误（消息为中文且包含位置）或执行失败。
    """
    from .query_parser import parse_query

    if 排序 is None:
        排序 = sort_by
    if descending is not None:
        降序 = descending
    if offset is not None:
        偏移 = offset
    if limit is not None:
        限制 = limit

    if not isinstance(knowledge_base, KnowledgeBase):
        raise QueryError("查询的第一个参数必须是知识库")
    if not isinstance(goal_str, str):
        raise QueryError(f"查询目标必须是文本，收到: {type(goal_str).__name__}")

    规范变量 = []
    for 名称 in variables or ():
        if not isinstance(名称, str) or not 名称:
            raise QueryError(f"变量声明必须是非空文本，收到: {名称!r}")
        规范变量.append(_规范变量名(名称))

    try:
        解析结果 = parse_query(goal_str, variables)
        for 名称 in 规范变量:
            if 名称 not in 解析结果.variables:
                解析结果.variables.append(名称)

        solver = Solver(knowledge_base)
        结果列表: list[QueryResult] = []
        for 子句 in 解析结果.clauses:
            结果列表.extend(_求解子句(solver, 子句, 解析结果.variables))
        结果列表 = _应用排序分页(结果列表, 排序, 降序, 偏移, 限制)
    except QueryError:
        raise
    except Exception as e:  # noqa: BLE001 - 刻意兜底：统一包装为 QueryError 向上抛出
        raise QueryError(f"查询解析或执行失败: {e}") from e

    if 结果对象:
        return 结果列表
    return [结果.to_dict() for 结果 in 结果列表]


# 结果格式化/导出工具（同时供 格式化结果() 等内置函数调用）
from .result_utils import (  # noqa: E402
    格式化结果,
    结果转列表,
    结果转字典,
    展示变量值,
)

