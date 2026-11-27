"""
LSP 语言特性实现
================

提供与具体传输、服务器状态无关的纯函数，供 :mod:`dao.lsp.server` 调用：

- :func:`compute_diagnostics` : 词法 / 语法诊断
- :func:`completion_list`      : 关键字、内置函数、标准库模块、文档标识符补全（可按前缀过滤）
- :func:`completion_resolve`   : 补全项的惰性详情回填
- :func:`hover_info`           : 关键字、内置函数、标准库模块及用户声明的中文说明
- :func:`document_symbols`     : 基于 AST 的文档符号（含嵌套与控制流内的子符号）
- :func:`definition_locations` : 当前文档内 + 跨文件的定义跳转（解析 ``导入`` 语句）
- :func:`reference_locations`  : 工作区内某符号的全部引用位置
- :func:`prepare_rename` / :func:`rename_edits` : 重命名范围校验与工作区编辑
- :func:`format_document`     : 基于缩进的源码规范化（复用 :mod:`dao.lsp.formatting`）
- :func:`build_workspace_index` / :func:`resolve_import_target` : 工作区索引与模块路径解析
- :func:`word_at` / :func:`word_prefix_at` : 取光标处的词 / 词前缀

设计要点：

- 对 ``Lexer`` / ``Parser`` 的调用都做异常兜底，源码有错时绝不向外抛异常，
  解析失败仍尽量返回已有信息（例如补全的静态候选与正则提取的标识符）；
- LSP 行列是 **0-based**，而道语言错误与 AST 的行列是 **1-based**，统一转换；
- 所有用户可见文字一律使用中文。
"""

import os
import re
from pathlib import Path
from urllib.parse import unquote, urlparse

