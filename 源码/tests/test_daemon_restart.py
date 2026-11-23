"""更夫 Nightwatch — 第十轮 · 真实守护重启与优雅停机验收（子代理 C / daemon-restart）。

覆盖共享契约《迭代规约-韧性审计与守护验收.md》§2 C：
- 用 sys.executable 启动真实 Python 子进程运行 示例/更夫/接入层/常驻入口.道
  （cwd=示例/更夫），不设「更夫长驻跳过运行」门控，走真实保活循环；
  设 更夫心跳周期毫秒=200 加速、更夫停机标记 指向 tempfile 内唯一路径、GENGFU_NO_LLM=1。
- 用例一（优雅停机）：确认存活 → touch 停机标记 → ≤5 秒内退出码 0（优雅退出，非被杀）。
- 用例二（外层重启）：确认存活 → proc.terminate() 强停 → 同命令重启第二个子进程 →
  确认存活并响应停机标记优雅退出，模拟「外层守护拉起」语义。

诚实边界：
- 本验收是「真实 Python 子进程 + 本地信号」，不等于生产 systemd / supervisor 的
  Restart=always 真实拉起；外层重启由测试代码显式重启子进程实现，是语义模拟而非真实 init 行为。
- 心跳/统计仅做本地保活与观测，不发起真实外部请求、不接真实平台；不依赖真实网络 / ollama。
- 不验证真实一周运行 / 真实平台断网；PRD §12 DoD 继续未勾选。

跨平台约定：
- 一律用 sys.executable 启动子进程，禁止硬编码 .venv/bin/python。
- 停止子进程统一用 proc.terminate()（Windows→TerminateProcess，POSIX→SIGTERM），
  超时才 fallback proc.kill()；不使用 signal.SIGKILL / os.kill(pid, SIGKILL)（Windows 无 SIGKILL）。
- 临时文件用 tempfile.TemporaryDirectory() 隔离并在退出时清理，项目目录不产生停机标记 / .db。
- stdout/stderr 用 PIPE（stderr 合并进 stdout）并在适当时机 communicate() 回收，
  避免长驻入口周期打印心跳把管道缓冲区填满导致阻塞；单用例 ≤10 秒。
"""

import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path

import pytest

# 源码/tests/test_daemon_restart.py -> 仓库根目录
PROJECT_ROOT = Path(__file__).resolve().parents[2]
MAIN = PROJECT_ROOT / "源码" / "main.py"
GENGFU_DIR = PROJECT_ROOT / "示例" / "更夫"
常驻入口 = "接入层/常驻入口.道"


def _启动长驻(停机标记路径: Path) -> subprocess.Popen:
    """用 sys.executable 启动真实子进程运行长驻入口（不设跳过门控，走真实保活循环）。"""
    环境变量 = os.environ.copy()
    环境变量["PYTHONPATH"] = str(MAIN.parent)
    环境变量["更夫心跳周期毫秒"] = "200"          # 加速心跳，便于快速观测与停机
    环境变量["更夫停机标记"] = str(停机标记路径)  # 指向本轮 tempfile 内唯一路径
    环境变量["GENGFU_NO_LLM"] = "1"              # 不依赖真实网络 / ollama
    # 关键：不设「更夫长驻跳过运行」，确保进入 运行长驻() 的真实保活循环。
    环境变量.pop("更夫长驻跳过运行", None)
    return subprocess.Popen(
        [sys.executable, str(MAIN), 常驻入口],
        cwd=str(GENGFU_DIR),
        env=环境变量,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,  # 合并两路输出，避免任一管道被心跳日志填满
        text=True,
    )


def _等待退出(进程: subprocess.Popen, 超时秒: float) -> bool:
    """轮询 proc.poll() 等待进程自然退出；返回是否在时限内退出。"""
    截止 = time.monotonic() + 超时秒
    while time.monotonic() < 截止:
        if 进程.poll() is not None:
            return True
        time.sleep(0.05)
    return False


def _停止进程(进程: subprocess.Popen, 超时秒: float = 3.0) -> None:
    """跨平台停止子进程：先 terminate()，超时才 fallback proc.kill()。

    terminate() 在 Windows 映射 TerminateProcess、POSIX 映射 SIGTERM；
    不使用 signal.SIGKILL / os.kill(pid, SIGKILL)（Windows 无 SIGKILL，第八轮因此全失败）。
    """
    if 进程.poll() is None:
        进程.terminate()
    try:
        进程.communicate(timeout=超时秒)
    except subprocess.TimeoutExpired:
        if 进程.poll() is None:
            进程.kill()  # 跨平台兜底（非显式 SIGKILL）
        进程.communicate(timeout=超时秒)


