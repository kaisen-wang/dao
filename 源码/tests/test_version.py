"""版本号信息测试

验证：
- ``dao.version`` 是版本号的单一来源，``dao.__version__`` 与之同步；
- 命令行 ``-V`` / ``--version`` 输出版本号并正常退出；
- REPL 横幅中的版本号取自同一来源，不再硬编码；
- 版本文本包含当前版本号。
"""

import io
import os
import subprocess
import sys
from contextlib import redirect_stdout

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

import dao
import main as cli
from dao.version import __version__, banner_text, version_text


def test_版本号单一来源():
    """dao.__version__ 必须等于 dao.version.__version__。"""
    assert dao.__version__ == __version__


def test_版本号为合法点分格式():
    """版本号形如 主.次.修订，均为正整数。"""
    parts = __version__.split('.')
    assert 2 <= len(parts) <= 3
    assert all(p.isdigit() for p in parts)


def test_版本文本包含版本号():
    """命令行版本文本与 REPL 横幅都应含当前版本号。"""
    assert __version__ in version_text()
    assert __version__ in banner_text()
    assert '道' in version_text()


def test_命令行长参数版本输出():
    """--version 打印版本号并以 0 退出。"""
    result = subprocess.run(
        [sys.executable, os.path.join(os.path.dirname(__file__), '..', 'main.py'), '--version'],
        capture_output=True, text=True, check=False,
    )
    assert result.returncode == 0
    assert __version__ in result.stdout
    assert '道' in result.stdout


def test_命令行短参数版本输出():
    """-V 与 --version 输出一致。"""
    root = os.path.join(os.path.dirname(__file__), '..', 'main.py')
    short = subprocess.run([sys.executable, root, '-V'], capture_output=True, text=True, check=False)
    long = subprocess.run([sys.executable, root, '--version'], capture_output=True, text=True, check=False)
    assert short.returncode == 0 and long.returncode == 0
    assert short.stdout == long.stdout


def test_命令行帮助含版本参数():
    """--help 中列出 -V/--version。"""
    result = subprocess.run(
        [sys.executable, os.path.join(os.path.dirname(__file__), '..', 'main.py'), '--help'],
        capture_output=True, text=True, check=False,
    )
    assert result.returncode == 0
    assert '--version' in result.stdout
    assert '显示版本号信息并退出' in result.stdout


def test_REPL横幅取自单一源():
    """REPL 横幅中的版本行与 banner_text() 一致。"""
    # 用空输入触发 EOFError 让 REPL 立即退出，仅捕获横幅。
    import builtins
    original = builtins.input
    builtins.input = lambda *a, **k: (_ for _ in ()).throw(EOFError())
    try:
        buf = io.StringIO()
        with redirect_stdout(buf):
            cli.run_repl()
        out = buf.getvalue()
    finally:
        builtins.input = original
    assert banner_text().strip() in out
    assert 'v' + __version__ in out
