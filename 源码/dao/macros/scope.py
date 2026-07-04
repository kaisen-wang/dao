"""
宏作用域管理
============

管理宏展开过程中的变量作用域，提供变量捕获分析和变量重写功能。

宏作用域管理的核心功能：
1. 分析变量的定义和使用
2. 检测变量捕获问题
3. 生成唯一的变量名
4. 应用变量重写
5. 管理作用域链

主要数据结构：
- VariableInfo：变量信息
- ScopeNode：作用域节点
- ScopeChain：作用域链

主要算法：
1. 变量作用域分析
2. 变量捕获检测
3. 卫生标识符生成
4. 变量重写
"""

from dataclasses import dataclass
from typing import Dict, List, Optional, Set


@dataclass
class VariableInfo:
    """变量信息数据类"""

    name: str
    is_bound: bool = False
    definition_line: int = -1
    used_lines: List[int] = None

    def __init__(self, name: str, is_bound: bool = False, definition_line: int = -1):
        self.name = name
        self.is_bound = is_bound
        self.definition_line = definition_line
        self.used_lines = []

    def add_use(self, line: int):
        """添加变量使用位置"""
        if line not in self.used_lines:
            self.used_lines.append(line)


@dataclass
class ScopeNode:
    """作用域节点"""

    name: str = ""
    variables: Dict[str, VariableInfo] = None
    children: List["ScopeNode"] = None
    parent: Optional["ScopeNode"] = None
    line: int = -1

    def __init__(self, name: str = "", line: int = -1):
        self.name = name
        self.variables = {}
        self.children = []
        self.parent = None
        self.line = line

    def add_variable(
        self, name: str, is_bound: bool = False, definition_line: int = -1
    ):
        """添加变量到作用域"""
        if name not in self.variables:
            self.variables[name] = VariableInfo(name, is_bound, definition_line)

    def has_variable(self, name: str) -> bool:
        """检查变量是否在当前作用域中定义"""
        return name in self.variables

    def get_variable(self, name: str) -> Optional[VariableInfo]:
        """获取变量信息（仅检查当前作用域）"""
        return self.variables.get(name)

    def lookup_variable(self, name: str) -> Optional[VariableInfo]:
        """查找变量（沿着作用域链向上查找）"""
        current = self
        while current:
            if name in current.variables:
                return current.variables[name]
            current = current.parent
        return None

    def add_child(self, child: "ScopeNode"):
        """添加子作用域"""
        child.parent = self
        self.children.append(child)


