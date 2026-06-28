"""
AST到数据结构转换
==================

提供AST节点到数据结构（如字典/列表）的双向转换功能。

主要功能：
1. AST转数据结构：用于宏处理过程中的操作
2. 数据结构转AST：用于重建和修改代码
3. 深度复制和修改
4. 节点信息提取

设计原则：
1. 保持转换的精确性
2. 支持所有类型的节点
3. 提供简单易用的API
4. 保持与源AST的一致性
"""

from typing import Any, Dict, List, Optional, Union

from ..ast_nodes import (
    AbstractDecl,
    AssertStmt,
    Assignment,
    AsyncFunctionDecl,
    AwaitAllExpr,
    AwaitExpr,
    AwaitRaceExpr,
    BinaryOp,
    BlockExpr,
    BooleanLiteral,
    BreakStmt,
    ChannelExpr,
    ClassDecl,
    CompareOp,
    ContinueStmt,
    DestructureAssign,
    DictLiteral,
    EnumDecl,
    ExportStmt,
    Expression,
    ExpressionStmt,
    ForInStmt,
    ForRangeStmt,
    FunctionCall,
    FunctionDecl,
    Identifier,
    IfStmt,
    ImportStmt,
    IndexAccess,
    LambdaExpr,
    ListLiteral,
    LogicBlock,
    LogicConstraint,
    LogicCut,
    LogicFact,
    LogicNegation,
    LogicPredicate,
    LogicQuery,
    LogicRule,
    LogicVariable,
    MacroCall,
    MacroDefinition,
    MatchCase,
    MatchStmt,
    MemberAccess,
    NullLiteral,
    NumberLiteral,
    ParallelStmt,
    PipeExpr,
    Program,
    QuoteBlock,
    ReceiveExpr,
    ReturnStmt,
    SelectCase,
    SelectStmt,
    SelfExpr,
    SendStmt,
    Statement,
    StringLiteral,
    SuperExpr,
    SyncStmt,
    TemplateLiteral,
    ThrowStmt,
    TraitDecl,
    TryStmt,
    UnaryOp,
    UnquoteExpr,
    VariableDecl,
    WhileStmt,
    YieldStmt,
)
from ..ast_nodes import (
    AssertStmt as Assert,
)
from ..ast_nodes import (
    BreakStmt as Break,
)
from ..ast_nodes import (
    ClassDecl as ClassDef,
)
from ..ast_nodes import (
    ContinueStmt as Continue,
)
from ..ast_nodes import (
    ForInStmt as For,
)
from ..ast_nodes import (
    IfStmt as If,
)
from ..ast_nodes import (
    LogicVariable as LogicVar,
)
from ..ast_nodes import (
    ReturnStmt as Return,
)
from ..ast_nodes import (
    ThrowStmt as Throw,
)
from ..ast_nodes import (
    TryStmt as Try,
)
from ..ast_nodes import (
    WhileStmt as While,
)
from ..tokens import TokenType


class ASTToData:
    """AST转数据结构"""

    @classmethod
    def convert(cls, node: Union[Expression, Statement, List]) -> Any:
        """转换节点或节点列表"""
        if isinstance(node, list):
            return [cls.convert(n) for n in node]

        if node is None:
            return None

        if hasattr(node, "__dataclass_fields__"):
            return cls._convert_dataclass(node)

        return node

    @classmethod
    def _convert_dataclass(cls, node: Any) -> Dict:
        """转换数据类节点"""
        result = {
            "__type__": type(node).__name__,
            "__line__": node.line,
            "__column__": node.column,
        }

        # 处理字段
        fields = []
        for field_name in getattr(node, "__dataclass_fields__", {}).keys():
            if field_name in ["line", "column"]:
                continue
            value = getattr(node, field_name)
            converted_value = cls.convert(value)
            result[field_name] = converted_value

        return result