from dao.ast_nodes import (
    AbstractDecl,
    AsyncFunctionDecl,
    ClassDecl,
    EnumDecl,
    ExportStmt,
    FunctionDecl,
    ImportStmt,
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
from .formatting import _is_protected, _protected_spans, format_source

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
    "读字节": "读字节：从标准输入读取指定字节数，返回字节数据（字节数须为正整数）",
    "字节长度": "字节长度：返回文本的 UTF-8 编码字节数（中文字符通常占 3 字节）",
    "错误输出": "错误输出：把内容输出到标准错误流，支持「分隔符」「结尾」「刷新」参数",
    "诊断源码": "诊断源码：分析源码字符串，返回含「行/列/类型/消息」的词法与语法诊断列表",
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


def uri_to_path(uri: str) -> str | None:
    """把文件 URI（或裸路径）解码成规范化本地路径，失败返回 ``None``。

    ``file:///tmp/%E9%81%93/main.道`` 中的百分号编码会还原成中文，供
    ``initialize`` 解析 ``workspaceFolders`` / ``rootUri`` 使用。
    """
    if not uri or not isinstance(uri, str):
        return None
    parsed = urlparse(uri)
    if parsed.scheme == "file":
        path = unquote(parsed.path)
    elif uri.startswith(("/", "\\")):
        path = unquote(uri)
    else:
        return None
    # Windows 盘符 URI（file:///C:/x）去掉开头多余斜杠。
    if os.name == "nt" and re.match(r"^/[A-Za-z]:", path):
        path = path[1:]
    return os.path.normpath(path)


def _path_to_uri(path: str) -> str:
    """把本地路径转成 percent-encoded 的 ``file://`` URI。"""
    return Path(os.path.abspath(path)).as_uri()


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


# 用户声明节点 -> CompletionItemKind（静态候选仍沿用文件中既定的常量值）
_USER_COMPLETION_KINDS = {
    FunctionDecl: 3,       # Function
    AsyncFunctionDecl: 3,  # Function
    MacroDefinition: 3,    # Function
    LogicBlock: 9,         # Module
    ClassDecl: 7,          # Class
    AbstractDecl: 7,       # Class
    TraitDecl: 8,          # Interface
    EnumDecl: 13,          # Enum
    VariableDecl: _变量,
    TypeAliasDecl: _变量,
}

# 作用域候选的优先级：数字越小越靠前。
_TIER_LOCAL = 0   # 局部变量 / 函数参数
_TIER_USER = 1    # AST 收集到的用户声明
_TIER_STATIC = 2  # 关键字 / 内置函数 / 标准库模块
_TIER_WORDS = 3   # 正则提取的文档标识符（最低优先级）


def _local_completion_symbols(source: str, line: int, character: int) -> dict[str, dict]:
    """提取光标之前的局部变量与函数参数（作用域相关性最高的候选）。

    这是基于文本的近似：扫描光标行及之前的代码，识别 ``函数 名(参数...)``
    的参数以及 ``定义`` / ``设`` / ``常量`` 声明的变量。错误源码下同样安全。
    """
    result: dict[str, dict] = {}
    for index, text in enumerate((source or "").splitlines()):
        if index > line:
            break
        stripped = text.strip()
        # 函数 / 异步函数的参数列表。
        match = re.match(
            r"(?:异步\s+)?函数\s+[^\W\d_][\w]*\s*\(([^)]*)\)", stripped
        )
        if match:
            for part in match.group(1).split(","):
                name = part.strip().split("=", 1)[0].strip()
                if name and _WORD_RE.fullmatch(name):
                    result.setdefault(
                        name,
                        {
                            "label": name,
                            "kind": _变量,
                            "detail": "函数参数",
                            "documentation": f"当前作用域的函数参数：{name}",
                        },
                    )
        # 局部变量声明（含光标所在行，便于输入到一半时补全）。
        match = re.match(r"(?:定义|设|常量)\s+([^\W\d_][\w]*)\s*=", stripped)
        if match:
            name = match.group(1)
            result.setdefault(
                name,
                {
                    "label": name,
                    "kind": _变量,
                    "detail": "局部变量",
                    "documentation": f"当前作用域的变量：{name}",
                },
            )
    return result


def completion_list(
    source: str,
    prefix: str = "",
    context: dict | None = None,
    position: tuple[int, int] | None = None,
) -> dict:
    """返回补全候选（CompletionList），按作用域相关性排序并去重。

    候选分层（优先级从高到低）：局部变量 / 函数参数 → AST 用户声明 →
    静态候选（关键字 / 内置 / 标准库）→ 正则提取的文档标识符。同名项只保留
    最高优先级的一份。``prefix`` 非空时按 ``label`` 前缀过滤。

    ``context`` 是 LSP 的 ``CompletionContext``；当 ``triggerKind == 2``
    （由触发字符唤起）时，会丢弃最低优先级的「文档中的标识符」，避免触发
    场景下出现大量噪声候选。``position`` 是 LSP 0-based ``(line, character)``，
    决定哪些局部变量 / 参数已进入作用域；不传时按文件末尾处理。解析失败时
    仍返回静态候选，绝不抛异常。

    ``isIncomplete`` 恒为 ``False``：候选已一次性完整给出，客户端可据
    ``label`` 二次筛选，无需再次请求补齐。
    """
    context = context if isinstance(context, dict) else {}
    triggered = context.get("triggerKind") == 2

    sources: list[tuple[str, dict, int]] = []

    def _add(item: dict, tier: int) -> None:
        if isinstance(item, dict) and item.get("label"):
            sources.append((str(item["label"]), item, tier))

    # 局部变量 / 函数参数（最高优先级）。未给坐标时按文件末尾处理。
    cursor_line, cursor_char = position if position is not None else (len((source or "").splitlines()), 0)
    for item in _local_completion_symbols(source, cursor_line, cursor_char).values():
        _add(item, _TIER_LOCAL)
    # AST 用户声明。
    for name, node in _user_symbols(source).items():
        label = _USER_KIND_LABELS.get(type(node), "声明")
        _add(
            {
                "label": name,
                "kind": _USER_COMPLETION_KINDS.get(type(node), _变量),
                "detail": label,
                "documentation": _signature_for(node),
            },
            _TIER_USER,
        )
    # 静态候选。
    for item in _static_completion_items().values():
        _add(item, _TIER_STATIC)
    # 文档标识符（触发字符场景下跳过，降低噪声）。
    if not triggered:
        for word in _WORD_RE.findall(source or ""):
            _add({"label": word, "kind": _变量, "detail": "文档中的标识符"}, _TIER_WORDS)

    # 去重：同名保留第一次出现（即最高优先级）的项，并记录稳定顺序。
    merged: dict[str, dict] = {}
    order: dict[str, int] = {}
    for label, item, tier in sources:
        if label in merged:
            continue
        enriched = dict(item)
        enriched["_tier"] = tier
        merged[label] = enriched
        order[label] = len(order)

    labels = [label for label in order if not prefix or label.startswith(prefix)]
    # 按作用域相关度排序，同层保持原始收集顺序。
    labels.sort(key=lambda label: (merged[label]["_tier"], order[label]))

    items = []
    for label in labels:
        item = dict(merged[label])
        item.pop("_tier", None)
        items.append(item)
    return {"isIncomplete": False, "items": items}


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
    source: str,
    line: int,
    character: int,
    uri: str,
    workspace_roots=(),
    documents=None,
) -> list[dict]:
    """查找光标处名字的定义位置（LSP Location 列表）。

    优先在当前文档内查找；找不到且提供了工作区根目录时，解析本文件的
    ``导入`` 语句跳到目标 ``.道`` 文件的符号定义（``从 模块 导入 名称``
    会按别名映射，``导入 模块`` 跳到模块文件），最后才在工作区内按名字
    兜底搜索。解析失败返回空列表，不抛异常。
    """
    word = word_at(source, line, character)
    if not word:
        return []
    locations: list[dict] = []
    _find_locations(document_symbols(source), word, uri, locations)
    if locations or not workspace_roots:
        return locations

    index = build_workspace_index(workspace_roots, documents)
    importer_path = uri_to_path(uri)
    for stmt in _import_statements(source):
        target_path = resolve_import_target(stmt.module_path, index, importer_path)
        if not target_path:
            continue
        target_uri = index["uri_by_path"][target_path]
        target_source = index["sources"][target_path]
        if stmt.is_from_import:
            for name, alias in stmt.names:
                effective = alias or name
                if effective == word:
                    _find_locations(
                        document_symbols(target_source), name, target_uri, locations
                    )
        else:
            module_name = stmt.alias or stmt.module_path.split(".")[-1]
            if module_name == word:
                # 导入模块名时跳到目标文件开头。
                locations.append(
                    {
                        "uri": target_uri,
                        "range": {
                            "start": {"line": 0, "character": 0},
                            "end": {"line": 0, "character": 0},
                        },
                    }
                )
        if locations:
            return locations

    # 兜底：工作区内按符号名查找（优先已导出的声明）。
    for relative_path in index["paths"]:
        if relative_path == importer_path:
            continue
        candidates = document_symbols(index["sources"][relative_path])
        if index["exports"][relative_path]:
            candidates = [
                symbol
                for symbol in candidates
                if symbol.get("name") in index["exports"][relative_path]
            ]
        _find_locations(candidates, word, index["uri_by_path"][relative_path], locations)
        if locations:
            break
    return locations


