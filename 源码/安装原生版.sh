#!/usr/bin/env bash
# 道语言 —— 安装 / 卸载原生可执行文件到系统 PATH
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SRC="$ROOT/dist/nuitka/dao"
NAME="dao"

SYSTEM=0
UNINSTALL=0
for arg in "$@"; do
    case "$arg" in
        --system) SYSTEM=1 ;;
        --uninstall) UNINSTALL=1 ;;
        -h|--help)
            echo "用法：$0 [--system] [--uninstall]"
            echo "  （默认）     安装到 ~/.local/bin/dao（推荐，无需管理员权限）"
            echo "  --system     安装到 /usr/local/bin/dao（需要 sudo）"
            echo "  --uninstall  卸载已安装的 dao 命令"
            exit 0
            ;;
        *)
            echo "未知参数：$arg" >&2
            exit 1
            ;;
    esac
done

if [ "$SYSTEM" -eq 1 ]; then
    DEST_DIR="/usr/local/bin"
    if [ "$(id -u)" -ne 0 ]; then
        echo "系统级安装需要管理员权限，请用：sudo $0 --system" >&2
        exit 1
    fi
else
    DEST_DIR="$HOME/.local/bin"
fi
DEST="$DEST_DIR/$NAME"

# 用 Python 删除单个文件（跨环境可靠，避免 shell 安全 shim 干扰）
_remove_file() {
    python3 - "$1" <<'PY'
import os
import sys

path = sys.argv[1]
if os.path.islink(path) or os.path.isfile(path):
    os.remove(path)
PY
}

if [ "$UNINSTALL" -eq 1 ]; then
    # 卸载：同时清理用户级与系统级可能存在的安装
    removed=0
    for d in "$HOME/.local/bin/$NAME" "/usr/local/bin/$NAME"; do
        if [ -e "$d" ] || [ -L "$d" ]; then
            if _remove_file "$d" 2>/dev/null; then
                echo "已卸载：$d"
                removed=1
            else
                echo "无法卸载 $d（系统级安装请用 sudo $0 --uninstall）" >&2
            fi
        fi
    done
    if [ "$removed" -eq 0 ]; then
        echo "未找到已安装的 $NAME 命令"
    fi
    exit 0
fi

if [ ! -f "$SRC" ]; then
    echo "错误：找不到原生可执行文件 $SRC" >&2
    echo "请先运行打包脚本：$ROOT/源码/打包原生版.sh" >&2
    exit 1
fi

mkdir -p "$DEST_DIR"
install -m 755 "$SRC" "$DEST"
echo "已安装：$DEST"

case ":$PATH:" in
    *":$DEST_DIR:"*)
        echo "PATH 已包含 $DEST_DIR，可直接运行：$NAME"
        ;;
    *)
        echo "提示：$DEST_DIR 不在当前 PATH 中。将下面一行加入 ~/.bashrc 或 ~/.zshrc："
        echo "  export PATH=\"$DEST_DIR:\$PATH\""
        echo "（加入后重开终端或执行 source 使其生效）"
        ;;
esac

echo ""
echo "=== 验证安装 ==="
"$DEST" --help | head -3
