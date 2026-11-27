"""新增/增强模块的端到端导入测试：统一使用「从 模块 导入 名称」语法。"""

import io
import json
import os
import sys
from contextlib import redirect_stdout

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from dao.interpreter import Interpreter
from dao.lexer import Lexer
from dao.parser import Parser
from dao.stdlib.loader import StdlibLoader


def _运行(源码):
    """在道解释器里执行源码并返回标准输出。"""
    输出 = io.StringIO()
    with redirect_stdout(输出):
        tokens = Lexer(源码).tokenize()
        ast = Parser(tokens).parse()
        Interpreter().execute(ast)
    return 输出.getvalue()


class Test加载器识别:
    def test_新模块被识别为标准库(self):
        for 模块名 in ("路径", "进程", "归档"):
            assert StdlibLoader.is_stdlib_module(模块名) is True

    def test_新模块可加载(self):
        for 模块名 in ("路径", "进程", "归档"):
            env = StdlibLoader.load(模块名, Interpreter())
            assert env.values


class Test导入语法:
    def test_路径模块导入(self):
        源码 = """
从 路径 导入 拼接, 取扩展名, 取文件名
打印(拼接("数据", "app.txt"))
打印(取扩展名("数据/app.txt"))
打印(取文件名("数据/app.txt"))
"""
        结果 = _运行(源码)
        assert "数据/app.txt" in 结果
        assert ".txt" in 结果
        assert "app.txt" in 结果

    def test_时间模块增强函数导入(self):
        源码 = """
从 时间 导入 创建时间, 日期加减, 日历
定义 某天 = 创建时间(2026, 1, 1)
打印(日期加减(某天, 天数=1).日)
打印(长度(日历(2026, 2)))
"""
        结果 = _运行(源码)
        assert "2" in 结果

    def test_密码模块增强函数导入(self):
        源码 = """
从 密码 导入 MD5, SHA512
打印(长度(MD5("abc")))
打印(长度(SHA512("abc")))
"""
        结果 = _运行(源码)
        assert "32" in 结果
        assert "128" in 结果

    def test_归档模块导入(self, tmp_path):
        源目录 = tmp_path / "源"
        源目录.mkdir()
        (源目录 / "a.txt").write_text("内容", encoding="utf-8")
        压缩包 = tmp_path / "a.zip"
        源码 = f"""
从 归档 导入 打包ZIP, 列出ZIP
打包ZIP({json.dumps(str(源目录), ensure_ascii=False)}, {json.dumps(str(压缩包), ensure_ascii=False)})
打印(列出ZIP({json.dumps(str(压缩包), ensure_ascii=False)}))
"""
        结果 = _运行(源码)
        assert "a.txt" in 结果

    def test_进程模块导入(self):
        源码 = f"""
从 进程 导入 运行命令
定义 结果 = 运行命令({json.dumps(sys.executable, ensure_ascii=False)}, ["-c", "print(789)"])
打印(结果.退出码)
"""
        结果 = _运行(源码)
        assert "0" in 结果
