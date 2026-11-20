"""
LSP 语言特性实现
================

提供与具体传输、服务器状态无关的纯函数，供 :mod:`dao.lsp.server` 调用：

- :func:`compute_diagnostics` : 词法 / 语法诊断
- :func:`completion_list`      : 关键字、内置函数、标准库模块、文档标识符补全（可按前缀过滤）
- :func:`completion_resolve`   : 补全项的惰性详情回填
- :func:`hover_info`           : 关键字、内置函数、标准库模块及用户声明的中文说明
- :func:`document_symbols`     : 基于 AST 的文档符号（含嵌套与控制流内的子符号）
- :func:`definition_locations` : 当前文档内的定义跳转
- :func:`word_at` / :func:`word_prefix_at` : 取光标处的词 / 词前缀

设计要点：

- 对 ``Lexer`` / ``Parser`` 的调用都做异常兜底，源码有错时绝不向外抛异常，
  解析失败仍尽量返回已有信息（例如补全的静态候选与正则提取的标识符）；
- LSP 行列是 **0-based**，而道语言错误与 AST 的行列是 **1-based**，统一转换；
- 所有用户可见文字一律使用中文。
"""

import re

from dao.ast_nodes import (
    AbstractDecl,
    AsyncFunctionDecl,
    ClassDecl,
    EnumDecl,
    FunctionDecl,
    LogicBlock,
    MacroDefinition,
    Program,
    TraitDecl,
    TypeAliasDecl,
    VariableDecl,
)
from dao.builtins.functions import get_builtins
from dao.builtins.hof import get_interpreter_builtins
from dao.errors import 道错误
from dao.lexer import Lexer
from dao.parser import Parser
from dao.stdlib.registry import STDLIB_REGISTRY
from dao.tokens import KEYWORDS

# 标识符 / 中文词：以「非数字、非下划线的单词字符」开头，后接单词字符。
# Python 的 \w 默认包含中文，因此「我的变量」会被整体识别为一个词。
_WORD_RE = re.compile(r"[^\W\d_][\w]*")

# LSP DiagnosticSeverity / CompletionItemKind / SymbolKind 常量
_错误 = 1
_关键字 = 14
_函数 = 3
_模块 = 9
_变量 = 6
_常量 = 14  # 注意：这是 SymbolKind.Constant，与上面的 CompletionItemKind 无冲突

# 声明节点类型 -> LSP SymbolKind
# File=1 Module=2 Class=5 Interface=11 Enum=10 Function=12
# Variable=13 Constant=14 TypeParameter=26
_DECL_KINDS = {
    VariableDecl: 13,
    FunctionDecl: 12,
    AsyncFunctionDecl: 12,
    MacroDefinition: 12,
    ClassDecl: 5,
    AbstractDecl: 5,
    TraitDecl: 11,
    EnumDecl: 10,
    TypeAliasDecl: 26,
    LogicBlock: 2,
}

