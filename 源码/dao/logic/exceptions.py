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

class CircularRuleError(LogicError):
    """Circular dependency in rules"""

class ConstraintError(LogicError):
    """Constraint solving error"""

class QueryError(LogicError):
    """Query execution error"""

class KnowledgeBaseError(LogicError):
    """Knowledge base operation error"""
