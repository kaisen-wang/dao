"""Logic Programming Engine Module"""

from .backtracking import TrailStack
from .core import KnowledgeBase
from .solver import QueryResult, 格式化结果, query, solve
from .unification import apply_substitution, occurs_check, unify

__all__ = [
    "KnowledgeBase",
    "QueryResult",
    "TrailStack",
    "apply_substitution",
    "occurs_check",
    "query",
    "solve",
    "unify",
    "格式化结果",
]
