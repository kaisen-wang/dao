"""
模式匹配引擎
============

在宏展开时对参数值进行模式匹配判断，支持多种匹配模式类型。

支持的匹配模式：
- 字面量模式：匹配特定值（数值、字符串、布尔、空值）
- 变量绑定模式：匹配任意值并绑定到变量
- 通配符模式：匹配任意值但不绑定
- 列表解构模式：匹配列表并解构元素
- 字典解构模式：匹配字典并解构键值对
- 类型检查模式：匹配特定类型的值
- 枚举变体模式：匹配枚举类型的特定变体
"""

import logging
from dataclasses import dataclass, field

from ..ast_nodes import (
    BooleanLiteral,
    DictPattern,
    EnumVariantPattern,
    Identifier,
    ListPattern,
    NullLiteral,
    NumberLiteral,
    StringLiteral,
    TypeCheckPattern,
)

logger = logging.getLogger('dao.macros')


@dataclass
class MatchResult:
    """模式匹配结果"""

    matched: bool = False
    bindings: dict = field(default_factory=dict)


class PatternMatchEngine:
    """模式匹配引擎：对运行时值进行模式匹配判断"""

    def match(self, pattern, value, env=None) -> MatchResult:
        """
        对值进行模式匹配

        Args:
            pattern: 匹配模式AST节点
            value: 运行时值
            env: 执行环境（可选）

        Returns:
            MatchResult: 匹配结果，包含是否匹配和变量绑定
        """
        # 字面量模式
        if isinstance(pattern, (NumberLiteral, StringLiteral, BooleanLiteral, NullLiteral)):
            return self._match_literal(pattern, value)

        # 通配符模式
        if isinstance(pattern, Identifier) and pattern.name == "_":
            return MatchResult(matched=True, bindings={})

        # 变量绑定模式
        if isinstance(pattern, Identifier):
            return MatchResult(matched=True, bindings={pattern.name: value})

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
        return MatchResult(matched=False, bindings={})

    def _match_literal(self, pattern, value) -> MatchResult:
        """匹配字面量模式"""
        if isinstance(pattern, NumberLiteral):
            return MatchResult(matched=(pattern.value == value), bindings={})
        if isinstance(pattern, StringLiteral):
            return MatchResult(matched=(pattern.value == value), bindings={})
        if isinstance(pattern, BooleanLiteral):
            return MatchResult(matched=(pattern.value == value), bindings={})
        if isinstance(pattern, NullLiteral):
            return MatchResult(matched=(value is None), bindings={})
        return MatchResult(matched=False, bindings={})

    def _match_list_pattern(self, pattern: ListPattern, value) -> MatchResult:
        """匹配列表解构模式"""
        if not isinstance(value, list):
            return MatchResult(matched=False, bindings={})

        elements = pattern.elements
        has_spread = pattern.has_spread

        if not elements:
            # 空列表模式 []：匹配空列表
            return MatchResult(matched=(len(value) == 0), bindings={})

        if has_spread:
            # 有展开操作符：[头, ...尾]
            # 展开操作符前的固定元素 + 展开变量
            fixed_count = len(elements) - 1  # 最后一个是展开变量
            if len(value) < fixed_count:
                return MatchResult(matched=False, bindings={})

            bindings = {}
            # 匹配固定元素
            for i in range(fixed_count):
                sub_result = self.match(elements[i], value[i])
                if not sub_result.matched:
                    return MatchResult(matched=False, bindings={})
                bindings.update(sub_result.bindings)

            # 展开变量绑定剩余元素
            spread_var = elements[-1]
            if isinstance(spread_var, Identifier):
                bindings[spread_var.name] = value[fixed_count:]

            return MatchResult(matched=True, bindings=bindings)
        else:
            # 无展开操作符：固定长度匹配
            if len(value) != len(elements):
                return MatchResult(matched=False, bindings={})

            bindings = {}
            for i, elem_pattern in enumerate(elements):
                sub_result = self.match(elem_pattern, value[i])
                if not sub_result.matched:
                    return MatchResult(matched=False, bindings={})
                bindings.update(sub_result.bindings)

            return MatchResult(matched=True, bindings=bindings)

    def _match_dict_pattern(self, pattern: DictPattern, value) -> MatchResult:
        """匹配字典解构模式"""
        if not isinstance(value, dict):
            return MatchResult(matched=False, bindings={})

        if not pattern.pairs:
            # 空字典模式 {}：匹配任意字典
            return MatchResult(matched=True, bindings={})

        bindings = {}
        for key_pattern, val_pattern in pattern.pairs:
            # 提取键的值
            key = self._extract_literal_value(key_pattern)
            if key is None:
                return MatchResult(matched=False, bindings={})

            # 检查键是否存在
            if key not in value:
                return MatchResult(matched=False, bindings={})

            # 匹配值
            sub_result = self.match(val_pattern, value[key])
            if not sub_result.matched:
                return MatchResult(matched=False, bindings={})
            bindings.update(sub_result.bindings)

        return MatchResult(matched=True, bindings=bindings)

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
            return MatchResult(matched=False, bindings={})

        # 特殊处理：bool 是 int 的子类，需要排除
        if pattern.type_name == "数值" and isinstance(value, bool):
            return MatchResult(matched=False, bindings={})

        return MatchResult(matched=(isinstance(value, target_type)), bindings={})

    def _match_enum_variant(self, pattern: EnumVariantPattern, value) -> MatchResult:
        """匹配枚举变体模式

        使用协议接口进行匹配，解耦与 OOP 内部实现的依赖：
        1. 优先使用 __dao_class__ / __variant__ 协议属性
        2. 其次尝试字典形式的 {'__type__': 'enum', '类': ..., '变体': ...}
        3. 最后尝试鸭子类型检查（具有匹配的类名属性）
        """
        # 协议1: 道语言标准枚举协议 (__dao_class__ / __variant__)
        if hasattr(value, '__dao_class__'):
            if value.__dao_class__ != pattern.enum_name:
                return MatchResult(matched=False, bindings={})
            if hasattr(value, '__variant__') and value.__variant__ != pattern.variant_name:
                return MatchResult(matched=False, bindings={})
            return self._extract_enum_binding(pattern, value)

        # 协议2: 字典形式的枚举表示
        if isinstance(value, dict):
            if value.get('__type__') == 'enum':
                if value.get('类') != pattern.enum_name:
                    return MatchResult(matched=False, bindings={})
                if value.get('变体') != pattern.variant_name:
                    return MatchResult(matched=False, bindings={})
                bindings = {}
                if pattern.binding:
                    inner_value = value.get('值')
                    if inner_value is not None:
                        bindings[pattern.binding] = inner_value
                return MatchResult(matched=True, bindings=bindings)

        # 协议3: 鸭子类型检查 - 对象有匹配的类名属性
        class_name = type(value).__name__
        if class_name == pattern.enum_name or class_name == pattern.variant_name:
            bindings = {}
            if pattern.binding:
                bindings[pattern.binding] = self._get_object_value(value)
            return MatchResult(matched=True, bindings=bindings)

        return MatchResult(matched=False, bindings={})

    def _extract_enum_binding(self, pattern: EnumVariantPattern, value) -> MatchResult:
        """从枚举实例中提取绑定变量"""
        bindings = {}
        if pattern.binding:
            bindings[pattern.binding] = self._get_object_value(value)
        return MatchResult(matched=True, bindings=bindings)

    def _get_object_value(self, value):
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
