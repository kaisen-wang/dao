"""通配符导入、标准库别名与关键字模块名测试。"""

import hashlib
import io
import os
from contextlib import redirect_stdout

import pytest

from dao.errors import 名称错误, 语法错误, 运行时错误
from dao.interpreter import Interpreter
from dao.lexer import Lexer
from dao.parser import Parser


def parse(source: str):
    """解析道源代码，返回 AST。"""
    return Parser(Lexer(source).tokenize()).parse()


def run(source: str) -> str:
    """真正走 Lexer → Parser → Interpreter 执行道源码，返回标准输出。"""
    ast = parse(source)
    interpreter = Interpreter()
    output = io.StringIO()
    with redirect_stdout(output):
        interpreter.execute(ast)
    return output.getvalue()


def write_module(tmp_path, name: str, code: str) -> None:
    """在 tmp_path 下写入一个 .道 模块文件。"""
    path = tmp_path / (name.replace(".", os.sep) + ".道")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(code, encoding="utf-8")


# ---------- 通配符解析 ----------


def test_parse_wildcard_from_import_ast():
    """`从 模块 导入 *` 在 AST 中以 ("*", None) 表示。"""
    stmt = parse("从 密码 导入 *").statements[0]
    assert stmt.is_from_import is True
    assert stmt.module_path == "密码"
    assert stmt.names == [("*", None)]


# ---------- 标准库通配符导入（真实执行） ----------


def test_wildcard_stdlib_password_executes():
    """标准库通配符导入后立即调用导入的函数。"""
    output = run('从 密码 导入 *\n打印(SHA256("abc"))')
    assert hashlib.sha256(b"abc").hexdigest() in output


def test_wildcard_stdlib_asyncio_alias_executes():
    """`异步` 别名与 `异步IO` 原名都支持通配符导入。"""
    for module in ("异步", "异步IO"):
        output = run(f"从 {module} 导入 *\n打印(默认超时)")
        assert "300" in output


# ---------- 别名模块 ----------


def test_stdlib_alias_encrypt_from_import():
    """`加密` 是 `密码` 的直觉别名，可精确导入并使用。"""
    output = run('从 加密 导入 SHA256\n打印(SHA256("abc"))')
    assert hashlib.sha256(b"abc").hexdigest() in output


def test_original_stdlib_names_still_work():
    """新增别名后，原有模块名继续可用。"""
    output = run('从 密码 导入 SHA256\n从 异步IO 导入 默认超时\n打印(SHA256("a"))\n打印(默认超时)')
    assert hashlib.sha256(b"a").hexdigest() in output
    assert "300" in output


# ---------- 本地 .道 模块通配符导入（真实执行） ----------


def test_wildcard_local_module_with_exports(tmp_path, monkeypatch):
    """本地模块有导出列表时，通配符导入全部导出项。"""
    write_module(tmp_path, "水果", "定义 苹果 = 5\n定义 香蕉 = 7\n导出 苹果, 香蕉\n")
    monkeypatch.chdir(tmp_path)
    assert "12" in run("从 水果 导入 *\n打印(苹果 + 香蕉)")


def test_wildcard_local_module_without_exports(tmp_path, monkeypatch):
    """本地模块无导出列表时，绑定用户定义但排除内部名。"""
    write_module(tmp_path, "裸模块", "定义 结果 = 99\n定义 _内部 = 123\n")
    monkeypatch.chdir(tmp_path)
    assert "99" in run("从 裸模块 导入 *\n打印(结果)")
    with pytest.raises(名称错误):
        run("从 裸模块 导入 *\n打印(_内部)")


def test_wildcard_respects_exports_filter(tmp_path, monkeypatch):
    """有导出列表时，通配符只绑定导出项，未导出项不可见。"""
    write_module(tmp_path, "m", "定义 公开 = 1\n定义 秘密值 = 2\n导出 公开\n")
    monkeypatch.chdir(tmp_path)
    assert "1" in run("从 m 导入 *\n打印(公开)")
    with pytest.raises(名称错误):
        run("从 m 导入 *\n打印(秘密值)")


def test_wildcard_dotted_module_path(tmp_path, monkeypatch):
    """点分路径的本地模块同样支持通配符导入。"""
    write_module(tmp_path, "工具.数学", "定义 值 = 42\n导出 值\n")
    monkeypatch.chdir(tmp_path)
    assert "42" in run("从 工具.数学 导入 *\n打印(值)")


# ---------- 作用域语义 ----------


def test_wildcard_import_respects_function_scope():
    """函数内的通配符导入只绑定到当前作用域，不泄漏到全局。"""
    source = '函数 试试()\n    从 密码 导入 *\n    返回 SHA256("abc")\n\n打印(试试())\n'
    assert hashlib.sha256(b"abc").hexdigest() in run(source)
    with pytest.raises(名称错误):
        run('打印(SHA256("abc"))')


# ---------- 精确导入与别名不回退 ----------


def test_exact_import_and_alias_no_regression(tmp_path, monkeypatch):
    """原有精确导入与 `作为` 别名行为保持不变。"""
    write_module(tmp_path, "m", "定义 x = 42\n导出 x\n")
    monkeypatch.chdir(tmp_path)
    assert "42" in run("从 m 导入 x 作为 y\n打印(y)")
    with pytest.raises(名称错误):
        run("从 m 导入 x 作为 y\n打印(x)")


# ---------- 关键字模块名 ----------


def test_keyword_module_name_parsing():
    """模块路径段允许上下文关键字（如 异步）。"""
    stmt = parse("从 异步 导入 默认超时").statements[0]
    assert stmt.module_path == "异步"
    assert stmt.names == [("默认超时", None)]

    stmt = parse("导入 异步").statements[0]
    assert stmt.module_path == "异步"
    assert stmt.is_from_import is False


# ---------- 错误路径 ----------


def test_wildcard_mixed_with_name_error():
    """通配符不能跟在其他导入名之后。"""
    with pytest.raises(语法错误, match="通配符"):
        parse("从 m 导入 a, *")


def test_wildcard_with_alias_error():
    """通配符不能带 `作为` 别名。"""
    with pytest.raises(语法错误, match="通配符"):
        parse("从 m 导入 * 作为 x")


def test_wildcard_then_comma_error():
    """通配符之后不能再跟逗号分隔的其他名称。"""
    with pytest.raises(语法错误, match="通配符"):
        parse("从 m 导入 *, a")


def test_wildcard_unknown_module_error():
    """通配符导入未知模块时照常报错。"""
    with pytest.raises(运行时错误, match="不存在"):
        run("从 不存在的模块XYZ 导入 *")


def test_exact_import_unknown_name_error(tmp_path, monkeypatch):
    """精确导入未导出的名称仍报原有错误。"""
    write_module(tmp_path, "m", "定义 x = 1\n导出 x\n")
    monkeypatch.chdir(tmp_path)
    with pytest.raises(运行时错误, match="没有导出"):
        run("从 m 导入 y")
