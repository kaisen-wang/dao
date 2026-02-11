# -*- coding: utf-8 -*-
"""Logic Programming Engine Module"""

from .core import KnowledgeBase
from .unification import unify, apply_substitution, occurs_check
from .backtracking import TrailStack
from .solver import solve

__all__ = [
    "KnowledgeBase",
    "unify",
    "apply_substitution",
    "occurs_check",
    "TrailStack",
    "solve",
]
