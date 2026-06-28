"""
模式穷尽性检查器
================

分析模式匹配宏的模式分支覆盖范围，当所有分支无法覆盖所有可能的输入时发出警告。

检查策略：
- 如果最后一个分支是通配符模式 `_` 或变量绑定模式（Identifier），视为穷尽
- 否则发出穷尽性警告
- 警告不阻止宏注册，仅作为提示
"""

import logging

from ..ast_nodes import Identifier, PatternBranch, TypeCheckPattern

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

        if not branches:
            warnings.append("模式匹配宏没有定义任何模式分支")
            return warnings

        last_branch = branches[-1]
        last_pattern = last_branch.pattern

        # 如果最后一个分支是通配符或变量绑定，视为穷尽
        if isinstance(last_pattern, Identifier):
            return warnings  # 穷尽

        # 如果最后一个分支是类型检查模式，也视为穷尽（因为可以覆盖所有类型）
        # 注意：这里只是简单检查，更精确的穷尽性分析需要更复杂的逻辑

        # 否则发出警告
        warnings.append(
            "模式匹配宏可能未覆盖所有情况，"
            "建议添加通配符 '_' 或变量绑定作为最后的分支"
        )
        return warnings
