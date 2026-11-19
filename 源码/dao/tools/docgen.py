"""道语言 API 文档生成器（P3）
============================

从内置函数注册表（``dao.builtins``）与标准库模块（``dao.stdlib``）的
``create_module_env()`` 导出信息中提取函数签名（参数个数）与描述
（docstring，中文优先），生成 Markdown API 文档。

设计要点：
    * 纯读取：不修改任何注册表、可调用对象或环境对象。
    * 数据源统一：函数名取导出名，参数个数取 ``param_count``（``-1``
      表示可变参数），描述取 ``func.__doc__`` 的首行/首句。
    * stdlib 中的嵌套命名空间（如 ``编码.JSON``）会展平为
      ``JSON.编码`` 这样的名称；常量/类型单独成表。

命令行用法::

    python -m dao.tools.docgen                 # 所有模块输出到 stdout
    python -m dao.tools.docgen -m 数学          # 仅输出指定模块
    python -m dao.tools.docgen -o 文档/api      # 每模块一个 .md 文件
"""

from __future__ import annotations

import argparse
import re
import sys
from dataclasses import dataclass
from pathlib import Path

from ..builtins.functions import get_builtins
from ..builtins.hof import get_interpreter_builtins
from ..stdlib.registry import STDLIB_REGISTRY, ensure_initialized

# 内置函数分组的文档标题
标题_基础内置 = "基础内置函数"
标题_高阶内置 = "高阶内置函数"

_可变参数 = "可变参数"
_暂无描述 = "（暂无描述）"
_HAN_RE = re.compile(r"[\u4e00-\u9fff]")


@dataclass(frozen=True)
class FunctionDoc:
    """单个函数的文档信息。"""

    name: str
    param_count: int
    description: str

    @property
    def arity_text(self) -> str:
        """文档展示用的参数个数：``-1`` 显示为“可变参数”。"""
        return _可变参数 if self.param_count < 0 else str(self.param_count)


@dataclass(frozen=True)
class ConstantDoc:
    """非函数导出（常量、类型等）的文档信息。"""

    name: str
    value_repr: str
    type_name: str


@dataclass(frozen=True)
class ModuleDoc:
    """一个模块（或内置函数分组）的完整文档信息。"""

    title: str
    functions: tuple[FunctionDoc, ...] = ()
    constants: tuple[ConstantDoc, ...] = ()


def _extract_description(func) -> str:
    """从可调用对象的 docstring 提取简洁描述，中文行优先。"""
    if func is None:
        return _暂无描述
    doc = getattr(func, "__doc__", None)
    if not doc:
        return _暂无描述
    lines = [line.strip() for line in doc.strip().splitlines() if line.strip()]
    if not lines:
        return _暂无描述
    chinese_lines = [line for line in lines if _HAN_RE.search(line)]
    chosen = chinese_lines[0] if chinese_lines else lines[0]
    # 截取第一句（中文句号结尾），保持描述简洁；无句号则保留整行
    end = chosen.find("。")
    if end != -1:
        chosen = chosen[: end + 1]
    return chosen


def _function_from_callable(name: str, value) -> FunctionDoc:
    """把一个 BuiltinFunction / InterpreterBuiltin 转成 FunctionDoc。"""
    param_count = getattr(value, "param_count", -1)
    if param_count is None:
        param_count = -1
    return FunctionDoc(
        name=name,
        param_count=int(param_count),
        description=_extract_description(getattr(value, "func", None)),
    )


def _add_export(name, value, functions: list, constants: list, prefix: str = "") -> None:
    """递归收集一个导出项：函数展平，常量/类型单独记录。"""
    full_name = f"{prefix}{name}"
    if hasattr(value, "func") and hasattr(value, "param_count"):
        functions.append(_function_from_callable(full_name, value))
    elif isinstance(value, dict):
        for sub_name, sub_value in value.items():
            _add_export(sub_name, sub_value, functions, constants, prefix=full_name + ".")
    else:
        constants.append(
            ConstantDoc(
                name=full_name,
                value_repr=repr(value),
                type_name=type(value).__name__,
            )
        )


