"""Parser Modules - Statement parsing functionality split by category"""

from .annotation import AnnotationParser
from .control_flow import ControlFlowParser
from .exception_handling import ExceptionHandlingParser
from .expressions import ExpressionAndAssignmentParser
from .function_decl import FunctionDeclParser
from .logic_programming import LogicProgrammingParser
from .module_system import ModuleSystemParser
from .oop_decl import OOPDeclParser
from .pattern_matching import PatternMatchingParser
from .variable_decl import VariableDeclParser
from .concurrency import ConcurrencyParser
from .type_annotation import TypeAnnotationParser
from .type_alias import TypeAliasParser

__all__ = [
    "AnnotationParser",
    "VariableDeclParser",
    "FunctionDeclParser",
    "ControlFlowParser",
    "ExceptionHandlingParser",
    "OOPDeclParser",
    "PatternMatchingParser",
    "ModuleSystemParser",
    "ExpressionAndAssignmentParser",
    "LogicProgrammingParser",
    "ConcurrencyParser",
    "TypeAnnotationParser",
    "TypeAliasParser",
]
