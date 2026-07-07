"""
模式匹配引擎
============

在宏展开时对参数值进行模式匹配判断，支持多种匹配模式类型。

支持的匹配模式：
- 字面量模式：匹配特定值（数值、字符串、布尔、空值）
- 变量绑定模式：匹配任意值并绑定到变量
- 通配符模式：匹配任意值但不绑定
- 列表解构模式：匹配列表并解构元素（支持嵌套模式）
- 字典解构模式：匹配字典并解构键值对（支持嵌套模式）
- 类型检查模式：匹配特定类型的值
- 枚举变体模式：匹配枚举类型的特定变体
- 守卫条件模式：模式匹配成功后附加条件判断

公共 API：
- PatternMatchEngine：模式匹配引擎主类
- MatchResult：匹配结果数据类
- DaoEnumProtocol：枚举协议接口（ABC）
- DictEnumAdapter：字典枚举适配器
- DaoStandardEnumAdapter：标准枚举适配器
- DuckTypeEnumAdapter：鸭子类型枚举适配器
- adapt_to_enum_protocol：枚举协议适配入口函数
- classify_pattern：模式分类查询函数
- describe_pattern：模式描述生成函数
"""

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Optional

from ..ast_nodes import (
    BooleanLiteral,
    DictPattern,
    EnumVariantPattern,
    Identifier,
    ListPattern,
    NullLiteral,
    NumberLiteral,
    PatternBranch,
    StringLiteral,
    TypeCheckPattern,
)

logger = logging.getLogger('dao.macros')


# ============================================================
# 模式类型枚举
# ============================================================


class PatternType(Enum):
    """模式类型枚举，用于 classify_pattern 返回值"""

    LITERAL = "字面量"
    WILDCARD = "通配符"
    VARIABLE_BINDING = "变量绑定"
    LIST_DESTRUCTURE = "列表解构"
    DICT_DESTRUCTURE = "字典解构"
    TYPE_CHECK = "类型检查"
    ENUM_VARIANT = "枚举变体"
    UNKNOWN = "未知"


# ============================================================
# 模式匹配协议接口
# ============================================================


class DaoEnumProtocol(ABC):
    """道语言枚举协议接口

    定义了模式匹配引擎识别枚举变体的统一协议。
    任何实现了此协议的对象都可以参与枚举变体模式匹配。

    协议层次：
    1. DaoEnumProtocol（ABC）— 道语言标准枚举协议
    2. DictEnumAdapter — 字典形式的枚举表示适配器
    3. DuckTypeEnumAdapter — 鸭子类型枚举适配器

    实现此协议的对象需提供：
    - dao_class_name: 所属枚举类名
    - dao_variant_name: 变体名称
    - dao_inner_value: 变体内部值（可选）
    """

    @property
    @abstractmethod
    def dao_class_name(self) -> str:
        """返回所属枚举类名"""
        ...

    @property
    @abstractmethod
    def dao_variant_name(self) -> str:
        """返回变体名称"""
        ...

    @property
    def dao_inner_value(self) -> Any:
        """返回变体内部值，默认返回 None"""
        return None

    def matches_enum(self, enum_name: str, variant_name: str) -> bool:
        """检查是否匹配指定的枚举名和变体名"""
        return self.dao_class_name == enum_name and self.dao_variant_name == variant_name


class DictEnumAdapter(DaoEnumProtocol):
    """字典形式枚举适配器

    将字典形式的枚举表示 {'__type__': 'enum', '类': ..., '变体': ...}
    适配为 DaoEnumProtocol 接口。
    """

    def __init__(self, data: dict):
        self._data = data

    @property
    def dao_class_name(self) -> str:
        return self._data.get('类', '')

    @property
    def dao_variant_name(self) -> str:
        return self._data.get('变体', '')

    @property
    def dao_inner_value(self) -> Any:
        return self._data.get('值')

    @classmethod
    def can_adapt(cls, value: Any) -> bool:
        """检查值是否可以被此适配器适配"""
        return isinstance(value, dict) and value.get('__type__') == 'enum'


