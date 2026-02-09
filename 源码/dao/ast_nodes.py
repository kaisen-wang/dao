"""
抽象语法树（AST）节点定义
========================

定义所有AST节点类型。语法分析器将Token流转换为这些节点组成的树形结构，
解释器遍历这棵树来执行程序。

设计原则：
- 每个节点都是不可变的dataclass
- 每个节点记录源代码位置（line, column）便于错误报告
- 使用继承体系区分语句（Statement）和表达式（Expression）
"""

from dataclasses import dataclass, field
from typing import Any


# ========================
# 基类
# ========================

@dataclass
class ASTNode:
    """AST节点基类"""
    line: int = 0
    column: int = 0


@dataclass
class Expression(ASTNode):
    """表达式基类：有返回值的节点"""
    pass


@dataclass
class Statement(ASTNode):
    """语句基类：执行动作但不一定有返回值的节点"""
    pass


# ========================
# 字面量表达式
# ========================

@dataclass
class NumberLiteral(Expression):
    """数值字面量：42, 3.14"""
    value: float | int = 0


@dataclass
class StringLiteral(Expression):
    """字符串字面量："你好" """
    value: str = ""


@dataclass
class BooleanLiteral(Expression):
    """布尔字面量：真, 假"""
    value: bool = True


@dataclass
class NullLiteral(Expression):
    """空值字面量：空"""
    pass


@dataclass
class ListLiteral(Expression):
    """列表字面量：[1, 2, 3]"""
    elements: list[Expression] = field(default_factory=list)


@dataclass
class DictLiteral(Expression):
    """字典字面量：{"键": 值}"""
    pairs: list[tuple[Expression, Expression]] = field(default_factory=list)


# ========================
# 标识符与访问
# ========================

@dataclass
class Identifier(Expression):
    """标识符（变量名）"""
    name: str = ""


@dataclass
class MemberAccess(Expression):
    """成员访问：对象.属性"""
    object: Expression = field(default_factory=lambda: Identifier())
    member: str = ""


@dataclass
class IndexAccess(Expression):
    """索引访问：列表[0]"""
    object: Expression = field(default_factory=lambda: Identifier())
    index: Expression = field(default_factory=lambda: NumberLiteral())


# ========================
# 运算表达式
# ========================

@dataclass
class BinaryOp(Expression):
    """二元运算：甲 + 乙"""
    left: Expression = field(default_factory=lambda: Identifier())
    operator: str = ""
    right: Expression = field(default_factory=lambda: Identifier())


@dataclass
class UnaryOp(Expression):
    """一元运算：不是 x, -x"""
    operator: str = ""
    operand: Expression = field(default_factory=lambda: Identifier())


@dataclass
class CompareOp(Expression):
    """比较运算（支持链式比较）：1 < x <= 10"""
    operands: list[Expression] = field(default_factory=list)
    operators: list[str] = field(default_factory=list)


# ========================
# 函数相关
# ========================

@dataclass
class FunctionCall(Expression):
    """函数调用：函数名(参数1, 参数2)"""
    callee: Expression = field(default_factory=lambda: Identifier())
    arguments: list[Expression] = field(default_factory=list)
    keyword_args: dict[str, Expression] = field(default_factory=dict)


@dataclass
class LambdaExpr(Expression):
    """匿名函数：函数(x) => x * 2"""
    params: list[str] = field(default_factory=list)
    body: "ASTNode" = field(default_factory=lambda: NullLiteral())


# ========================
# 语句
# ========================

@dataclass
class Program(ASTNode):
    """程序根节点：包含所有顶层语句"""
    statements: list[Statement] = field(default_factory=list)


@dataclass
class VariableDecl(Statement):
    """变量声明：定义 x = 10"""
    name: str = ""
    value: Expression = field(default_factory=lambda: NullLiteral())
    is_constant: bool = False


@dataclass
class Assignment(Statement):
    """赋值语句：x = 10"""
    target: Expression = field(default_factory=lambda: Identifier())
    value: Expression = field(default_factory=lambda: NullLiteral())


@dataclass
class ExpressionStmt(Statement):
    """表达式语句：将表达式当作语句使用（如函数调用）"""
    expression: Expression = field(default_factory=lambda: NullLiteral())


@dataclass
class FunctionDecl(Statement):
    """函数声明：函数 名字(参数) ..."""
    name: str = ""
    params: list[str] = field(default_factory=list)
    default_values: dict[str, Expression] = field(default_factory=dict)
    body: list[Statement] = field(default_factory=list)
    is_static: bool = False
    is_private: bool = False