# ========================
# 工作区索引与引用
# ========================

# 模块级缓存：由 server 在 initialize / didOpen / didChange / didClose 时失效。
_WORKSPACE_INDEX: dict | None = None


def invalidate_workspace_index() -> None:
    """清空工作区索引缓存，下次调用 :func:`build_workspace_index` 时重建。"""
    global _WORKSPACE_INDEX
    _WORKSPACE_INDEX = None


def _import_statements(source: str) -> list[ImportStmt]:
    """提取源码顶层的 ``导入`` / ``从 ... 导入`` 语句；解析失败返回空列表。"""
    program = _parse_program(source)
    if program is None:
        return []
    return [
        stmt
        for stmt in getattr(program, "statements", [])
        if isinstance(stmt, ImportStmt)
    ]


def _discover_dao_files(roots, documents) -> dict[str, str]:
    """收集工作区内的 ``.道`` 文件，返回 ``绝对路径 -> 源码``。

    已打开文档（``documents``）的内存文本覆盖磁盘内容，使未保存的修改也
    参与跳转 / 引用分析；位于根目录之外但已打开的文档同样纳入。
    """
    files: dict[str, str] = {}
    for root in roots:
        if os.path.isfile(root):
            candidates = [root] if root.endswith(".道") else []
        elif os.path.isdir(root):
            candidates = []
            for dirpath, dirnames, filenames in os.walk(root):
                dirnames[:] = [name for name in dirnames if not name.startswith(".")]
                for filename in filenames:
                    if filename.endswith(".道"):
                        candidates.append(os.path.join(dirpath, filename))
        else:
            candidates = []
        for path in candidates:
            path = os.path.abspath(path)
            if path in files:
                continue
            try:
                with open(path, encoding="utf-8") as handle:
                    files[path] = handle.read()
            except (OSError, UnicodeError):
                continue
    for uri, source in (documents or {}).items():
        path = uri_to_path(uri)
        if path and isinstance(source, str):
            files[os.path.abspath(path)] = source
    return files


