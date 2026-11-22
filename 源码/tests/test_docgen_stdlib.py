"""stdlib docstring 补齐后的 docgen 文档生成回归测试（任务 D）。

覆盖：主要 stdlib 模块导出函数的中文描述、占位描述消除比例、
FunctionDoc 参数个数与真实可调用对象的一致性、Markdown 结构，
以及 docgen 纯读取（不修改注册表与导出对象）。
"""

import inspect
import os
import re
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from dao.stdlib.registry import (
    STDLIB_REGISTRY,
    ensure_initialized,
    get_registry,
)
from dao.tools.docgen import (
    FunctionDoc,
    collect_all,
    collect_stdlib,
    generate_docs,
    render_module_doc,
)

暂无描述 = "（暂无描述）"
改进前基线占位数量 = 84
占位允许上限 = 改进前基线占位数量 * 0.2
中文 = re.compile(r"[\u4e00-\u9fff]")
主要模块 = (
    "文本", "数学", "集合", "时间", "编码", "文件",
    "系统", "测试", "日志", "网络", "异步IO",
    "密码", "数据库", "调度", "大模型",
)


@pytest.fixture(scope="module")
def 模块表():
    """按标题索引的 stdlib ModuleDoc，供多个测试复用。"""
    return {m.title: m for m in collect_stdlib()}


def _遍历导出(name, value, prefix=""):
    """递归产出 (展平名, BuiltinFunction) 对，与 docgen 的 _add_export 规则一致。"""
    full = f"{prefix}{name}"
    if hasattr(value, "func") and hasattr(value, "param_count"):
        yield full, value
    elif isinstance(value, dict):
        for sub_name, sub_value in value.items():
            yield from _遍历导出(sub_name, sub_value, prefix=full + ".")


def test_主要模块导出函数均有中文描述(模块表):
    """主要 stdlib 模块的每个导出函数描述不再是占位且含中文。"""
    for title in 主要模块:
        assert title in 模块表
        funcs = 模块表[title].functions
        assert funcs
        assert all(isinstance(func, FunctionDoc) for func in funcs)
        for func in funcs:
            assert func.description != 暂无描述
            assert 中文.search(func.description)


def test_全部stdlib导出函数无占位描述():
    """全部 stdlib 模块导出函数规模达标且占位描述为零。"""
    modules = collect_stdlib()
    total = sum(len(m.functions) for m in modules)
    placeholders = [
        f"{m.title}.{f.name}"
        for m in modules
        for f in m.functions
        if f.description == 暂无描述
    ]
    assert len(modules) == 15
    assert total >= 100
    assert placeholders == []


def test_占位描述相比基线减少八成以上():
    """全量 collect_all 占位描述数量较改进前基线 84 减少 >= 80%。"""
    placeholders = sum(
        1
        for m in collect_all()
        for f in m.functions
        if f.description == 暂无描述
    )
    assert placeholders <= 占位允许上限


def test_参数个数与注册表中真实导出对象一致(模块表):
    """FunctionDoc 的函数名与参数个数逐一对齐注册表导出的 BuiltinFunction。"""
    ensure_initialized()
    checked = 0
    for title in get_registry():
        env = STDLIB_REGISTRY[title]()
        exports = getattr(env, "exports", None) or list(env.values)
        by_name = {f.name: f for f in 模块表[title].functions}
        for export in exports:
            if export not in env.values:
                continue
            for full, builtin in _遍历导出(export, env.values[export]):
                assert full in by_name
                expected = builtin.param_count
                if expected is None:
                    expected = -1
                assert by_name[full].param_count == int(expected)
                checked += 1
    assert checked >= 100


def test_参数个数与Python可调用签名相容():
    """定长参数函数的 param_count 不超过底层 Python 可调用对象的形参数。"""
    ensure_initialized()
    checked = 0
    for title in get_registry():
        env = STDLIB_REGISTRY[title]()
        for export in list(env.values):
            for _full, builtin in _遍历导出(export, env.values[export]):
                if builtin.param_count is None or builtin.param_count < 0:
                    continue
                params = inspect.signature(builtin.func).parameters
                assert int(builtin.param_count) <= len(params)
                checked += 1
    assert checked >= 50


def test_生成Markdown含模块标题与函数表(模块表):
    """generate_docs 与 render_module_doc 均产出含模块标题与函数表的 Markdown。"""
    docs = generate_docs()
    assert len(docs) == 17
    for title, text in docs.items():
        assert text.startswith(f"# {title}\n")
        assert "## 函数" in text
        assert "| 函数名 | 参数个数 | 描述 |" in text
        assert "| --- | --- | --- |" in text
        assert text.endswith("\n")
    for title in 主要模块:
        assert 暂无描述 not in docs[title]
        assert docs[title] == render_module_doc(模块表[title])


def test_docgen纯读取不修改注册表():
    """生成文档不改动注册表键、工厂函数、导出集合与底层可调用对象/docstring。"""
    ensure_initialized()
    before = get_registry()
    before_keys = tuple(before.keys())
    before_ids = {k: id(v) for k, v in before.items()}
    before_exports = {}
    for name, factory in before.items():
        env = factory()
        before_exports[name] = {
            key: (
                getattr(value, "func", None),
                getattr(value, "param_count", None),
                getattr(getattr(value, "func", None), "__doc__", None),
            )
            for key, value in env.values.items()
        }

    first = generate_docs()
    collect_stdlib()
    collect_all()
    second = generate_docs()
    assert first == second

    after = get_registry()
    assert tuple(after.keys()) == before_keys
    assert {k: id(v) for k, v in after.items()} == before_ids
    for name, factory in after.items():
        env = factory()
        assert set(env.values) == set(before_exports[name])
        for key, value in env.values.items():
            old_func, old_count, old_doc = before_exports[name][key]
            assert getattr(value, "func", None) is old_func
            assert getattr(value, "param_count", None) == old_count
            if old_func is not None:
                assert old_func.__doc__ == old_doc