def _安全回收(进程: subprocess.Popen) -> None:
    """用例收尾：已退出则回收管道，仍存活则跨平台停止。"""
    if 进程.poll() is None:
        _停止进程(进程)
        return
    try:
        进程.communicate(timeout=2)
    except subprocess.TimeoutExpired:
        pass


def _touch停机标记(路径: Path) -> None:
    """touch 停机标记并写入内容，触发长驻入口优雅停机。"""
    路径.write_text("stop-by-nightwatch-test\n", encoding="utf-8")


def test_优雅停机_标记触发后优雅退出():
    """用例一：确认存活 → touch 停机标记 → ≤5 秒内退出码 0（优雅退出，非被杀）。"""
    with tempfile.TemporaryDirectory(prefix="更夫守护-停机-") as 临时目录:
        停机标记 = Path(临时目录) / "gengfu.stop"  # 本轮唯一路径，退出即清理
        进程 = _启动长驻(停机标记)
        try:
            # 启动后先给 interpreter 初始化与心跳注册留时间，再确认进程存活（未立即崩溃）。
            time.sleep(0.4)
            assert 进程.poll() is None, (
                f"长驻进程启动后应存活，实际退出码 {进程.returncode}"
            )

            # touch 停机标记（写入内容），长驻心跳应在 next 轮检测到并优雅退出。
            _touch停机标记(停机标记)

            # 轮询等待自然退出，≤5 秒；超时视为失败（finally 会 terminate 清理）。
            已退出 = _等待退出(进程, 超时秒=5.0)
            assert 已退出, "touch 停机标记后 5 秒内进程未退出（未触发优雅停机）"
            assert 进程.returncode == 0, (
                f"期望优雅退出码 0（非被杀），实际 {进程.returncode}"
            )

            输出, _ = 进程.communicate(timeout=2)
            assert "[停机]" in 输出 and "优雅退出" in 输出, (
                f"未看到优雅停机日志，stdout={输出!r}"
            )
            print(
                f"[优雅停机] 退出码={进程.returncode}；命中 '[停机]…优雅退出' 日志；"
                f"心跳周期=200ms，停机标记={停机标记.name}"
            )
        finally:
            _安全回收(进程)


def test_外层重启_强停后同命令拉起并响应停机():
    """用例二：确认存活 → proc.terminate() 强停 → 同命令重启第二个子进程 →
    确认存活并响应停机标记优雅退出。模拟「外层守护拉起」语义，不等于真实 systemd。
    """
    with tempfile.TemporaryDirectory(prefix="更夫守护-重启-") as 临时目录:
        停机标记 = Path(临时目录) / "gengfu.stop"

        # --- 阶段一：第一个进程，模拟被外层判定需强停的旧实例 ---
        进程一 = _启动长驻(停机标记)
        try:
            time.sleep(0.4)
            assert 进程一.poll() is None, "第一个长驻进程启动后应存活"

            # 跨平台强停：Windows→TerminateProcess / POSIX→SIGTERM（非 SIGKILL）。
            进程一.terminate()
            if not _等待退出(进程一, 超时秒=3.0) and 进程一.poll() is None:
                进程一.kill()  # 终止超时才兜底；不使用 SIGKILL

            assert 进程一.poll() is not None, "第一个进程 terminate 后应退出"
            # 优雅退出码为 0；被强停应为非 0（Windows 通常 1 / POSIX 通常 -15），据此区分。
            assert 进程一.returncode != 0, (
                f"第一个进程应是被强停而非优雅退出，实际退出码 {进程一.returncode}"
            )
            print(f"[外层重启] 第一个进程 terminate 后退出码={进程一.returncode}（非 0，确认被强停）")
        finally:
            _安全回收(进程一)

        # --- 阶段二：用同一命令重启，模拟「外层守护拉起」（语义模拟，非真实 systemd） ---
        进程二 = _启动长驻(停机标记)
        try:
            time.sleep(0.4)
            assert 进程二.poll() is None, "重启后的第二个长驻进程应存活"

            _touch停机标记(停机标记)
            已退出 = _等待退出(进程二, 超时秒=5.0)
            assert 已退出, "重启进程 touch 停机标记后 5 秒内未退出"
            assert 进程二.returncode == 0, (
                f"重启进程期望优雅退出码 0，实际 {进程二.returncode}"
            )

            输出, _ = 进程二.communicate(timeout=2)
            assert "[停机]" in 输出, f"重启进程未看到停机日志：{输出!r}"
            print(
                f"[外层重启] 第二个进程优雅退出码={进程二.returncode}；"
                f"命中 '[停机]' 日志；同命令重启后仍可响应停机标记"
            )
        finally:
            _安全回收(进程二)