def collect_builtins() -> ModuleDoc:
    """收集基础内置函数（``get_builtins``）。"""
    functions = tuple(
        _function_from_callable(name, value) for name, value in get_builtins().items()
    )
    return ModuleDoc(标题_基础内置, functions)


def collect_hof() -> ModuleDoc:
    """收集高阶内置函数（``get_interpreter_builtins``）。"""
    functions = tuple(
        _function_from_callable(name, value)
        for name, value in get_interpreter_builtins().items()
    )
    return ModuleDoc(标题_高阶内置, functions)


def collect_stdlib() -> list[ModuleDoc]:
    """收集所有标准库模块的导出函数与常量。"""
    ensure_initialized()
    modules: list[ModuleDoc] = []
    for name in STDLIB_REGISTRY.keys():
        env = STDLIB_REGISTRY[name]()
        functions: list[FunctionDoc] = []
        constants: list[ConstantDoc] = []
        exports = getattr(env, "exports", None) or list(env.values)
        for export in exports:
            if export in env.values:
                _add_export(export, env.values[export], functions, constants)
        modules.append(ModuleDoc(name, tuple(functions), tuple(constants)))
    return modules


def collect_all() -> list[ModuleDoc]:
    """收集所有模块：基础内置、高阶内置，以及全部标准库模块。"""
    return [collect_builtins(), collect_hof(), *collect_stdlib()]


def _escape_cell(text: object) -> str:
    """转义 Markdown 表格单元格中的特殊字符。"""
    return str(text).replace("|", "\\|").replace("\n", " ")


def render_module_doc(module: ModuleDoc) -> str:
    """把一个 ModuleDoc 渲染为 Markdown 文本。"""
    lines = [f"# {module.title}", ""]
    if module.functions:
        lines += [
            "## 函数",
            "",
            "| 函数名 | 参数个数 | 描述 |",
            "| --- | --- | --- |",
        ]
        for func in module.functions:
            lines.append(
                f"| {_escape_cell(func.name)} | {_escape_cell(func.arity_text)} | "
                f"{_escape_cell(func.description)} |"
            )
        lines.append("")
    if module.constants:
        lines += [
            "## 常量与类型",
            "",
            "| 名称 | 类型 | 值 |",
            "| --- | --- | --- |",
        ]
        for const in module.constants:
            lines.append(
                f"| {_escape_cell(const.name)} | {_escape_cell(const.type_name)} | "
                f"{_escape_cell(const.value_repr)} |"
            )
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def generate_docs() -> dict[str, str]:
    """生成所有模块的 Markdown 文档，以模块标题为键。"""
    return {module.title: render_module_doc(module) for module in collect_all()}


def _safe_filename(title: str) -> str:
    """把模块标题转成安全的文件名。"""
    return re.sub(r"[^\w\u4e00-\u9fff]+", "_", title).strip("_") + ".md"


def main(argv: list[str] | None = None) -> int:
    """命令行入口。"""
    parser = argparse.ArgumentParser(
        prog="python -m dao.tools.docgen",
        description="从道语言内置函数与标准库生成 Markdown API 文档",
    )
    parser.add_argument(
        "-o",
        "--output",
        type=Path,
        help="输出目录；每个模块生成一个 .md 文件。不指定则输出到 stdout",
    )
    parser.add_argument(
        "-m",
        "--module",
        help="仅生成指定模块（按标题，如：数学、基础内置函数）",
    )
    args = parser.parse_args(argv)

    docs = generate_docs()
    if args.module:
        if args.module not in docs:
            print(
                f"错误：未找到模块“{args.module}”。可用模块：{'、'.join(docs)}",
                file=sys.stderr,
            )
            return 1
        docs = {args.module: docs[args.module]}

    if args.output is None:
        sys.stdout.write("\n".join(docs.values()))
        return 0

    out_dir = args.output
    out_dir.mkdir(parents=True, exist_ok=True)
    for title, text in docs.items():
        (out_dir / _safe_filename(title)).write_text(text, encoding="utf-8")
    print(f"已生成 {len(docs)} 个文档到 {out_dir}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