class DaoStandardEnumAdapter(DaoEnumProtocol):
    """道语言标准枚举适配器

    将具有 __dao_class__ / __variant__ 协议属性的对象
    适配为 DaoEnumProtocol 接口。
    """

    def __init__(self, obj: Any):
        self._obj = obj

    @property
    def dao_class_name(self) -> str:
        return getattr(self._obj, '__dao_class__', '')

    @property
    def dao_variant_name(self) -> str:
        return getattr(self._obj, '__variant__', '')

    @property
    def dao_inner_value(self) -> Any:
        return _extract_object_value(self._obj)


class DuckTypeEnumAdapter(DaoEnumProtocol):
    """鸭子类型枚举适配器

    通过对象的类名进行匹配，将任意对象适配为 DaoEnumProtocol 接口。
    """

    def __init__(self, obj: Any):
        self._obj = obj
        self._class_name = type(obj).__name__

    @property
    def dao_class_name(self) -> str:
        return self._class_name

    @property
    def dao_variant_name(self) -> str:
        return self._class_name

    @property
    def dao_inner_value(self) -> Any:
        return _extract_object_value(self._obj)

    @classmethod
    def can_adapt(cls, value: Any) -> bool:
        """检查值是否可以被此适配器适配（任何非字典、非DaoEnumProtocol对象）"""
        return not isinstance(value, dict) and not isinstance(value, DaoEnumProtocol)


def adapt_to_enum_protocol(value: Any) -> Optional[DaoEnumProtocol]:
    """将任意值适配为 DaoEnumProtocol 接口

    按协议层次依次尝试：
    1. 如果值本身就是 DaoEnumProtocol 实例，直接返回
    2. 如果值具有 __dao_class__ / __variant__ 属性，使用 DaoStandardEnumAdapter
    3. 尝试 DictEnumAdapter 适配
    4. 尝试 DuckTypeEnumAdapter 适配

    Args:
        value: 要适配的值

    Returns:
        DaoEnumProtocol 实例，或 None（无法适配）
    """
    # 层次1: 已经是 DaoEnumProtocol 实例
    if isinstance(value, DaoEnumProtocol):
        return value

    # 层次2: 道语言标准枚举协议 (__dao_class__ / __variant__)
    if hasattr(value, '__dao_class__'):
        return DaoStandardEnumAdapter(value)

    # 层次3: 字典形式枚举
    if DictEnumAdapter.can_adapt(value):
        return DictEnumAdapter(value)

    # 层次4: 鸭子类型
    if DuckTypeEnumAdapter.can_adapt(value):
        return DuckTypeEnumAdapter(value)

    return None


def _extract_object_value(value: Any) -> Any:
    """从对象中提取内部值，使用多种策略"""
    # 策略1: _value 属性
    if hasattr(value, '_value'):
        return value._value
    # 策略2: 值 属性
    if hasattr(value, '值'):
        return value.值
    # 策略3: 第一个非特殊属性
    for attr_name in dir(value):
        if not attr_name.startswith('_') and attr_name not in ('__dao_class__', '__variant__'):
            return getattr(value, attr_name)
    return value


# ============================================================
# 匹配结果
# ============================================================


@dataclass
class MatchResult:
    """模式匹配结果

    Attributes:
        matched: 是否匹配成功
        bindings: 变量绑定字典，键为变量名，值为绑定的运行时值
        failure_reason: 匹配失败原因（仅在 matched=False 时有意义）
    """

    matched: bool = False
    bindings: dict = field(default_factory=dict)
    failure_reason: str = ""

    def merge(self, other: 'MatchResult') -> 'MatchResult':
        """合并两个匹配结果

        当两个结果都匹配成功时，合并变量绑定；
        任一结果匹配失败时，返回失败结果。

        Args:
            other: 另一个匹配结果

        Returns:
            合并后的 MatchResult
        """
        if not self.matched:
            return MatchResult(matched=False, bindings={}, failure_reason=self.failure_reason)
        if not other.matched:
            return MatchResult(matched=False, bindings={}, failure_reason=other.failure_reason)
        merged_bindings = {**self.bindings, **other.bindings}
        return MatchResult(matched=True, bindings=merged_bindings)

    @staticmethod
    def success(bindings: dict | None = None) -> 'MatchResult':
        """创建匹配成功的结果

        Args:
            bindings: 变量绑定字典

        Returns:
            匹配成功的 MatchResult
        """
        return MatchResult(matched=True, bindings=bindings or {})

    @staticmethod
    def failure(reason: str = "") -> 'MatchResult':
        """创建匹配失败的结果

        Args:
            reason: 失败原因描述

        Returns:
            匹配失败的 MatchResult
        """
        return MatchResult(matched=False, bindings={}, failure_reason=reason)


