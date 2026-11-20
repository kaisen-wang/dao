"""Logic Programming Engine Module"""

from .backtracking import TrailStack
from .core import KnowledgeBase
from .solver import solve
from .unification import apply_substitution, occurs_check, unify

__all__ = [
    "KnowledgeBase",
    "TrailStack",
    "apply_substitution",
    "occurs_check",
    "solve",
    "unify",
]