# 常用关键字的中文说明；未列出的关键字回退到通用说明。
KEYWORD_DOCS: dict[str, str] = {
    "定义": "声明一个变量，例如：定义 甲 = 1",
    "常量": "声明一个不可重新赋值的常量",
    "设": "为已有变量赋值",
    "函数": "声明一个函数，例如：函数 加(甲, 乙) ... 返回 甲 + 乙",
    "返回": "从函数中返回一个值",
    "如果": "条件分支：如果 条件 ... 否则 ...",
    "否则": "条件分支的「否则」分支",
    "否则如果": "多分支条件判断",
    "当": "当型循环（while）",
    "遍历": "遍历集合或范围的循环（for）",
    "在": "用于「遍历 变量 在 集合」",
    "从": "范围循环的起点",
    "到": "范围循环的终点",
    "步长": "范围循环每次递增的步长",
    "跳出": "跳出当前循环（break）",
    "继续": "直接进入下一轮循环（continue）",
    "匹配": "模式匹配语句",
    "情况": "模式匹配的一个分支",
    "产出": "从生成器产出一个值（yield）",
    "尝试": "异常处理：尝试 ... 捕获 ... 最终 ...",
    "捕获": "捕获异常的分支",
    "最终": "无论是否发生异常都会执行的收尾块",
    "抛出": "抛出一个异常",
    "断言": "断言条件成立，否则报错",
    "并且": "逻辑与（and）",
    "或者": "逻辑或（or）",
    "不是": "逻辑非（not）",
    "类型": "声明一个类（class）",
    "继承自": "声明类继承的父类",
    "实现": "声明类实现的特征",
    "特征": "声明一个特征（trait / interface）",
    "枚举": "声明一个枚举",
    "初始化": "类的构造函数",
    "本对象": "当前对象引用（this / self）",
    "父对象": "父类引用（super）",
    "导入": "导入模块",
    "导出": "导出名称供其它模块使用",
    "作为": "为导入项起别名",
    "异步": "声明异步函数",
    "等待": "等待异步结果（await）",
    "类型别名": "声明一个类型别名",
    "定义宏": "定义一个宏",
    "真": "布尔真值",
    "假": "布尔假值",
    "空": "空值（null）",
}

# 常用内置函数的中文说明；未列出的内置函数回退到通用说明。
BUILTIN_DOCS: dict[str, str] = {
    "打印": "打印：把内容输出到控制台，支持「分隔符」「结尾」参数",
    "输入": "输入：从控制台读取一行文本",
    "长度": "长度：返回字符串、列表、字典等的长度",
    "取类型": "取类型：返回值的类型名称（如 数值 / 文本 / 列表）",
    "范围": "范围：生成数值序列",
    "整数": "整数：把值转换为整数",
    "小数": "小数：把值转换为浮点数",
    "文本": "文本：把值转换为字符串",
    "集合": "集合：构造一个集合",
    "追加": "追加：向列表末尾添加元素",
    "反转": "反转：反转列表或文本",
    "包含": "包含：判断集合是否含有某元素",
    "最大值": "最大值：返回一组数中的最大值",
    "最小值": "最小值：返回一组数中的最小值",
    "绝对值": "绝对值：返回数值的绝对值",
    "映射": "映射：对集合每个元素应用函数并返回新集合（高阶函数）",
    "筛选": "筛选：保留满足谓词的元素（高阶函数）",
    "折叠": "折叠：把集合归约为单个值（高阶函数）",
    "排序": "排序：对集合排序",
    "分组": "分组：按键把元素分组",
    "查找": "查找：找到第一个满足谓词的元素",
}


# ========================
# 通用工具
# ========================


def word_at(source: str, line: int, character: int) -> str | None:
    """返回光标所在位置的词；越界或落在空白/标点上时返回 ``None``。

    ``line`` 与 ``character`` 均为 LSP 的 0-based 坐标。
    """
    lines = (source or "").splitlines()
    if line < 0 or line >= len(lines):
        return None
    text = lines[line]
    for match in _WORD_RE.finditer(text):
        if match.start() <= character <= match.end():
            return match.group()
    return None


def word_prefix_at(source: str, line: int, character: int) -> str:
    """返回光标前当前词已输入的前缀；落在空白或越界时返回空串。

    与 :func:`word_at` 不同，本函数只取词首到光标的子串。例如源码中是
    「打印」而光标停在第一个字之后时拿到「打」（而非整词「打印」），
    便于补全按用户实际输入的前缀过滤。
    """
    lines = (source or "").splitlines()
    if line < 0 or line >= len(lines):
        return ""
    text = lines[line]
    character = max(0, min(character, len(text)))
    for match in _WORD_RE.finditer(text):
        if match.start() < character <= match.end():
            return text[match.start():character]
    return ""