def build_workspace_index(workspace_roots=(), documents=None, refresh=False) -> dict:
    """构建（或复用）工作区索引。

    索引内容：所有 ``.道`` 文件的源码 / URI、按相对路径推导的模块名、每个
    文件的符号树、导入语句和导出名称集合。缓存签名包含根路径与文件内容的
    长度和哈希，故源码变动或显式 :func:`invalidate_workspace_index` 都会重建。
    """
    global _WORKSPACE_INDEX
    roots = [os.path.abspath(root) for root in (workspace_roots or ()) if root]
    files = _discover_dao_files(roots, documents or {})
    signature = (
        tuple(roots),
        tuple(sorted((path, len(text), hash(text)) for path, text in files.items())),
    )
    if (
        not refresh
        and _WORKSPACE_INDEX is not None
        and _WORKSPACE_INDEX.get("signature") == signature
    ):
        return _WORKSPACE_INDEX

    uri_by_path = {path: _path_to_uri(path) for path in files}
    modules: dict[str, str] = {}
    for root in roots:
        for path in files:
            if path != root and not path.startswith(root + os.sep):
                continue
            relative = os.path.relpath(path, root)
            module = relative[:-3].replace(os.sep, ".") if relative.endswith(".道") else relative.replace(os.sep, ".")
            modules.setdefault(module, path)

    symbols: dict[str, list[dict]] = {}
    imports: dict[str, list[ImportStmt]] = {}
    exports: dict[str, set[str]] = {}
    for path, text in files.items():
        symbols[path] = document_symbols(text)
        imports[path] = _import_statements(text)
        program = _parse_program(text)
        names: list[str] = []
        if program is not None:
            for stmt in getattr(program, "statements", []):
                if isinstance(stmt, ExportStmt):
                    names.extend(stmt.names)
        exports[path] = set(names)

    index = {
        "signature": signature,
        "roots": tuple(roots),
        "paths": tuple(sorted(files)),
        "sources": files,
        "uri_by_path": uri_by_path,
        "path_by_uri": {uri: path for path, uri in uri_by_path.items()},
        "modules": modules,
        "symbols": symbols,
        "imports": imports,
        "exports": exports,
    }
    _WORKSPACE_INDEX = index
    return index


