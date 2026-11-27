"""``dao.tools.docgen`` 文档生成工具测试。

覆盖：内置函数、高阶函数、标准库模块、参数个数、Markdown 格式、
CLI 输出模式，以及“纯读取、不修改源数据”的约束。
"""

import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from dao.tools import docgen
from dao.tools.docgen import (
    FunctionDoc,
    _extract_description,
    collect_all,
    collect_builtins,
    collect_hof,
    collect_stdlib,
    generate_docs,
    render_module_doc,
)


def test_collect_builtins():
    """基础内置函数：数量、类型与中文描述。"""
    module = collect_builtins()
    assert module.title == "基础内置函数"
    assert len(module.functions) == 43
    assert all(isinstance(func, FunctionDoc) for func in module.functions)

    by_name = {func.name: func for func in module.functions}
    assert "打印" in by_name
    assert "打印函数" in by_name["打印"].description  # docstring 中文描述
    assert "输入" in by_name
    assert "取类型" in by_name
    # 新增 IO/诊断原语均带中文描述
    for 新增 in ("读字节", "字节长度", "错误输出", "诊断源码"):
        assert 新增 in by_name
        assert by_name[新增].description != "（暂无描述）"
    # 时间戳 没有 docstring，应使用占位描述
    assert by_name["时间戳"].description == "（暂无描述）"


def test_collect_hof():
    """高阶内置函数：数量与关键函数。"""
    module = collect_hof()
    assert module.title == "高阶内置函数"
    assert len(module.functions) == 15
    names = {func.name for func in module.functions}
    assert {"映射", "筛选", "折叠", "柯里化", "组合", "管道组合"} <= names
    assert all(isinstance(func, FunctionDoc) for func in module.functions)


def test_collect_stdlib():
    """标准库模块：模块齐全、函数与常量均被收集。"""
    modules = collect_stdlib()
    by_title = {module.title: module for module in modules}
    assert {"文本", "数学", "集合", "文件", "编码", "异步IO"} <= set(by_title)

    math_module = by_title["数学"]
    math_funcs = {func.name: func for func in math_module.functions}
    assert "正弦" in math_funcs
    assert "幂" in math_funcs
    assert {const.name for const in math_module.constants} >= {"圆周率", "自然常数"}

    # 编码模块的嵌套命名空间应展平为 “子空间.函数”
    encoding_names = {func.name for func in by_title["编码"].functions}
    assert "JSON.编码" in encoding_names
    assert "Base64.解码" in encoding_names


def test_param_counts():
    """参数个数从注册信息正确提取，可变参数正确渲染。"""
    builtins = {f.name: f for f in collect_builtins().functions}
    assert builtins["长度"].param_count == 1
    assert builtins["交集"].param_count == 2
    assert builtins["互斥锁"].param_count == 0
    assert builtins["范围"].param_count == -1
    assert builtins["范围"].arity_text == "可变参数"
    assert builtins["长度"].arity_text == "1"
    assert builtins["读字节"].param_count == 1
    assert builtins["字节长度"].param_count == 1
    assert builtins["错误输出"].param_count == -1
    assert builtins["诊断源码"].param_count == 1

    hof = {f.name: f for f in collect_hof().functions}
    assert hof["映射"].param_count == 2
    assert hof["折叠"].param_count == 3

    math_funcs = {
        f.name: f
        for f in next(m for m in collect_stdlib() if m.title == "数学").functions
    }
    assert math_funcs["正弦"].param_count == 1
    assert math_funcs["幂"].param_count == 2


def test_markdown_format():
    """Markdown 表格结构正确，内容与字段名符合约定。"""
    doc = render_module_doc(collect_builtins())
    assert doc.startswith("# 基础内置函数\n")
    assert "## 函数" in doc
    assert "| 函数名 | 参数个数 | 描述 |" in doc
    assert "| --- | --- | --- |" in doc
    assert "| 打印 | 可变参数 | 打印函数：输出内容到控制台 |" in doc
    assert doc.endswith("\n")

    math_doc = render_module_doc(
        next(m for m in collect_stdlib() if m.title == "数学")
    )
    assert "## 常量与类型" in math_doc
    assert "| 圆周率 | float |" in math_doc
    # 表格单元格不得出现未转义的竖线
    for line in math_doc.splitlines():
        if line.startswith("| ") and not line.startswith("| ---"):
            assert line.count("|") >= 3


def test_generate_docs_all_modules():
    """所有模块（22 个）都能生成非空 Markdown 文档。"""
    docs = generate_docs()
    assert len(docs) == 22
    assert "基础内置函数" in docs and "高阶内置函数" in docs
    for title, text in docs.items():
        assert text.startswith(f"# {title}\n")
        assert "## 函数" in text
    assert len(collect_all()) == len(docs)


def test_description_extraction_chinese_first():
    """描述提取：中文行优先、无描述时给出占位文本。"""

    def _mixed():
        """First line in English.
        中文描述：这是中文说明。
        """

    def _no_doc():
        pass

    assert _extract_description(_mixed) == "中文描述：这是中文说明。"
    assert _extract_description(_no_doc) == "（暂无描述）"
    assert _extract_description(None) == "（暂无描述）"


def test_cli_stdout(capsys):
    """CLI 默认把全部文档输出到 stdout。"""
    assert docgen.main([]) == 0
    output = capsys.readouterr().out
    assert "# 基础内置函数" in output
    assert "# 高阶内置函数" in output
    assert "# 数学" in output


def test_cli_module_filter(capsys):
    """CLI 的 --module 仅输出指定模块；未知模块报错退出。"""
    assert docgen.main(["--module", "数学"]) == 0
    output = capsys.readouterr().out
    assert output.startswith("# 数学\n")
    assert "基础内置函数" not in output

    assert docgen.main(["--module", "不存在的模块"]) == 1
    assert "未找到模块" in capsys.readouterr().err


def test_cli_output_dir(tmp_path, capsys):
    """CLI 的 --output 为每个模块写出一个 .md 文件。"""
    out_dir = tmp_path / "api"
    assert docgen.main(["--output", str(out_dir)]) == 0
    capsys.readouterr()
    files = list(out_dir.glob("*.md"))
    assert len(files) == 22
    assert (out_dir / "数学.md").read_text(encoding="utf-8").startswith("# 数学\n")
    assert (out_dir / "基础内置函数.md").exists()


def test_pure_read_no_mutation():
    """生成文档不会修改源注册数据，重复调用结果稳定。"""
    from dao.builtins.functions import get_builtins
    from dao.builtins.hof import get_interpreter_builtins

    before_builtins = set(get_builtins())
    before_hof = set(get_interpreter_builtins())
    first = generate_docs()
    second = generate_docs()
    assert first == second
    assert set(get_builtins()) == before_builtins
    assert set(get_interpreter_builtins()) == before_hof


if __name__ == "__main__":
    pytest.main([__file__])