def _builtin_names() -> list[str]:
    """返回全部内置函数名（基础内置 + 高阶内置），异常时安全降级。"""
    try:
        return list(get_builtins().keys()) + list(get_interpreter_builtins().keys())
    # 有意宽泛捕获：错误源码时降级返回已有信息，绝不让 LSP 服务器崩溃
    except Exception:  # noqa: BLE001
        return []


def _stdlib_names() -> list[str]:
    """返回全部标准库模块名，异常时安全降级为空列表。"""
    try:
        return list(STDLIB_REGISTRY.keys())
    # 有意宽泛捕获：错误源码时降级返回已有信息，绝不让 LSP 服务器崩溃
    except Exception:  # noqa: BLE001
        return []


def _is_builtin(word: str) -> bool:
    try:
        return word in get_builtins() or word in get_interpreter_builtins()
    # 有意宽泛捕获：错误源码时降级返回已有信息，绝不让 LSP 服务器崩溃
    except Exception:  # noqa: BLE001
        return False


def _parse_program(source: str) -> Program | None:
    """尽力把源码解析为 AST；任何错误（含道错误与内部异常）都返回 ``None``。"""
    try:
        tokens = Lexer(source).tokenize()
        return Parser(tokens, source).parse()
    # 有意宽泛捕获：错误源码时降级返回已有信息，绝不让 LSP 服务器崩溃
    except Exception:  # noqa: BLE001
        return None


def _iter_child_statements(node):
    """产出节点内可能包含的所有子语句列表。

    覆盖函数 / 类的 ``body``、类 ``methods``、``如果`` / ``当`` / ``遍历`` 的
    分支体、``尝试`` 的捕获与收尾块，以及 ``匹配`` / ``选择`` 的 case 体。
    符号收集统一复用本函数，避免控制流内的声明从大纲中遗漏。
    """
    for attr in ("body", "methods", "else_body", "try_body", "finally_body"):
        sub = getattr(node, attr, None)
        if isinstance(sub, list):
            yield sub
    elif_clauses = getattr(node, "elif_clauses", None)
    if isinstance(elif_clauses, list):
        for clause in elif_clauses:
            if isinstance(clause, (tuple, list)) and len(clause) >= 2:
                sub = clause[1]
                if isinstance(sub, list):
                    yield sub
    catches = getattr(node, "catches", None)
    if isinstance(catches, list):
        for catch in catches:
            if isinstance(catch, dict):
                sub = catch.get("catch_body") or catch.get("body")
                if isinstance(sub, list):
                    yield sub
    cases = getattr(node, "cases", None)
    if isinstance(cases, list):
        for case in cases:
            sub = getattr(case, "body", None)
            if isinstance(sub, list):
                yield sub


# ========================
# 诊断
# ========================


def _diagnostic(line: int, column: int, message: str) -> dict:
    """构造一条 LSP Diagnostic，行列已经是 0-based。"""
    start = {"line": line, "character": column}
    end = {"line": line, "character": column + 1}
    return {
        "range": {"start": start, "end": end},
        "severity": _错误,
        "source": "道语言",
        "message": message,
    }


def _diagnostic_from_error(error: 道错误) -> dict:
    """把 ``道错误`` 转成诊断：1-based 行列转 0-based 并做下限钳制。

    少数词法错误（如未闭合字符串）携带的 ``line`` / ``column`` 为 0，
    直接用 ``-1`` 会得到负坐标，因此统一钳制到不小于 0。
    """
    kind = type(error).__name__ or "编译错误"
    line = max(0, (error.line or 0) - 1)
    column = max(0, (error.column or 0) - 1)
    return _diagnostic(line, column, f"{kind}：{error.message}")


