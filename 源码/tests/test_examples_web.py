"""网络模块完整 Web 示例的端到端回归测试
========================================

用 sys.executable 真实启动 示例/Web应用/服务器.道 子进程，轮询端口就绪后：
1. 用 urllib 直接校验全部路由契约（首页 HTML、健康、订单 201/400、通配用户、默认 404）；
2. 用 sys.executable 跑 客户端.道，断言逐行稳定输出；
3. 断网时客户端重试耗尽后仍稳定退出并打印固定失败文本。

进程与端口约定：一律 sys.executable；通过 ASCII 环境变量 WEB示例端口 同步服务端与
客户端端口，使用临时空闲端口避免 18081 被占用导致失败；结束一律 terminate() +
communicate() 回收，就绪等待与读取均带超时，避免卡死。模块搜索基于 cwd，子进程
工作目录统一设为 示例/Web应用。
"""

import json
import os
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

import pytest

# 源码/tests/test_examples_web.py -> 仓库根目录
PROJECT_ROOT = Path(__file__).resolve().parents[2]
MAIN = PROJECT_ROOT / "源码" / "main.py"
示例目录 = PROJECT_ROOT / "示例" / "Web应用"

_ENV_PORT = "WEB示例端口"


def _空闲端口():
    """取一个当前空闲的本地端口，避免与固定端口 18081 上的其他进程冲突。"""
    with socket.socket() as 临时套接字:
        临时套接字.bind(("127.0.0.1", 0))
        return 临时套接字.getsockname()[1]


def _子进程环境(端口):
    环境 = os.environ.copy()
    环境[_ENV_PORT] = str(端口)
    环境["PYTHONPATH"] = str(MAIN.parent)
    return 环境


def _等待就绪(端口, 进程, 超时=10):
    """轮询 TCP 连接直到服务器就绪；进程提前退出或超时则 pytest.fail。"""
    截止 = time.monotonic() + 超时
    while time.monotonic() < 截止:
        if 进程.poll() is not None:
            pytest.fail(f"服务器子进程提前退出（退出码 {进程.returncode}）")
        try:
            with socket.create_connection(("127.0.0.1", 端口), timeout=0.3):
                return
        except OSError:
            time.sleep(0.05)
    pytest.fail(f"服务器未能在 {超时} 秒内监听端口 {端口}")


def _回收(进程):
    """terminate() + wait() 回收子进程，必要时 kill 兜底，避免端口泄漏与卡死。"""
    if 进程.poll() is None:
        进程.terminate()
        try:
            进程.communicate(timeout=5)
        except subprocess.TimeoutExpired:
            进程.kill()
            进程.communicate(timeout=5)
    else:
        进程.communicate(timeout=5)