class MacroScope:
    """宏作用域管理类"""

    def __init__(self, root_name: str = "root"):
        self.root = ScopeNode(root_name)
        self.current = self.root
        self.line_counter = 0

    def enter_scope(self, name: str = "scope"):
        """进入新的作用域"""
        new_scope = ScopeNode(name, self.line_counter)
        self.current.add_child(new_scope)
        self.current = new_scope
        self.line_counter += 1

    def leave_scope(self):
        """离开当前作用域"""
        if self.current != self.root:
            self.current = self.current.parent

    def define_variable(self, name: str, is_bound: bool = False, line: int = -1):
        """在当前作用域定义变量"""
        if line == -1:
            line = self.line_counter
        self.current.add_variable(name, is_bound, line)

    def use_variable(self, name: str, line: int = -1):
        """记录变量使用位置"""
        if line == -1:
            line = self.line_counter
        variable = self.current.lookup_variable(name)
        if variable:
            variable.add_use(line)
        else:
            # 如果变量未定义，视为自由变量
            self.current.add_variable(name, False, -1)

    def get_used_variables(self) -> List[VariableInfo]:
        """获取当前作用域链中所有被使用的变量"""
        used = []
        processed = set()

        def collect_variables(scope: ScopeNode):
            for var_name, info in scope.variables.items():
                if var_name not in processed and info.used_lines:
                    processed.add(var_name)
                    used.append(info)
            for child in scope.children:
                collect_variables(child)

        collect_variables(self.root)
        return used

    def get_free_variables(self) -> List[VariableInfo]:
        """获取自由变量（未在作用域中定义但被使用的变量）"""
        free = []
        processed = set()

        def collect_free(scope: ScopeNode):
            for var_name, info in scope.variables.items():
                if var_name not in processed and not info.is_bound:
                    processed.add(var_name)
                    free.append(info)
            for child in scope.children:
                collect_free(child)

        collect_free(self.root)
        return free

    def analyze_captures(self) -> List[VariableInfo]:
        """分析可能被宏捕获的变量

        基于作用域链分析捕获风险：
        - 自由变量（未在宏作用域中定义）可能被外部环境捕获
        - 跨作用域引用的变量有更高的捕获风险
        - 绑定变量（宏内部定义的）不会产生捕获问题
        """
        captures = []
        free_vars = self.get_free_variables()

        for var in free_vars:
            # 检查变量是否在多个作用域中被引用
            scope_count = self._count_scope_references(var.name)
            if scope_count > 1:
                # 跨作用域引用，有捕获风险
                captures.append(var)
            elif not var.is_bound and var.definition_line == -1:
                # 完全未定义的自由变量，有捕获风险
                captures.append(var)

        return captures

    def _count_scope_references(self, var_name: str) -> int:
        """统计变量在多少个不同作用域中被引用

        Args:
            var_name: 变量名

        Returns:
            引用该变量的作用域数量
        """
        count = 0

        def check_scope(scope: ScopeNode):
            nonlocal count
            if var_name in scope.variables and scope.variables[var_name].used_lines:
                count += 1
            for child in scope.children:
                check_scope(child)

        check_scope(self.root)
        return count

    def analyze_capture_risk(self) -> Dict[str, str]:
        """分析变量捕获风险等级

        Returns:
            Dict[str, str]: 变量名到风险等级的映射
            风险等级：
            - "高": 跨作用域引用的自由变量，极易被捕获
            - "中": 未定义的自由变量，可能被捕获
            - "低": 仅在单一作用域使用的自由变量
        """
        risk_map = {}
        free_vars = self.get_free_variables()
        bound_var_names = {var.name for var in self.get_used_variables() if var.is_bound}

        for var in free_vars:
            scope_count = self._count_scope_references(var.name)

            if scope_count > 1:
                risk_map[var.name] = "高"
            elif var.definition_line == -1 and var.name not in bound_var_names:
                risk_map[var.name] = "中"
            else:
                risk_map[var.name] = "低"

        return risk_map

    def generate_unique_name(self, base_name: str, scope: ScopeNode = None) -> str:
        """
        生成唯一的变量名，避免变量捕获问题

        Args:
            base_name: 基础变量名
            scope: 作用域（None表示当前作用域）

        Returns:
            str: 唯一变量名
        """
        if scope is None:
            scope = self.current

        # 检查基础名称是否已使用
        count = 1
        candidate = base_name
        while scope.lookup_variable(candidate) is not None:
            candidate = f"{base_name}_{count}"
            count += 1

        return candidate

    def rewrite_variable(self, old_name: str, new_name: str):
        """重写变量名（在整个作用域链中）"""

        def rewrite_in_scope(scope: ScopeNode):
            if old_name in scope.variables:
                # 更新变量信息
                info = scope.variables.pop(old_name)
                info.name = new_name
                scope.variables[new_name] = info
            for child in scope.children:
                rewrite_in_scope(child)

        rewrite_in_scope(self.root)

    def apply_hygiene(self) -> Dict[str, str]:
        """
        应用卫生宏处理，重写可能被捕获的变量

        Returns:
            Dict[str, str]: 变量重写映射表
        """
        captures = self.analyze_captures()
        rewrite_map = {}

        for var in captures:
            # 为可能被捕获的变量生成唯一名称
            unique_name = self.generate_unique_name(var.name)
            self.rewrite_variable(var.name, unique_name)
            rewrite_map[var.name] = unique_name

        return rewrite_map

    def print_scope_tree(self, scope: ScopeNode = None, indent: int = 0):
        """打印作用域树（调试用途）"""
        if scope is None:
            scope = self.root

        indent_str = "  " * indent
        print(f"{indent_str}作用域: {scope.name}")
        print(f"{indent_str}变量: {', '.join([var for var in scope.variables.keys()])}")
        for child in scope.children:
            self.print_scope_tree(child, indent + 1)

    def __str__(self):
        return f"MacroScope(变量数={len(self.get_used_variables())}, 自由变量={len(self.get_free_variables())})"