class DataToAST:
    """数据结构转AST"""

    @classmethod
    def convert(cls, data: Any) -> Any:
        """转换数据结构到AST节点"""
        if isinstance(data, list):
            return [cls.convert(d) for d in data]

        if data is None:
            return None

        if isinstance(data, dict) and "__type__" in data:
            return cls._convert_dict(data)

        return data

    @classmethod
    def _convert_dict(cls, data: Dict) -> Any:
        """转换字典到节点"""
        type_name = data["__type__"]
        node_class = cls._get_class_by_name(type_name)

        if not node_class:
            return data

        # 创建节点实例
        kwargs = {"line": data.get("__line__", 0), "column": data.get("__column__", 0)}

        # 转换字段值
        for field_name, value in data.items():
            if field_name in ["__type__", "__line__", "__column__"]:
                continue
            converted_value = cls.convert(value)
            kwargs[field_name] = converted_value

        # 创建节点实例
        try:
            return node_class(**kwargs)
        except Exception as e:
            print(f"转换节点 {type_name} 时出错: {e}")
            return None

    @classmethod
    def _get_class_by_name(cls, class_name: str) -> type:
        """根据类名获取类"""
        # 手动维护类名映射，确保覆盖所有类型
        class_map = {
            # 字面量
            "NumberLiteral": NumberLiteral,
            "StringLiteral": StringLiteral,
            "BooleanLiteral": BooleanLiteral,
            "NullLiteral": NullLiteral,
            "ListLiteral": ListLiteral,
            "DictLiteral": DictLiteral,
            # 标识符与访问
            "Identifier": Identifier,
            "MemberAccess": MemberAccess,
            "IndexAccess": IndexAccess,
            # 运算表达式
            "BinaryOp": BinaryOp,
            "UnaryOp": UnaryOp,
            "CompareOp": CompareOp,
            # 函数相关
            "FunctionCall": FunctionCall,
            "LambdaExpr": LambdaExpr,
            # 宏相关
            "MacroCall": MacroCall,
            "QuoteBlock": QuoteBlock,
            "UnquoteExpr": UnquoteExpr,
            "BlockExpr": BlockExpr,
            # 逻辑编程
            "LogicVariable": LogicVar,
            "LogicPredicate": LogicPredicate,
            "LogicNegation": LogicNegation,
            "LogicCut": LogicCut,
            "LogicConstraint": LogicConstraint,
            "LogicFact": LogicFact,
            "LogicRule": LogicRule,
            "LogicQuery": LogicQuery,
            "LogicBlock": LogicBlock,
            # 并发编程
            "ReceiveExpr": ReceiveExpr,
            "SendStmt": SendStmt,
            "ChannelExpr": ChannelExpr,
            "AsyncFunctionDecl": AsyncFunctionDecl,
            "AwaitExpr": AwaitExpr,
            "AwaitAllExpr": AwaitAllExpr,
            "AwaitRaceExpr": AwaitRaceExpr,
            "ParallelStmt": ParallelStmt,
            "SelectStmt": SelectStmt,
            "SelectCase": SelectCase,
            "SyncStmt": SyncStmt,
            # 语句
            "VariableDecl": VariableDecl,
            "Assignment": Assignment,
            "ExpressionStmt": ExpressionStmt,
            "FunctionDecl": FunctionDecl,
            "ReturnStmt": Return,
            "YieldStmt": YieldStmt,
            "IfStmt": If,
            "WhileStmt": While,
            "ForInStmt": For,
            "ForRangeStmt": ForRangeStmt,
            "BreakStmt": Break,
            "ContinueStmt": Continue,
            "TryStmt": Try,
            "ThrowStmt": Throw,
            "AssertStmt": Assert,
            "ClassDecl": ClassDef,
            "TraitDecl": TraitDecl,
            "EnumDecl": EnumDecl,
            "AbstractDecl": AbstractDecl,
            "ImportStmt": ImportStmt,
            "ExportStmt": ExportStmt,
            "DestructureAssign": DestructureAssign,
            "MatchStmt": MatchStmt,
            "MatchCase": MatchCase,
            # 其他
            "Program": Program,
            "PipeExpr": PipeExpr,
            "TemplateLiteral": TemplateLiteral,
            "MacroDefinition": MacroDefinition,
        }

        return class_map.get(class_name)


class ASTSerializer:
    """AST序列化工具"""

    @staticmethod
    def to_json(node: Union[Expression, Statement, List], indent: int = 2) -> str:
        """序列化为JSON字符串"""
        import json

        data = ASTToData.convert(node)
        return json.dumps(data, ensure_ascii=False, indent=indent)

    @staticmethod
    def from_json(json_str: str) -> Any:
        """从JSON字符串解析"""
        import json

        data = json.loads(json_str)
        return DataToAST.convert(data)

    @staticmethod
    def to_file(node: Union[Expression, Statement, List], filename: str):
        """保存到文件"""
        with open(filename, "w", encoding="utf-8") as f:
            f.write(ASTSerializer.to_json(node))

    @staticmethod
    def from_file(filename: str) -> Any:
        """从文件读取"""
        with open(filename, "r", encoding="utf-8") as f:
            return ASTSerializer.from_json(f.read())


class ASTComparison:
    """AST比较工具"""

    @staticmethod
    def equal(node1: Any, node2: Any) -> bool:
        """比较两个节点是否相等"""
        if type(node1) != type(node2):
            return False

        if isinstance(node1, list) and isinstance(node2, list):
            if len(node1) != len(node2):
                return False
            return all(ASTComparison.equal(n1, n2) for n1, n2 in zip(node1, node2))

        if hasattr(node1, "__dataclass_fields__") and hasattr(
            node2, "__dataclass_fields__"
        ):
            for field in getattr(node1, "__dataclass_fields__", {}):
                if field in ["line", "column"]:
                    continue
                value1 = getattr(node1, field)
                value2 = getattr(node2, field)
                if not ASTComparison.equal(value1, value2):
                    return False
            return True

        return node1 == node2
