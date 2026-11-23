#!/bin/sh
# 更夫 Nightwatch - 生产启动包装脚本（第九轮）
# 原理：systemd 259 / supervisor 对环境变量的处理不同——systemd 会忽略中文变量名，
#       故本脚本用 ASCII 中转变量先存值，再 export 成中文变量名，
#       使道语言层 取环境变量("键名") 能真正读到；随后 exec 长驻入口进程。
#       长驻入口为 接入层/常驻入口.道（主线程保活 + 优雅停机），替代跑完即退的演示入口.道。

# ===================== 现场替换项（★必改）=====================
#   1) GENGFU_PYTHON : 道语言解释器 python 绝对路径（生产如 /opt/gengfu/venv/bin/python）
#   2) GENGFU_MAIN   : 解释器 main.py 绝对路径（生产如 /opt/gengfu/源码/main.py）
#   3) GENGFU_ROOT   : 示例/更夫 工作目录绝对路径（生产如 /opt/gengfu/示例/更夫）
#   4) 下面 GENGFU_* 默认值（端口/数据库/演示模式/停机标记）按现场修改，
#      并与 supervisor/gengfu.conf 的 environment 口径保持一致。
#   5) 部署后执行：chmod +x /opt/gengfu/示例/更夫/部署/systemd/启动包装.sh
# ===============================================================

# ---- 1. ASCII 中转变量：先把默认/占位值存入 ASCII 变量（可被外部同名环境变量覆盖）----
GENGFU_NO_LLM_DEFAULT="${GENGFU_NO_LLM_DEFAULT:-1}"
GENGFU_PORT="${GENGFU_PORT:-8765}"
GENGFU_DB="${GENGFU_DB:-/var/lib/gengfu/gengfu.db}"
GENGFU_WEBHOOK_PORT="${GENGFU_WEBHOOK_PORT:-8766}"
GENGFU_DEMO="${GENGFU_DEMO:-0}"
# 停机标记须与 systemd unit 的 ExecStop（touch /opt/gengfu/run/gengfu.stop）指向同一文件。
GENGFU_STOP_FILE="${GENGFU_STOP_FILE:-/opt/gengfu/run/gengfu.stop}"

# ---- 2. export 成五个中文变量名（中文名真正进入进程环境）----
export GENGFU_NO_LLM="$GENGFU_NO_LLM_DEFAULT"
export 更夫端口="$GENGFU_PORT"
export 更夫数据库="$GENGFU_DB"
export 更夫Webhook端口="$GENGFU_WEBHOOK_PORT"
export 更夫演示模式="$GENGFU_DEMO"
# 第六个为优雅停机标记变量，与 ExecStop 对齐（长驻入口按此路径监听）。
export 更夫停机标记="$GENGFU_STOP_FILE"

# ---- 3. 现场替换：python / main.py / 工作目录（均为绝对路径占位）----
GENGFU_PYTHON="${GENGFU_PYTHON:-/opt/gengfu/venv/bin/python}"
GENGFU_MAIN="${GENGFU_MAIN:-/opt/gengfu/源码/main.py}"
GENGFU_ROOT="${GENGFU_ROOT:-/opt/gengfu/示例/更夫}"

# 道语言模块搜索基于 cwd，必须先切到 示例/更夫 再载入入口脚本。
cd "$GENGFU_ROOT" || exit 1

# 用 exec 让守护进程直接持有道语言进程，stop/kill 信号可直接送达。
exec "$GENGFU_PYTHON" "$GENGFU_MAIN" "接入层/常驻入口.道"