def resolve_import_target(module_path: str, index: dict, importer_path=None) -> str | None:
    """解析 import 的模块路径到工作区内 ``.道`` 文件的绝对路径。

    搜索顺序：索引中的模块名映射 → 导入文件所在目录 → 各工作区根 →
    当前工作目录（与解释器 ``exec_import`` 的搜索顺序一致）。标准库模块
    不参与本地解析。
    """
    target = index.get("modules", {}).get(module_path)
    if target:
        return target
    if module_path in _stdlib_names():
        return None
    relative = module_path.replace(".", os.sep) + ".道"
    search_dirs: list[str] = []
    if importer_path:
        search_dirs.append(os.path.dirname(importer_path))
    search_dirs.extend(index.get("roots", ()))
    search_dirs.append(os.getcwd())
    known = set(index.get("paths", ()))
    for directory in search_dirs:
        candidate = os.path.abspath(os.path.join(directory, relative))
        if candidate in known or os.path.isfile(candidate):
            return candidate
    return None


def reference_locations(
    source: str,
    line: int,
    character: int,
    uri: str,
    workspace_roots=(),
    documents=None,
) -> list[dict]:
    """返回工作区内光标处符号的全部引用位置（含声明，符合 includeDeclaration 默认行为）。"""
    word = word_at(source, line, character)
    if not word or not workspace_roots:
        return []
    index = build_workspace_index(workspace_roots, documents)
    locations: list[dict] = []
    for path, text in index["sources"].items():
        file_uri = index["uri_by_path"][path]
        for match in _WORD_RE.finditer(text):
            if match.group() != word:
                continue
            start_offset = match.start()
            line_no = text.count("\n", 0, start_offset)
            last_newline = text.rfind("\n", 0, start_offset)
            char_no = start_offset - (last_newline + 1)
            end_char = char_no + len(word)
            locations.append(
                {
                    "uri": file_uri,
                    "range": {
                        "start": {"line": line_no, "character": char_no},
                        "end": {"line": line_no, "character": end_char},
                    },
                }
            )
    return locations


# ========================
# 格式化与重命名
# ========================


class 重命名错误(ValueError):
    """重命名请求参数或目标不合法；服务器将其转成带中文消息的 JSON-RPC 错误。"""


def format_document(source: str, options=None) -> str:
    """按 LSP ``FormattingOptions`` 规范化源码；不改动字符串与注释内容。

    仅采用 ``tabSize``（非法值由格式化核心回退到 4）；道语言不支持制表符，
    因此 ``insertSpaces`` 不影响结果。
    """
    options = options if isinstance(options, dict) else {}
    return format_source(source or "", options.get("tabSize", 4))


def word_range_at(source: str, line: int, character: int) -> dict | None:
    """返回光标所在词的 LSP ``Range``；空白或越界返回 ``None``。"""
    lines = (source or "").splitlines()
    if line < 0 or line >= len(lines):
        return None
    text = lines[line]
    for match in _WORD_RE.finditer(text):
        if match.start() <= character <= match.end():
            return {
                "start": {"line": line, "character": match.start()},
                "end": {"line": line, "character": match.end()},
            }
    return None


def _rename_rejection(word: str) -> str | None:
    """返回不可重命名的原因；允许时返回 ``None``。"""
    if word in KEYWORDS:
        return f"「{word}」是关键字，不能重命名"
    if word in _builtin_names():
        return f"「{word}」是内置函数，不能重命名"
    if word in _stdlib_names():
        return f"「{word}」是标准库模块名，不能重命名"
    return None


def _validate_new_name(new_name) -> str:
    """校验新名字；合法时返回它本身，否则抛出中文 :class:`重命名错误`。"""
    if not isinstance(new_name, str) or not _WORD_RE.fullmatch(new_name):
        raise 重命名错误("新名字必须是合法标识符（以中文或字母开头，仅含字母、数字、下划线）")
    reason = _rename_rejection(new_name)
    if reason is not None:
        raise 重命名错误(f"新名字不可用：{reason}")
    return new_name