# ============================================================
# 模式分类与描述
# ============================================================


def classify_pattern(pattern) -> PatternType:
    """对模式AST节点进行分类

    Args:
        pattern: 匹配模式AST节点

    Returns:
        PatternType 枚举值，表示模式的类型
    """
    if isinstance(pattern, (NumberLiteral, StringLiteral, BooleanLiteral, NullLiteral)):
        return PatternType.LITERAL
    if isinstance(pattern, Identifier):
        if pattern.name == "_":
            return PatternType.WILDCARD
        return PatternType.VARIABLE_BINDING
    if isinstance(pattern, ListPattern):
        return PatternType.LIST_DESTRUCTURE
    if isinstance(pattern, DictPattern):
        return PatternType.DICT_DESTRUCTURE
    if isinstance(pattern, TypeCheckPattern):
        return PatternType.TYPE_CHECK
    if isinstance(pattern, EnumVariantPattern):
        return PatternType.ENUM_VARIANT
    return PatternType.UNKNOWN


def describe_pattern(pattern, indent: int = 0) -> str:
    """生成模式的人类可读描述

    递归地描述模式结构，包括嵌套模式。

    Args:
        pattern: 匹配模式AST节点
        indent: 缩进层级（用于嵌套模式的格式化）

    Returns:
        模式的描述字符串
    """
    prefix = "  " * indent
    ptype = classify_pattern(pattern)

    if ptype == PatternType.LITERAL:
        if isinstance(pattern, NumberLiteral):
            return f"{prefix}字面量模式: {pattern.value}"
        if isinstance(pattern, StringLiteral):
            return f"{prefix}字面量模式: \"{pattern.value}\""
        if isinstance(pattern, BooleanLiteral):
            return f"{prefix}字面量模式: {'真' if pattern.value else '假'}"
        if isinstance(pattern, NullLiteral):
            return f"{prefix}字面量模式: 空"

    if ptype == PatternType.WILDCARD:
        return f"{prefix}通配符模式: _"

    if ptype == PatternType.VARIABLE_BINDING:
        return f"{prefix}变量绑定模式: {pattern.name}"

    if ptype == PatternType.LIST_DESTRUCTURE:
        lines = [f"{prefix}列表解构模式:"]
        for elem in pattern.elements:
            lines.append(describe_pattern(elem, indent + 1))
        if pattern.has_spread:
            lines.append(f"{prefix}  (含展开操作符 ...)")
        return "\n".join(lines)

    if ptype == PatternType.DICT_DESTRUCTURE:
        lines = [f"{prefix}字典解构模式:"]
        for key_pattern, val_pattern in pattern.pairs:
            key_desc = _describe_literal_key(key_pattern)
            val_type = classify_pattern(val_pattern)
            if val_type == PatternType.VARIABLE_BINDING:
                lines.append(f"{prefix}  \"{key_desc}\" => {val_pattern.name}")
            elif val_type == PatternType.WILDCARD:
                lines.append(f"{prefix}  \"{key_desc}\" => _")
            else:
                lines.append(f"{prefix}  \"{key_desc}\" =>")
                lines.append(describe_pattern(val_pattern, indent + 2))
        return "\n".join(lines)

    if ptype == PatternType.TYPE_CHECK:
        return f"{prefix}类型检查模式: 类型:{pattern.type_name}"

    if ptype == PatternType.ENUM_VARIANT:
        binding_desc = f"({pattern.binding})" if pattern.binding else ""
        return f"{prefix}枚举变体模式: {pattern.enum_name}.{pattern.variant_name}{binding_desc}"

    return f"{prefix}未知模式"