@dataclass
class ReturnStmt(Statement):
    """返回语句：返回 值"""
    value: Expression | None = None


@dataclass
class YieldStmt(Statement):
    """产出语句：产出 值"""
    value: Expression | None = None


# ========================
# 控制流
# ========================

@dataclass
class IfStmt(Statement):
    """条件语句：如果 ... 否则如果 ... 否则 ..."""
    condition: Expression = field(default_factory=lambda: BooleanLiteral())
    body: list[Statement] = field(default_factory=list)
    elif_clauses: list[tuple[Expression, list[Statement]]] = field(default_factory=list)
    else_body: list[Statement] = field(default_factory=list)


@dataclass
class WhileStmt(Statement):
    """当循环：当 条件 ..."""
    condition: Expression = field(default_factory=lambda: BooleanLiteral())
    body: list[Statement] = field(default_factory=list)


@dataclass
class ForInStmt(Statement):
    """遍历循环：遍历 变量 在 集合 ..."""
    variable: str = ""
    iterable: Expression = field(default_factory=lambda: Identifier())
    body: list[Statement] = field(default_factory=list)


@dataclass
class ForRangeStmt(Statement):
    """范围循环：遍历 变量 从 起始 到 结束 ..."""
    variable: str = ""
    start: Expression = field(default_factory=lambda: NumberLiteral())
    end: Expression = field(default_factory=lambda: NumberLiteral())
    step: Expression | None = None
    body: list[Statement] = field(default_factory=list)


@dataclass
class BreakStmt(Statement):
    """跳出语句"""
    pass


@dataclass
class ContinueStmt(Statement):
    """继续语句"""
    pass


# ========================
# 错误处理
# ========================

@dataclass
class TryStmt(Statement):
    """尝试-捕获-最终"""
    try_body: list[Statement] = field(default_factory=list)
    catch_var: str | None = None
    catch_body: list[Statement] = field(default_factory=list)
    finally_body: list[Statement] = field(default_factory=list)


@dataclass
class ThrowStmt(Statement):
    """抛出异常：抛出 错误("消息")"""
    expression: Expression = field(default_factory=lambda: Identifier())


@dataclass
class AssertStmt(Statement):
    """断言语句：断言 条件, "消息" """
    condition: Expression = field(default_factory=lambda: BooleanLiteral())
    message: Expression | None = None


# ========================
# OOP
# ========================

@dataclass
class TraitDecl(Statement):
    """特征声明：特征 名字 ..."""
    name: str = ""
    body: list[Statement] = field(default_factory=list)


@dataclass
class ClassDecl(Statement):
    """类型声明：类型 名字 [继承自 父类] [实现 特征1, 特征2] ..."""
    name: str = ""
    parent_name: str | None = None
    implemented_traits: list[str] = field(default_factory=list)
    body: list[Statement] = field(default_factory=list)


@dataclass
class SelfExpr(Expression):
    """本对象引用 (this/self)"""
    pass


@dataclass
class SuperExpr(Expression):
    """父对象引用 (super)"""
    pass


# ========================
# 管道运算符
# ========================

@dataclass
class PipeExpr(Expression):
    """管道表达式：甲 |> 乙"""
    left: Expression = field(default_factory=lambda: Identifier())
    right: Expression = field(default_factory=lambda: Identifier())


# ========================
# 模式匹配
# ========================

@dataclass
class MatchStmt(Statement):
    """匹配语句：匹配 表达式 ..."""
    subject: Expression = field(default_factory=lambda: Identifier())
    cases: list["MatchCase"] = field(default_factory=list)


@dataclass
class MatchCase(ASTNode):
    """匹配分支：情况 模式 [当 守卫]: 代码块"""
    pattern: Expression = field(default_factory=lambda: Identifier())
    guard: Expression | None = None
    body: list[Statement] = field(default_factory=list)
    is_wildcard: bool = False


# ========================
# 模块系统
# ========================

@dataclass
class ImportStmt(Statement):
    """导入语句"""
    module_path: str = ""
    names: list[str] = field(default_factory=list)
    alias: str | None = None


# ========================
# 模板字符串
# ========================

@dataclass
class TemplateLiteral(Expression):
    """模板字符串：`你好 {名字}，{年龄}岁`"""
    parts: list[str] = field(default_factory=list)
    expressions: list[Expression] = field(default_factory=list)


# ========================
# 解构赋值
# ========================

@dataclass
class DestructureAssign(Statement):
    """解构赋值：[甲, 乙] = [10, 20]"""
    targets: list[str] = field(default_factory=list)
    value: Expression = field(default_factory=lambda: NullLiteral())
    is_declaration: bool = False