def prepare_rename(source: str, line: int, character: int) -> dict:
    """``textDocument/prepareRename``：返回待重命名标识符的范围与占位文本。"""
    word = word_at(source, line, character)
    if not word:
        raise 重命名错误("光标处没有可重命名的标识符")
    reason = _rename_rejection(word)
    if reason is not None:
        raise 重命名错误(reason)
    word_range = word_range_at(source, line, character)
    if word_range is None:
        raise 重命名错误("无法确定标识符的范围")
    return {"range": word_range, "placeholder": word}


def _offset_of(source: str, line: int, character: int) -> int:
    """把 LSP 0-based 行列换算成源码下标（仅供过滤字符串 / 注释中的伪引用）。"""
    offset = 0
    for index, text_line in enumerate(source.split("\n")):
        if index == line:
            return offset + max(0, min(character, len(text_line.rstrip("\r"))))
        offset += len(text_line) + 1
    return len(source)


def _word_locations_in_source(source: str, word: str, uri: str) -> list[dict]:
    """在单份源码中按词边界收集出现位置（无工作区时的兜底范围）。"""
    spans = _protected_spans(source)
    locations: list[dict] = []
    for match in _WORD_RE.finditer(source):
        if match.group() != word or _is_protected(spans, match.start()):
            continue
        line_no = source.count("\n", 0, match.start())
        last_newline = source.rfind("\n", 0, match.start())
        char_no = match.start() - (last_newline + 1)
        locations.append(
            {
                "uri": uri,
                "range": {
                    "start": {"line": line_no, "character": char_no},
                    "end": {"line": line_no, "character": char_no + len(word)},
                },
            }
        )
    return locations


def rename_edits(
    source: str,
    line: int,
    character: int,
    new_name: str,
    uri: str,
    workspace_roots=(),
    documents=None,
) -> dict:
    """构造工作区重命名编辑（LSP ``WorkspaceEdit``）。

    范围严格限于工作区的 ``.道`` 文件；未初始化工作区时只改当前文档。
    字符串字面量与注释中的同名词会被过滤，避免误改非标识符出现。
    """
    word = word_at(source, line, character)
    if not word:
        raise 重命名错误("光标处没有可重命名的标识符")
    reason = _rename_rejection(word)
    if reason is not None:
        raise 重命名错误(reason)
    new_name = _validate_new_name(new_name)
    if new_name == word:
        return {"changes": {}}

    roots = [os.path.abspath(root) for root in (workspace_roots or ()) if root]
    if roots:
        locations = reference_locations(source, line, character, uri, roots, documents)
    else:
        locations = _word_locations_in_source(source, word, uri)

    current_path = os.path.abspath(uri_to_path(uri) or "") if uri else ""
    changes: dict[str, list[dict]] = {}
    seen: dict[str, set[tuple[int, int]]] = {}
    for location in locations:
        loc_uri = location.get("uri", "")
        path = uri_to_path(loc_uri)
        if not path:
            continue
        path = os.path.abspath(path)
        if roots:
            if not any(path == root or path.startswith(root + os.sep) for root in roots):
                continue
        elif path != current_path:
            continue
        text = (documents or {}).get(loc_uri)
        if text is None:
            try:
                with open(path, encoding="utf-8") as handle:
                    text = handle.read()
            except (OSError, UnicodeError):
                continue
        word_range = location["range"]
        start = word_range["start"]
        if _is_protected(
            _protected_spans(text), _offset_of(text, start["line"], start["character"])
        ):
            continue
        key = (start["line"], start["character"])
        bucket = seen.setdefault(loc_uri, set())
        if key in bucket:
            continue
        bucket.add(key)
        changes.setdefault(loc_uri, []).append({"range": word_range, "newText": new_name})

    for edits in changes.values():
        edits.sort(
            key=lambda edit: (
                edit["range"]["start"]["line"],
                edit["range"]["start"]["character"],
            )
        )
    return {"changes": changes}