def _describe_literal_key(pattern) -> str:
    """描述字典模式中的字面量键"""
    if isinstance(pattern, StringLiteral):
        return pattern.value
    if isinstance(pattern, NumberLiteral):
        return str(pattern.value)
    if isinstance(pattern, BooleanLiteral):
        return '真' if pattern.value else '假'
    if isinstance(pattern, NullLiteral):
        return '空'
    return '?'


# ============================================================
# 模式匹配引擎
# ============================================================


class PatternMatchEngine:
    """模式匹配引擎：对运行时值进行模式匹配判断

    核心方法：
    - match(pattern, value, env=None): 对单个值进行模式匹配
    - match_with_guard(pattern, value, guard_fn, env=None): 带守卫条件的模式匹配
    - match_branches(branches, value, env=None): 按顺序匹配多个模式分支
    - match_tuple(patterns, values, env=None): 多参数元组模式匹配
    """

    def match(self, pattern, value, env=None) -> MatchResult:
        """对值进行模式匹配

        Args:
            pattern: 匹配模式AST节点
            value: 运行时值
            env: 执行环境（可选，用于守卫条件求值）

        Returns:
            MatchResult: 匹配结果，包含是否匹配、变量绑定和失败原因
        """
        # 字面量模式
        if isinstance(pattern, (NumberLiteral, StringLiteral, BooleanLiteral, NullLiteral)):
            return self._match_literal(pattern, value)

        # 通配符模式
        if isinstance(pattern, Identifier) and pattern.name == "_":
            return MatchResult.success()

        # 变量绑定模式
        if isinstance(pattern, Identifier):
            return MatchResult.success(bindings={pattern.name: value})

        # 列表解构模式
        if isinstance(pattern, ListPattern):
            return self._match_list_pattern(pattern, value)

        # 字典解构模式
        if isinstance(pattern, DictPattern):
            return self._match_dict_pattern(pattern, value)

        # 类型检查模式
        if isinstance(pattern, TypeCheckPattern):
            return self._match_type_pattern(pattern, value)

        # 枚举变体模式
        if isinstance(pattern, EnumVariantPattern):
            return self._match_enum_variant(pattern, value)

        # 其他情况：不匹配
        return MatchResult.failure(f"不支持的模式类型: {type(pattern).__name__}")

    def match_with_guard(
        self,
        pattern,
        value,
        guard_fn: Optional[Callable[[dict], bool]] = None,
        env=None,
    ) -> MatchResult:
        """带守卫条件的模式匹配

        先执行模式匹配，匹配成功后若提供了守卫函数，则将绑定变量
        传入守卫函数进行二次判断。守卫函数返回 True 时才视为最终匹配成功。

        Args:
            pattern: 匹配模式AST节点
            value: 运行时值
            guard_fn: 守卫条件函数，接收变量绑定字典，返回布尔值
            env: 执行环境（可选）

        Returns:
            MatchResult: 匹配结果
        """
        result = self.match(pattern, value, env)
        if not result.matched:
            return result

        # 匹配成功，检查守卫条件
        if guard_fn is not None:
            try:
                guard_passed = guard_fn(result.bindings)
            except Exception as e:
                return MatchResult.failure(f"守卫条件求值失败: {e}")
            if not guard_passed:
                return MatchResult.failure("守卫条件不满足")

        return result

    def match_branches(
        self,
        branches: list[PatternBranch],
        value: Any,
        guard_evaluator: Optional[Callable] = None,
        env=None,
    ) -> tuple[Optional[PatternBranch], MatchResult]:
        """按顺序匹配多个模式分支，返回第一个匹配成功的分支

        Args:
            branches: 模式分支列表（PatternBranch）
            value: 运行时值
            guard_evaluator: 守卫条件求值函数，接收 (guard_ast, bindings, env)，
                             返回布尔值。若为 None 则忽略守卫条件。
            env: 执行环境（可选）

        Returns:
            (匹配的分支, 匹配结果) 元组。若无匹配分支，分支为 None。
        """
        for branch in branches:
            result = self.match(branch.pattern, value, env)
            if not result.matched:
                continue

            # 检查守卫条件
            if branch.guard is not None and guard_evaluator is not None:
                try:
                    guard_passed = guard_evaluator(branch.guard, result.bindings, env)
                except Exception:
                    guard_passed = False
                if not guard_passed:
                    continue

            return branch, result

        return None, MatchResult.failure("所有模式分支均不匹配")

    def match_tuple(
        self,
        patterns: list,
        values: list,
        env=None,
    ) -> MatchResult:
        """多参数元组模式匹配

        对多个模式与多个值同时进行匹配，所有模式都匹配成功时
        才返回成功结果，绑定变量合并。

        Args:
            patterns: 匹配模式AST节点列表
            values: 运行时值列表
            env: 执行环境（可选）

        Returns:
            MatchResult: 合并后的匹配结果
        """
        if len(patterns) != len(values):
            return MatchResult.failure(
                f"参数数量不匹配: 期望 {len(patterns)} 个，实际 {len(values)} 个"
            )

        combined = MatchResult.success()
        for pattern, value in zip(patterns, values):
            result = self.match(pattern, value, env)
            combined = combined.merge(result)
            if not combined.matched:
                return combined

        return combined

    def _match_literal(self, pattern, value) -> MatchResult:
        """匹配字面量模式"""
        if isinstance(pattern, NumberLiteral):
            if pattern.value == value:
                return MatchResult.success()
            return MatchResult.failure(f"数值不匹配: 期望 {pattern.value}，实际 {value}")
        if isinstance(pattern, StringLiteral):
            if pattern.value == value:
                return MatchResult.success()
            return MatchResult.failure(f"字符串不匹配: 期望 \"{pattern.value}\"，实际 \"{value}\"")
        if isinstance(pattern, BooleanLiteral):
            if pattern.value == value:
                return MatchResult.success()
            return MatchResult.failure(f"布尔值不匹配: 期望 {pattern.value}，实际 {value}")
        if isinstance(pattern, NullLiteral):
            if value is None:
                return MatchResult.success()
            return MatchResult.failure(f"空值不匹配: 期望 None，实际 {value}")
        return MatchResult.failure(f"未知字面量类型: {type(pattern).__name__}")

    def _match_list_pattern(self, pattern: ListPattern, value) -> MatchResult:
        """匹配列表解构模式"""
        if not isinstance(value, list):
            return MatchResult.failure(f"列表模式不匹配: 值不是列表类型，而是 {type(value).__name__}")

        elements = pattern.elements
        has_spread = pattern.has_spread

        if not elements:
            # 空列表模式 []：匹配空列表
            if len(value) == 0:
                return MatchResult.success()
            return MatchResult.failure(f"空列表模式不匹配: 列表长度为 {len(value)}")

        if has_spread:
            # 有展开操作符：[头, ...尾]
            # 展开操作符前的固定元素 + 展开变量
            fixed_count = len(elements) - 1  # 最后一个是展开变量
            if len(value) < fixed_count:
                return MatchResult.failure(
                    f"列表长度不足: 展开操作符前需要 {fixed_count} 个元素，实际 {len(value)} 个"
                )

            bindings = {}
            # 匹配固定元素（支持嵌套模式）
            for i in range(fixed_count):
                sub_result = self.match(elements[i], value[i])
                if not sub_result.matched:
                    return MatchResult.failure(f"列表第 {i} 个元素不匹配: {sub_result.failure_reason}")
                bindings.update(sub_result.bindings)

            # 展开变量绑定剩余元素
            spread_var = elements[-1]
            if isinstance(spread_var, Identifier):
                bindings[spread_var.name] = value[fixed_count:]

            return MatchResult.success(bindings=bindings)
        else:
            # 无展开操作符：固定长度匹配
            if len(value) != len(elements):
                return MatchResult.failure(
                    f"列表长度不匹配: 期望 {len(elements)} 个元素，实际 {len(value)} 个"
                )

            bindings = {}
            for i, elem_pattern in enumerate(elements):
                sub_result = self.match(elem_pattern, value[i])
                if not sub_result.matched:
                    return MatchResult.failure(f"列表第 {i} 个元素不匹配: {sub_result.failure_reason}")
                bindings.update(sub_result.bindings)

            return MatchResult.success(bindings=bindings)

    def _match_dict_pattern(self, pattern: DictPattern, value) -> MatchResult:
        """匹配字典解构模式"""
        if not isinstance(value, dict):
            return MatchResult.failure(f"字典模式不匹配: 值不是字典类型，而是 {type(value).__name__}")

        if not pattern.pairs:
            # 空字典模式 {}：匹配任意字典
            return MatchResult.success()

        bindings = {}
        for key_pattern, val_pattern in pattern.pairs:
            # 提取键的值
            key = self._extract_literal_value(key_pattern)
            if key is None and not isinstance(key_pattern, NullLiteral):
                return MatchResult.failure(f"字典键不是字面量: {type(key_pattern).__name__}")

            # 检查键是否存在
            if key not in value:
                return MatchResult.failure(f"字典缺少键: \"{key}\"")

            # 递归匹配值（支持嵌套模式）
            sub_result = self.match(val_pattern, value[key])
            if not sub_result.matched:
                return MatchResult.failure(f"字典键 \"{key}\" 的值不匹配: {sub_result.failure_reason}")
            bindings.update(sub_result.bindings)

        return MatchResult.success(bindings=bindings)

    def _match_type_pattern(self, pattern: TypeCheckPattern, value) -> MatchResult:
        """匹配类型检查模式"""
        type_map = {
            "列表": list,
            "字典": dict,
            "数值": (int, float),
            "文本": str,
            "布尔": bool,
            "函数": callable,
        }

        target_type = type_map.get(pattern.type_name)
        if target_type is None:
            return MatchResult.failure(f"未知类型名: \"{pattern.type_name}\"")

        # 特殊处理：bool 是 int 的子类，需要排除
        if pattern.type_name == "数值" and isinstance(value, bool):
            return MatchResult.failure("类型检查不匹配: 布尔值不属于数值类型")

        if isinstance(value, target_type):
            return MatchResult.success()
        return MatchResult.failure(
            f"类型检查不匹配: 期望 类型:{pattern.type_name}，实际 {type(value).__name__}"
        )

    def _match_enum_variant(self, pattern: EnumVariantPattern, value) -> MatchResult:
        """匹配枚举变体模式

        使用统一的 DaoEnumProtocol 协议接口进行匹配，
        通过 adapt_to_enum_protocol() 将任意值适配为协议对象。
        """
        adapted = adapt_to_enum_protocol(value)
        if adapted is None:
            return MatchResult.failure(
                f"枚举变体模式不匹配: 值无法适配为枚举协议 (类型: {type(value).__name__})"
            )

        if not adapted.matches_enum(pattern.enum_name, pattern.variant_name):
            return MatchResult.failure(
                f"枚举变体不匹配: 期望 {pattern.enum_name}.{pattern.variant_name}，"
                f"实际 {adapted.dao_class_name}.{adapted.dao_variant_name}"
            )

        bindings = {}
        if pattern.binding:
            inner_value = adapted.dao_inner_value
            if inner_value is not None:
                bindings[pattern.binding] = inner_value
            else:
                # 回退：从原始值提取
                bindings[pattern.binding] = _extract_object_value(value)

        return MatchResult.success(bindings=bindings)

    def _extract_literal_value(self, pattern):
        """从字面量模式节点中提取值"""
        if isinstance(pattern, StringLiteral):
            return pattern.value
        if isinstance(pattern, NumberLiteral):
            return pattern.value
        if isinstance(pattern, BooleanLiteral):
            return pattern.value
        if isinstance(pattern, NullLiteral):
            return None
        return None