def compute_diagnostics(source: str) -> list[dict]:
    """对源码做词法 + 语法分析，返回诊断列表；正确源码返回空列表。

    捕获 ``词法错误`` / ``语法错误``（均继承自 ``道错误``）并转换为中文
    诊断；即便分析器抛出非预期异常也返回一条兜底诊断，绝不向外抛异常。
    """
    try:
        tokens = Lexer(source).tokenize()
    except 道错误 as error:
        return [_diagnostic_from_error(error)]
    # 有意宽泛捕获：错误源码时降级返回已有信息，绝不让 LSP 服务器崩溃
    except Exception as error:  # noqa: BLE001
        return [_diagnostic(0, 0, f"词法分析失败：{type(error).__name__}")]
    try:
        Parser(tokens, source).parse()
    except 道错误 as error:
        return [_diagnostic_from_error(error)]
    # 有意宽泛捕获：错误源码时降级返回已有信息，绝不让 LSP 服务器崩溃
    except Exception as error:  # noqa: BLE001
        return [_diagnostic(0, 0, f"语法分析失败：{type(error).__name__}")]
    return []


# ========================
# 补全
# ========================


def _static_completion_items() -> dict[str, dict]:
    """构造静态补全项：关键字、内置函数、标准库模块。

    用 ``setdefault`` 保证重名时优先级为 关键字 > 内置函数 > 标准库模块。
    """
    items: dict[str, dict] = {}
    for word in KEYWORDS:
        items.setdefault(
            word,
            {
                "label": word,
                "kind": _关键字,
                "detail": "道语言关键字",
                "documentation": KEYWORD_DOCS.get(word, f"道语言关键字：{word}"),
            },
        )
    for name in _builtin_names():
        items.setdefault(
            name,
            {
                "label": name,
                "kind": _函数,
                "detail": "内置函数",
                "documentation": BUILTIN_DOCS.get(name, f"内置函数：{name}"),
            },
        )
    for name in _stdlib_names():
        items.setdefault(
            name,
            {
                "label": name,
                "kind": _模块,
                "detail": "标准库模块",
                "documentation": f"标准库模块：{name}，可用「从 {name} 导入 ...」引入",
            },
        )
    return items


def completion_list(source: str, prefix: str = "") -> dict:
    """返回补全候选（CompletionList）。

    不依赖源码能否解析：即便词法或语法有错，仍返回静态候选，并用正则从
    源码中提取已出现的标识符，保证「错误源码也返回已有信息」。``prefix``
    非空时按 ``label`` 前缀过滤（客户端仍可按 ``label`` 二次筛选）；不传时
    保持全量返回，返回类型仍是标准的 ``CompletionList``。
    """
    items = _static_completion_items()
    for word in _WORD_RE.findall(source or ""):
        items.setdefault(
            word,
            {
                "label": word,
                "kind": _变量,
                "detail": "文档中的标识符",
            },
        )
    values = list(items.values())
    if prefix:
        values = [
            item for item in values if str(item.get("label", "")).startswith(prefix)
        ]
    return {"isIncomplete": False, "items": values}


def completion_resolve(item: dict) -> dict:
    """为 ``completionItem/resolve`` 补全项的 ``detail`` / ``documentation``。

    客户端传来的项通常只有 ``label``；这里按静态候选表回填缺失的
    ``kind`` / ``detail`` / ``documentation``，已存在的字段一律保留。
    非字典输入或找不到对应静态候选时安全返回原项。
    """
    if not isinstance(item, dict):
        return {}
    result = dict(item)
    label = result.get("label")
    if not isinstance(label, str):
        return result
    static = _static_completion_items().get(label)
    if static is None:
        return result
    for key in ("kind", "detail", "documentation"):
        if not result.get(key) and static.get(key) is not None:
            result[key] = static[key]
    return result


# ========================
# 悬停
# ========================


def _markdown_hover(value: str) -> dict:
    return {"contents": {"kind": "markdown", "value": value}}


