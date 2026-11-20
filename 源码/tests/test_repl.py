"""
REPL 交互体验测试
================

通过 monkeypatch 替换输入源来驱动 run_repl()，不依赖真实终端；
输入耗尽后抛出 EOFError 触发优雅退出，因此不会进入死循环。
"""

import builtins
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

import pytest

import main as repl_main


class FakeInput:
    """按序返回预设输入的假输入源；耗尽后抛 EOFError 结束 REPL。"""

    def __init__(self, lines):
        self.lines = list(lines)
        self.calls = 0

    def __call__(self, prompt=''):
        self.calls += 1
        if not self.lines:
            raise EOFError
        return self.lines.pop(0)


def _drive(lines, monkeypatch, capsys):
    """用给定的输入列表驱动一次 run_repl，返回 (输出, 假输入源)。"""
    fake = FakeInput(lines)
    monkeypatch.setattr(repl_main, '_read_line', fake)
    repl_main.run_repl()
    return capsys.readouterr().out, fake


# ---------------------------------------------------------------------------
# 端到端 REPL 行为
# ---------------------------------------------------------------------------

def test_单行执行结果(monkeypatch, capsys):
    """单行表达式应当被执行并显示结果，退出命令打印再见。"""
    out, _ = _drive(['定义 x = 1', 'x + 2', '退出'], monkeypatch, capsys)
    assert any(line.strip() == '3' for line in out.splitlines())
    assert '再见' in out


def test_多行块拼接(monkeypatch, capsys):
    """块关键字进入续行，空行结束，整段源码被拼接后一次执行。"""
    sources = []
    monkeypatch.setattr(
        repl_main, 'run_source',
        lambda source, interp, *a, **k: sources.append(source),
    )
    _drive(['如果 1 == 1', '    打印(42)', '', '退出'], monkeypatch, capsys)

    assert len(sources) == 1
    assert sources[0] == '如果 1 == 1\n    打印(42)\n'


def test_帮助命令输出(monkeypatch, capsys):
    """:帮助 列出所有 REPL 命令，欢迎语也给出提示。"""
    out, _ = _drive([':帮助', '退出'], monkeypatch, capsys)
    for kw in ('REPL 命令', ':宏列表', ':宏追踪', ':宏追踪状态',
               ':宏调用栈', ':宏帮助', ':粘贴', ':多行'):
        assert kw in out
    assert "输入 ':帮助' 查看所有命令" in out


@pytest.mark.parametrize('cmd', ['退出', 'exit', 'quit'])
def test_退出命令(monkeypatch, capsys, cmd):
    """三种退出命令都应在读取一行后优雅退出。"""
    out, fake = _drive([cmd], monkeypatch, capsys)
    assert '再见' in out
    assert fake.calls == 1


def test_粘贴模式拼接(monkeypatch, capsys):
    """:粘贴 进入多行模式，以 '.' 结束后整体执行。"""
    sources = []
    monkeypatch.setattr(
        repl_main, 'run_source',
        lambda source, interp, *a, **k: sources.append(source),
    )
    _drive([':粘贴', '打印(1)', '打印(2)', '.', '退出'], monkeypatch, capsys)

    assert len(sources) == 1
    assert sources[0] == '打印(1)\n打印(2)\n'


def test_未知命令给出提示(monkeypatch, capsys):
    """未知冒号命令不应崩溃，并提示查看帮助。"""
    out, _ = _drive([':不存在', '退出'], monkeypatch, capsys)
    assert '未知命令' in out
    assert ':帮助' in out


# ---------------------------------------------------------------------------
# 多行判定（纯函数，无 I/O）
# ---------------------------------------------------------------------------

@pytest.mark.parametrize('line, expected', [
    ('打印("a:")', False),          # 字符串里的冒号
    ('设 s = "abc:"', False),
    ('打印("""a:""")', False),       # 三引号字符串里的冒号
    ('注：注释：', False),            # 行注释里的冒号
    ('// 注释：', False),
    ('设 d = {"a": 1}', False),      # 字典字面量里的冒号（括号内层）
    ('如果 x: 打印(x)', False),      # 单行语句，冒号后还有代码
    ('x + 2', False),
    ('函数表 = 1', False),           # 以关键字开头但不是独立关键字
    ('如果 x > 0', True),            # 块关键字进入续行
    ('如果 x:', True),               # 顶层冒号结尾进入续行
    ('函数 f()', True),
])
def test_多行判定(line, expected):
    assert repl_main._needs_continuation(line) is expected


# ---------------------------------------------------------------------------
# prompt_toolkit 可选接入与优雅降级
# ---------------------------------------------------------------------------

def test_依赖缺失时降级到_input(monkeypatch):
    """无法取得 PromptSession 时，_read_line 回退到内置 input()。"""
    seen = []

    def fake_input(prompt=''):
        seen.append(prompt)
        return 'x + 1'

    monkeypatch.setattr(repl_main, '_prompt_session', None)
    monkeypatch.setattr(repl_main, '_prompt_session_tried', True)
    monkeypatch.setattr('sys.stdin.isatty', lambda: True)
    monkeypatch.setattr(builtins, 'input', fake_input)

    assert repl_main._read_line('道 > ') == 'x + 1'
    assert seen == ['道 > ']


def test_导入失败时返回_None(monkeypatch):
    """prompt_toolkit 导入抛异常时，_get_prompt_session 返回 None 而不外抛。"""
    real_import = builtins.__import__

    def fake_import(name, *args, **kwargs):
        if name.startswith('prompt_toolkit'):
            raise ImportError('模拟依赖缺失')
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(repl_main, '_prompt_session_tried', False)
    monkeypatch.setattr(builtins, '__import__', fake_import)

    assert repl_main._get_prompt_session() is None


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
