#!/usr/bin/env bash
# 道语言 —— 用 Nuitka 编译为单文件原生可执行文件
# 在仓库任意位置运行均可；产物输出到 dist/nuitka/dao
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SRC="$ROOT/源码"
OUT="$ROOT/dist/nuitka"

echo "=== 道语言原生版打包（Nuitka onefile）==="

if ! command -v gcc >/dev/null 2>&1; then
    echo "错误：未找到 gcc C 编译器，Nuitka 需要它来生成原生代码" >&2
    exit 1
fi

if [ ! -x "$SRC/.venv/bin/python" ]; then
    echo "错误：未找到隔离解释器 $SRC/.venv/bin/python" >&2
    exit 1
fi

if ! "$SRC/.venv/bin/python" -m nuitka --version >/dev/null 2>&1; then
    echo "错误：Nuitka 未安装。请先执行：" >&2
    echo "  $SRC/.venv/bin/python -m pip install 'nuitka>=2.5'" >&2
    exit 1
fi

mkdir -p "$OUT"
cd "$SRC"
echo "开始编译（首次约需 5-8 分钟，取决于机器性能）..."
"$SRC/.venv/bin/python" -m nuitka \
    --onefile \
    --include-package=dao \
    --output-filename=dao \
    --output-dir="$OUT" \
    --assume-yes-for-downloads \
    main.py

echo ""
echo "=== 编译完成 ==="
echo "产物：$OUT/dao"
ls -lh "$OUT/dao"
echo ""
echo "验证：  $OUT/dao --help"
echo "安装：  $SRC/安装原生版.sh [--system]"