# 用户自定义声明类型 -> 悬停标签
_USER_KIND_LABELS = {
    FunctionDecl: "函数",
    AsyncFunctionDecl: "异步函数",
    ClassDecl: "类型",
    AbstractDecl: "抽象类型",
    TraitDecl: "特征",
    EnumDecl: "枚举",
    MacroDefinition: "宏",
    TypeAliasDecl: "类型别名",
}


def _type_name(annotation) -> str:
    """把类型注解节点转成简短类型名，取不到时返回空串。"""
    if annotation is None:
        return ""
    name = getattr(annotation, "name", None)
    if name:
        return str(name)
    types = getattr(annotation, "types", None)
    if isinstance(types, list) and types:
        return " | ".join(
            part for part in (_type_name(item) for item in types) if part
        )
    inner = getattr(annotation, "inner", None)
    if inner is not None:
        return _type_name(inner)
    target = getattr(annotation, "target_type", None)
    if target is not None:
        return _type_name(target)
    return ""


def _signature_for(node) -> str:
    """由用户声明节点生成一行可读签名。"""
    if isinstance(node, (FunctionDecl, AsyncFunctionDecl)):
        defaults = getattr(node, "default_values", None) or {}
        parts = [
            f"{param}=..." if param in defaults else str(param)
            for param in (getattr(node, "params", None) or [])
        ]
        rest = getattr(node, "rest_param", None)
        if rest:
            parts.append(f"...{rest}")
        signature = f"{getattr(node, 'name', '')}({', '.join(parts)})"
        return_type = _type_name(getattr(node, "return_type", None))
        if return_type:
            signature += f" -> {return_type}"
        label = "异步函数" if isinstance(node, AsyncFunctionDecl) else "函数"
        return f"{label} {signature}"
    if isinstance(node, (ClassDecl, AbstractDecl)):
        text = f"类型 {getattr(node, 'name', '')}"
        parent = getattr(node, "parent_name", None)
        if parent:
            text += f"，继承自 {parent}"
        traits = getattr(node, "implemented_traits", None) or []
        if traits:
            text += f"，实现 {', '.join(str(t) for t in traits)}"
        return text
    if isinstance(node, TraitDecl):
        return f"特征 {getattr(node, 'name', '')}"
    if isinstance(node, EnumDecl):
        values = getattr(node, "values", None) or []
        variants = getattr(node, "variants", None) or []
        names = [str(value) for value in values]
        names += [getattr(variant, "name", "") for variant in variants]
        tail = f"（{', '.join(n for n in names if n)}）" if names else ""
        return f"枚举 {getattr(node, 'name', '')}{tail}"
    if isinstance(node, MacroDefinition):
        params = getattr(node, "parameters", None) or []
        return f"宏 {getattr(node, 'name', '')}({', '.join(str(p) for p in params)})"
    if isinstance(node, TypeAliasDecl):
        alias = f"类型别名 {getattr(node, 'name', '')}"
        target = _type_name(getattr(node, "target_type", None))
        return f"{alias} = {target}" if target else alias
    return str(getattr(node, "name", ""))


def _collect_user_symbols(statements, out: dict) -> None:
    """递归收集有名字的用户声明，供悬停按名字查签名。"""
    for node in statements:
        if type(node) in _USER_KIND_LABELS:
            name = getattr(node, "name", None)
            if name and name not in out:
                out[name] = node
        for sub in _iter_child_statements(node):
            _collect_user_symbols(sub, out)


def _user_symbols(source: str) -> dict:
    """解析源码并收集用户声明；解析失败或内部异常时返回空字典。"""
    program = _parse_program(source)
    if program is None:
        return {}
    symbols: dict = {}
    try:
        _collect_user_symbols(getattr(program, "statements", []), symbols)
    # 有意宽泛捕获：错误源码时降级返回已有信息，绝不让 LSP 服务器崩溃
    except Exception:  # noqa: BLE001, S110
        pass
    return symbols


