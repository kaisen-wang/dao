"""
模式穷尽性检查器
================

分析模式匹配宏的模式分支覆盖范围，当所有分支无法覆盖所有可能的输入时发出警告。

检查策略：
1. 通配符/变量绑定检查：如果最后一个分支是通配符或变量绑定，视为穷尽
2. 布尔类型穷尽性：检查是否同时覆盖了真和假
3. 枚举类型穷尽性：检查是否覆盖了所有枚举变体
4. 守卫条件分析：有守卫条件的分支可能不穷尽
5. 缺失分支提示：建议用户补充哪些分支

警告不阻止宏注册，仅作为提示。
"""

import logging

from ..ast_nodes import (
    BooleanLiteral,
    EnumVariantPattern,
    Identifier,
    NumberLiteral,
    PatternBranch,
    StringLiteral,
    TypeCheckPattern,
)

logger = logging.getLogger('dao.macros')


class ExhaustivenessChecker:
    """模式穷尽性检查器"""

    def check(self, branches: list[PatternBranch]) -> list[str]:
        """
        检查模式分支的穷尽性

        Args:
            branches: 模式分支列表

        Returns:
            警告消息列表（空列表表示无警告）
        """
        warnings = []
        self._boolean_exhaustive = False

        if not branches:
            warnings.append("模式匹配宏没有定义任何模式分支")
            return warnings

        # 检查是否有通配符或变量绑定作为最后分支
        if self._has_catch_all(branches):
            return warnings

        # 检查布尔类型的穷尽性
        bool_warnings = self._check_boolean_exhaustiveness(branches)
        warnings.extend(bool_warnings)

        # 如果布尔类型已穷尽，不再给出通用提示
        if self._boolean_exhaustive:
            return warnings

        # 检查枚举类型的穷尽性
        enum_warnings = self._check_enum_exhaustiveness(branches)
        warnings.extend(enum_warnings)

        # 检查守卫条件的影响
        guard_warnings = self._check_guard_exhaustiveness(branches)
        warnings.extend(guard_warnings)

        # 如果没有其他警告，给出通用提示
        if not warnings:
            warnings.append(
                "模式匹配宏可能未覆盖所有情况，"
                "建议添加通配符 '_' 或变量绑定作为最后的分支"
            )

        return warnings

    def _has_catch_all(self, branches: list[PatternBranch]) -> bool:
        """检查是否有通配符或变量绑定分支"""
        for branch in branches:
            pattern = branch.pattern
            # 变量绑定模式（如 x）可以匹配任何值
            if isinstance(pattern, Identifier) and pattern.name != "_":
                # 但如果有守卫条件，则不一定穷尽
                if branch.guard is None:
                    return True
            # 通配符模式
            if isinstance(pattern, Identifier) and pattern.name == "_":
                return True
        return False

    def _check_boolean_exhaustiveness(self, branches: list[PatternBranch]) -> list[str]:
        """检查布尔类型的穷尽性

        如果所有分支都是布尔字面量，检查是否同时覆盖了真和假。
        如果布尔类型已穷尽（同时覆盖真和假），返回空列表且标记为穷尽。
        """
        warnings = []
        bool_values = set()
        non_bool_count = 0

        for branch in branches:
            pattern = branch.pattern
            if isinstance(pattern, BooleanLiteral):
                bool_values.add(pattern.value)
            else:
                non_bool_count += 1

        # 如果有布尔模式但未覆盖全部
        if bool_values and len(bool_values) < 2:
            missing = []
            if True not in bool_values:
                missing.append("真")
            if False not in bool_values:
                missing.append("假")
            if missing:
                warnings.append(
                    f"布尔模式未覆盖所有情况，缺少: {', '.join(missing)}"
                )

        # 如果布尔类型已穷尽（同时覆盖真和假）且没有非布尔分支，
        # 标记为穷尽，阻止通用提示
        if len(bool_values) == 2 and non_bool_count == 0:
            self._boolean_exhaustive = True

        return warnings

    def _check_enum_exhaustiveness(self, branches: list[PatternBranch]) -> list[str]:
        """检查枚举类型的穷尽性

        如果所有分支都是同一枚举的变体，检查是否覆盖了所有变体。
        注意：由于在宏展开阶段无法获取枚举定义，只能检查已知变体。
        """
        warnings = []
        enum_variants = {}  # enum_name -> set of variant_names

        for branch in branches:
            pattern = branch.pattern
            if isinstance(pattern, EnumVariantPattern):
                enum_name = pattern.enum_name
                variant_name = pattern.variant_name
                if enum_name not in enum_variants:
                    enum_variants[enum_name] = set()
                enum_variants[enum_name].add(variant_name)

        # 对于枚举变体模式，如果只有部分变体被覆盖，给出提示
        for enum_name, variants in enum_variants.items():
            # 无法确定枚举的总变体数，但可以提示已覆盖的变体
            logger.debug(
                "枚举 '%s' 已覆盖变体: %s", enum_name, ", ".join(variants)
            )

        return warnings

    def _check_guard_exhaustiveness(self, branches: list[PatternBranch]) -> list[str]:
        """检查守卫条件对穷尽性的影响

        有守卫条件的分支可能不匹配，即使模式本身匹配。
        """
        warnings = []
        guarded_branches = [b for b in branches if b.guard is not None]

        if guarded_branches and not self._has_catch_all(branches):
            warnings.append(
                f"存在 {len(guarded_branches)} 个带守卫条件的分支，"
                "守卫条件可能不满足，建议添加通配符分支作为兜底"
            )

        return warnings
