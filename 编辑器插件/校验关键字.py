#!/usr/bin/env python3
"""校验编辑器语法文件是否覆盖权威关键字表（源码/dao/tokens.py 的 KEYWORDS）。

纯标准库实现；路径均相对本脚本推导，可从任意工作目录执行。
对每个语法文件逐一检查关键字字符串是否出现，输出缺失清单与覆盖结果；
任一文件有缺失时退出码为 1，全部通过时为 0。
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parent
TOKENS_FILE = REPO_ROOT / "源码" / "dao" / "tokens.py"
TARGETS = (
    SCRIPT_DIR / "vscode" / "syntaxes" / "dao.tmLanguage.json",
    SCRIPT_DIR / "neovim" / "syntax" / "dao.vim",
)


def load_keywords() -> dict[str, object]:
    """按文件路径加载 tokens.py，避免依赖包安装状态与当前工作目录。"""
    spec = importlib.util.spec_from_file_location("dao_tokens_for_check", TOKENS_FILE)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"无法加载关键字典文件：{TOKENS_FILE}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.KEYWORDS


def main() -> int:
    keywords = load_keywords()
    total = len(keywords)
    print(f"权威关键字表：源码/dao/tokens.py（{total} 项）")

    all_ok = True
    for target in TARGETS:
        text = target.read_text(encoding="utf-8")
        missing = [kw for kw in keywords if kw not in text]
        rel = target.relative_to(REPO_ROOT)
        if missing:
            all_ok = False
            print(f"[缺失] {rel}：缺失 {len(missing)} 项 -> {'、'.join(missing)}")
            print(f"       覆盖 {total - len(missing)}/{total}")
        else:
            print(f"[通过] {rel}：{total}/{total}（全覆盖，缺失清单为空）")

    print(f"结果：{'PASS' if all_ok else 'FAIL'} —— {total}/{total} 权威关键字 × {len(TARGETS)} 个语法文件")
    return 0 if all_ok else 1


if __name__ == "__main__":
    sys.exit(main())
