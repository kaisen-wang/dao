# -*- coding: utf-8 -*-
"""Logic Programming Exceptions Module"""

class LogicError(Exception):
    """Base exception for logic programming"""
    def __init__(self, message: str, line: int = 0, column: int = 0):
        self.message = message
        self.line = line
        self.column = column
        super().__init__(message)

class UnificationError(LogicError):
    """Error during unification"""
    pass

class CircularRuleError(LogicError):
    """Circular dependency in rules"""
    pass

class ConstraintError(LogicError):
    """Constraint solving error"""
    pass

class QueryError(LogicError):
    """Query execution error"""
    pass

class KnowledgeBaseError(LogicError):
    """Knowledge base operation error"""
    pass