def _启动服务器(端口):
    进程 = subprocess.Popen(
        [sys.executable, str(MAIN), "服务器.道"],
        cwd=str(示例目录),
        env=_子进程环境(端口),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    try:
        _等待就绪(端口, 进程)
    except BaseException:
        _回收(进程)
        raise
    return 进程


@pytest.fixture
def 运行中服务器():
    """每个用例独占一个空闲端口，结束后确保服务器进程退出。"""
    端口 = _空闲端口()
    进程 = _启动服务器(端口)
    try:
        yield 进程, 端口
    finally:
        _回收(进程)


def _请求(端口, 路径, 方法="GET", 数据=None, 请求头=None):
    """发请求并返回 (状态码, 响应体文本, Content-Type)；中文路径自动百分号编码。"""
    地址 = f"http://127.0.0.1:{端口}" + urllib.parse.quote(路径, safe="/?=&")
    请求对象 = urllib.request.Request(地址, data=数据, method=方法)
    for 键, 值 in (请求头 or {}).items():
        请求对象.add_header(键, 值)
    try:
        with urllib.request.urlopen(请求对象, timeout=5) as 响应:
            return 响应.status, 响应.read().decode("utf-8"), 响应.headers.get("Content-Type")
    except urllib.error.HTTPError as 错误:
        return 错误.code, 错误.read().decode("utf-8"), 错误.headers.get("Content-Type")


_JSON头 = {"Content-Type": "application/json"}


def test_服务端路由契约(运行中服务器):
    _, 端口 = 运行中服务器

    状态码, 响应体, 类型 = _请求(端口, "/")
    assert 状态码 == 200
    assert 类型 == "text/html; charset=utf-8"
    assert "<!DOCTYPE html>" in 响应体 and "道语言 Web 示例" in 响应体

    状态码, 响应体, 类型 = _请求(端口, "/api/健康")
    assert 状态码 == 200
    assert 类型 == "application/json; charset=utf-8"
    assert json.loads(响应体) == {"状态": "正常"}

    状态码, 响应体, _ = _请求(端口, "/api/用户/张三")
    assert 状态码 == 200
    assert json.loads(响应体) == {"用户": "张三"}
    # 通配路径支持多级与 URL 编码后的用户名
    状态码, 响应体, _ = _请求(端口, "/api/用户/李四/详情")
    assert 状态码 == 200
    assert json.loads(响应体) == {"用户": "李四/详情"}

    状态码, 响应体, _ = _请求(端口, "/api/订单", 方法="POST",
                              数据=json.dumps({"商品": "键盘", "数量": 2}, ensure_ascii=False).encode("utf-8"),
                              请求头=_JSON头)
    assert 状态码 == 201
    assert json.loads(响应体) == {"商品": "键盘", "数量": 2, "状态": "已创建"}

    for 载荷 in ({"商品": "键盘"}, {"数量": 2}, {}):
        状态码, 响应体, _ = _请求(端口, "/api/订单", 方法="POST",
                                  数据=json.dumps(载荷, ensure_ascii=False).encode("utf-8"),
                                  请求头=_JSON头)
        assert 状态码 == 400
        assert json.loads(响应体) == {"错误": "缺少商品或数量"}

    状态码, 响应体, _ = _请求(端口, "/api/订单", 方法="POST",
                              数据=b"{not json", 请求头=_JSON头)
    assert 状态码 == 400
    assert json.loads(响应体) == {"错误": "请求体不是合法的JSON"}

    状态码, 响应体, _ = _请求(端口, "/不存在的路径")
    assert 状态码 == 404
    assert "未找到" in 响应体


def _运行客户端(端口, 超时=20):
    进程 = subprocess.Popen(
        [sys.executable, str(MAIN), "客户端.道"],
        cwd=str(示例目录),
        env=_子进程环境(端口),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    try:
        标准输出, 标准错误 = 进程.communicate(timeout=超时)
    except subprocess.TimeoutExpired:
        进程.terminate()
        try:
            标准输出, 标准错误 = 进程.communicate(timeout=5)
        except subprocess.TimeoutExpired:
            进程.kill()
            标准输出, 标准错误 = 进程.communicate(timeout=5)
        pytest.fail(f"客户端超时已终止；stderr={标准错误!r}")
    assert 进程.returncode == 0, f"客户端退出码 {进程.returncode}；stdout={标准输出!r} stderr={标准错误!r}"
    return 标准输出, 标准错误


def test_客户端端到端输出(运行中服务器):
    _, 端口 = 运行中服务器
    标准输出, 标准错误 = _运行客户端(端口)
    行 = 标准输出.strip().splitlines()
    assert 行 == [
        "健康接口：HTTP 200 / 状态=正常",
        "订单创建：HTTP 201 / 商品=键盘 / 数量=2",
        "请求校验：HTTP 400 / 错误=缺少商品或数量",
    ], f"客户端输出不符：{行!r}；stderr={标准错误!r}"
    assert "请求失败" not in 标准输出
    assert "Traceback" not in 标准错误


def test_断网时重试耗尽后稳定失败():
    """没有服务器时，三条链路都在重试耗尽后打印固定失败文本并正常退出。"""
    端口 = _空闲端口()
    标准输出, 标准错误 = _运行客户端(端口)
    行 = 标准输出.strip().splitlines()
    assert 行 == [
        "健康接口：请求失败（网络异常）",
        "订单创建：请求失败（网络异常）",
        "请求校验：请求失败（网络异常）",
    ], f"断网输出不符：{行!r}"
    assert "Traceback" not in 标准错误
