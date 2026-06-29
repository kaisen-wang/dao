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
class TupleLiteral(Expression):
    """元组字面量：(1, "苹果", 真)"""

    elements: list[Expression] = field(default_factory=list)


@dataclass
class SetLiteral(Expression):
    """集合字面量：{1, 2, 3}"""

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


@dataclass
class BlockExpr(Expression):
    """块表达式：将一系列语句包装为表达式"""

    body: list[Statement] = field(default_factory=list)


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
    is_abstract: bool = False  # 是否是抽象方法
    is_operator: bool = False  # 是否是运算符重载
    operator_symbol: str = ""  # 运算符符号（如 "+", "-", "=="）
    is_getter: bool = False  # 是否是属性 getter
    is_setter: bool = False  # 是否是属性 setter
    rest_param: str | None = None  # 可变参数名


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
    second_variable: str | None = None


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
    catches: list[dict] = field(
        default_factory=list
    )  # 多个捕获块，每个包含 catch_var、catch_body、error_type
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
class EnumVariant(ASTNode):
    """枚举变体：简单值或带关联数据"""

    name: str = ""
    params: list[str] = field(default_factory=list)


@dataclass
class EnumDecl(Statement):
    """枚举声明：枚举 名字 { 枚举值1, 枚举值2, ... }"""

    name: str = ""
    values: list[str] = field(default_factory=list)
    variants: list[EnumVariant] = field(default_factory=list)


@dataclass
class ClassDecl(Statement):
    """类型声明：类型 名字 [继承自 父类] [实现 特征1, 特征2] ..."""

    name: str = ""
    parent_name: str | None = None
    implemented_traits: list[str] = field(default_factory=list)
    body: list[Statement] = field(default_factory=list)
    is_error_class: bool = False  # 是否是错误类（继承自 错误）
    is_abstract: bool = False  # 是否是抽象类


@dataclass
class AbstractDecl(Statement):
    """抽象类型声明：抽象 类型 名字"""

    name: str = ""
    parent_name: str | None = None
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
class ConditionalExpr(Expression):
    """条件表达式：值 如果 条件 否则 值"""

    true_value: Expression = field(default_factory=lambda: NullLiteral())
    condition: Expression = field(default_factory=lambda: BooleanLiteral())
    false_value: Expression = field(default_factory=lambda: NullLiteral())


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


# ========================
# 模式匹配（解构模式）
# ========================


@dataclass
class ListPattern(Expression):
    """列表模式：[x, y, ...rest]"""

    elements: list[Expression] = field(default_factory=list)
    has_spread: bool = False  # 是否有 ... 展开操作符


@dataclass
class DictPattern(Expression):
    """字典模式：{键: 值}"""

    pairs: list[tuple[Expression, Expression]] = field(default_factory=list)


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
    names: list[str] = field(default_factory=list)  # 选择性导入的名称列表
    alias: str | None = None
    is_from_import: bool = False  # 是否是 "从 模块 导入 {项}" 语法


@dataclass
class ExportStmt(Statement):
    """导出语句：导出 名称 / 导出 {名称1, 名称2}"""

    names: list[str] = field(default_factory=list)


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
    """解构赋值：[甲, 乙] = [10, 20] 或 {姓名, 年龄} = 人"""

    targets: list[str] = field(default_factory=list)
    value: Expression = field(default_factory=lambda: NullLiteral())
    is_declaration: bool = False
    rest_target: str | None = None
    dict_targets: dict[str, str] = field(default_factory=dict)
    is_dict_destructure: bool = False


# ========================
# 逻辑编程
# ========================


@dataclass
class LogicBlock(Statement):
    """逻辑代码块：逻辑 名称 { ... }"""

    name: str = ""
    facts: list["LogicFact"] = field(default_factory=list)
    rules: list["LogicRule"] = field(default_factory=list)


@dataclass
class LogicFact(Expression):
    """事实声明：事实: 父母("张三", "小明")"""

    predicate: str = ""
    arguments: list[Expression] = field(default_factory=list)


@dataclass
class LogicRule(Expression):
    """规则声明：规则: 祖父母(?祖, ?孙) 如果 父母(?祖, ?父) 并且 父母(?父, ?孙)"""

    head: "LogicFact" = field(default_factory=lambda: LogicFact())
    body: list[Expression] = field(default_factory=list)  # 规则体中的逻辑表达式


@dataclass
@dataclass
class LogicVariable(Expression):
    """逻辑变量：?变量名"""

    name: str = ""


@dataclass
class LogicQuery(Expression):
    """查询表达式：查询(知识库, 目标)"""

    knowledge_base: str = ""
    goal: Expression = field(default_factory=lambda: NullLiteral())