def hover_info(source: str, line: int, character: int) -> dict | None:
    """对关键字、内置函数、标准库模块及用户自定义声明给出中文说明。"""
    word = word_at(source, line, character)
    if not word:
        return None
    if word in KEYWORDS:
        text = KEYWORD_DOCS.get(word, f"道语言关键字：{word}")
        return _markdown_hover(f"**{word}**（关键字）\n\n{text}")
    if _is_builtin(word):
        text = BUILTIN_DOCS.get(word, f"内置函数：{word}")
        return _markdown_hover(f"**{word}**（内置函数）\n\n{text}")
    if word in _stdlib_names():
        return _markdown_hover(
            f"**{word}**（标准库模块）\n\n可用「从 {word} 导入 ...」引入。"
        )
    node = _user_symbols(source).get(word)
    if node is not None:
        label = _USER_KIND_LABELS.get(type(node), "声明")
        return _markdown_hover(f"**{word}**（{label}）\n\n`{_signature_for(node)}`")
    return None


# ========================
# 文档符号与定义跳转
# ========================


def _range_for(node, source: str, name: str) -> tuple[dict, dict]:
    """由 AST 节点的 1-based 行列构造 LSP 的 range 与 selectionRange。

    ``range`` 覆盖声明所在行，``selectionRange`` 尽量精确定位到名字本身。
    AST 只记录起始位置、不含结束位置，故以行末作为 range 的终点。
    """
    line = max(0, (node.line or 1) - 1)
    column = max(0, (node.column or 1) - 1)
    lines = (source or "").splitlines()
    text = lines[line] if 0 <= line < len(lines) else ""
    name_start = text.find(name, column)
    if name_start < 0:
        name_start = column
    selection = {
        "start": {"line": line, "character": name_start},
        "end": {"line": line, "character": name_start + len(name)},
    }
    whole = {
        "start": {"line": line, "character": column},
        "end": {"line": line, "character": max(column, len(text))},
    }
    return whole, selection


def _collect_definitions(statements, source: str, out: list[dict]) -> None:
    """递归收集声明节点，生成层次化的 DocumentSymbol 列表。

    控制流语句（``如果`` / ``当`` / ``遍历`` / ``尝试`` / ``匹配`` 等）本身
    不是声明节点，但其分支体内的声明会被提升到当前层级，从而出现在大纲中。
    """
    for node in statements:
        kind = _DECL_KINDS.get(type(node))
        name = getattr(node, "name", None)
        symbol = None
        children: list[dict] = []
        if name and kind is not None:
            if isinstance(node, VariableDecl) and node.is_constant:
                kind = _常量
            whole, selection = _range_for(node, source, name)
            symbol = {
                "name": name,
                "kind": kind,
                "range": whole,
                "selectionRange": selection,
            }
            out.append(symbol)
            target = children
        else:
            target = out
        for sub in _iter_child_statements(node):
            _collect_definitions(sub, source, target)
        if symbol is not None and children:
            symbol["children"] = children


def document_symbols(source: str) -> list[dict]:
    """返回文档中的函数 / 类 / 变量等符号；解析失败时返回空列表。"""
    program = _parse_program(source)
    if program is None:
        return []
    symbols: list[dict] = []
    _collect_definitions(getattr(program, "statements", []), source, symbols)
    return symbols


def _find_locations(symbols, word: str, uri: str, out: list[dict]) -> None:
    for symbol in symbols:
        if symbol.get("name") == word:
            out.append({"uri": uri, "range": symbol["selectionRange"]})
        children = symbol.get("children", [])
        if children:
            _find_locations(children, word, uri, out)


def definition_locations(
    source: str, line: int, character: int, uri: str
) -> list[dict]:
    """查找光标处名字在当前文档内的定义位置（Location 列表）。

    找不到或源码解析失败时返回空列表，不抛异常。
    """
    word = word_at(source, line, character)
    if not word:
        return []
    locations: list[dict] = []
    _find_locations(document_symbols(source), word, uri, locations)
    return locations