@dataclass
class LogicPredicate(Expression):
    """逻辑谓词调用：父母(?父, ?子)"""

    predicate: str = ""
    arguments: list[Expression] = field(default_factory=list)


@dataclass
class LogicNegation(Expression):
    """逻辑否定：非 已封禁(?用户)"""

    expression: Expression = field(default_factory=lambda: NullLiteral())


@dataclass
class LogicCut(Expression):
    """剪枝操作符：剪枝"""

    pass


@dataclass
class LogicConstraint(Expression):
    """约束表达式：?x 在范围 1..10"""

    variable: str = ""
    operator: str = ""  # "在范围"
    bounds: tuple[int, int] = (0, 0)


# ========================
# 并发编程
# ========================


@dataclass
class AsyncFunctionDecl(Statement):
    """异步函数声明：异步 函数 名字(参数) ..."""

    name: str = ""
    params: list[str] = field(default_factory=list)
    default_values: dict[str, Expression] = field(default_factory=dict)
    body: list[Statement] = field(default_factory=list)
    is_static: bool = False
    is_private: bool = False


@dataclass
class AwaitExpr(Expression):
    """等待表达式：等待 表达式"""

    expression: Expression = field(default_factory=lambda: NullLiteral())


@dataclass
class AwaitAllExpr(Expression):
    """全部等待表达式：全部(任务1, 任务2, ...)"""

    expressions: list[Expression] = field(default_factory=list)


@dataclass
class AwaitRaceExpr(Expression):
    """竞速等待表达式：竞速(任务1, 任务2, ...)"""

    expressions: list[Expression] = field(default_factory=list)


@dataclass
class ParallelStmt(Statement):
    """并行块：并行 { ... }"""

    body: list[Statement] = field(default_factory=list)


@dataclass
class ChannelExpr(Expression):
    """通道表达式：通道() 或 通道(容量)"""

    capacity: int | None = None


@dataclass
class SendStmt(Statement):
    """发送语句：发送 通道 值"""

    channel: Expression = field(default_factory=lambda: NullLiteral())
    value: Expression = field(default_factory=lambda: NullLiteral())


@dataclass
class ReceiveExpr(Expression):
    """接收表达式：接收 通道"""

    channel: Expression = field(default_factory=lambda: NullLiteral())


@dataclass
class SelectStmt(Statement):
    """选择语句：选择 { 情况 接收 ch as val: ... 情况 超时(秒数): ... }"""

    cases: list[Expression] = field(default_factory=list)  # SelectCase 节点


@dataclass
class SelectCase(ASTNode):
    """选择分支：情况 接收通道 as var 或 情况 超时(秒数)"""

    type: str = ""  # "receive" 或 "timeout"
    channel: Expression | None = None  # 接收情况的通道
    variable: str | None = None  # 接收情况绑定的变量
    timeout_value: Expression | None = None  # 超时情况的时间值
    body: list[Statement] = field(default_factory=list)


@dataclass
class SyncStmt(Statement):
    """同步块：同步 锁 { ... }"""

    mutex: Expression = field(default_factory=lambda: NullLiteral())
    body: list[Statement] = field(default_factory=list)


# ========================
# 宏系统
# ========================


@dataclass
class MacroDefinition(Statement):
    """宏定义：定义宏 名称(参数) { 引述块 }"""

    name: str = ""
    parameters: list[str] = field(default_factory=list)
    body: Expression = field(default_factory=lambda: NullLiteral())


@dataclass
class QuoteBlock(Expression):
    """引述块：引述 { 代码块 }"""

    body: list[Statement] = field(default_factory=list)


@dataclass
class UnquoteExpr(Expression):
    """注入表达式：注入 表达式"""

    expression: Expression = field(default_factory=lambda: NullLiteral())


@dataclass
class MacroCall(Expression):
    """宏调用：!宏名(参数)"""

    name: str = ""
    arguments: list[Expression] = field(default_factory=list)


# ========================
# 模式匹配宏
# ========================


@dataclass
class PatternBranch(ASTNode):
    """模式分支：模式 [当 守卫] => 引述体"""

    pattern: Expression = field(default_factory=lambda: Identifier())
    guard: Expression | None = None
    body: QuoteBlock = field(default_factory=lambda: QuoteBlock())


@dataclass
class PatternMatchBody(Expression):
    """模式匹配宏体：包含多个模式分支"""

    branches: list[PatternBranch] = field(default_factory=list)


@dataclass
class TypeCheckPattern(Expression):
    """类型检查模式：类型:类型名"""

    type_name: str = ""  # "列表"、"字典"、"数值"、"文本"、"布尔"、"函数"


@dataclass
class EnumVariantPattern(Expression):
    """枚举变体模式：枚举名.变体名(绑定变量)"""

    enum_name: str = ""
    variant_name: str = ""
    binding: str | None = None
