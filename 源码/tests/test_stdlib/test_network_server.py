import json
import os
import socket
import sys
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from unittest.mock import MagicMock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from dao.builtins.callables import DaoCallable
from dao.stdlib.network import DaoHttpServer


def _启动(server):
    """在后台线程启动服务器（端口 0），等待绑定完成后返回线程对象。"""
    thread = threading.Thread(target=server.启动, kwargs={"端口": 0}, daemon=True)
    thread.start()
    截止时间 = time.time() + 5
    while server.端口 is None and time.time() < 截止时间:
        time.sleep(0.01)
    assert server.端口 is not None, "服务器未能在预期时间内启动"
    return thread


def _关闭(server, thread):
    """关闭服务器并等待线程退出，避免端口泄漏。"""
    server.关闭()
    thread.join(timeout=5)
    assert not thread.is_alive(), "服务器线程未能退出"


def _请求(端口, 路径, 方法="GET", 数据=None, 请求头=None):
    """用 urllib 发起请求，返回 (状态码, 响应体文本, 响应头字典)。"""
    url = f"http://127.0.0.1:{端口}{路径}"
    req = urllib.request.Request(url, method=方法)
    for key, value in (请求头 or {}).items():
        req.add_header(key, value)
    try:
        with urllib.request.urlopen(req, data=数据, timeout=5) as resp:
            return resp.status, resp.read().decode("utf-8"), dict(resp.headers)
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode("utf-8"), dict(e.headers)


def _原始请求(端口, 报文):
    """用原始 socket 发送 HTTP 报文，返回 (状态码, 响应体文本)。"""
    with socket.create_connection(("127.0.0.1", 端口), timeout=5) as sock:
        sock.sendall(报文.encode("utf-8"))
        chunks = []
        while True:
            data = sock.recv(4096)
            if not data:
                break
            chunks.append(data)
    响应 = b"".join(chunks).decode("utf-8", errors="replace")
    状态行, _, 响应体 = 响应.partition("\r\n\r\n")
    return int(状态行.split()[1]), 响应体


def test_精确路由_get_正常响应():
    server = DaoHttpServer()
    server.路由("GET", "/hello", lambda req: {"状态码": 200, "内容": "你好，世界"})
    thread = _启动(server)
    try:
        状态码, 响应体, _ = _请求(server.端口, "/hello")
        assert 状态码 == 200
        assert 响应体 == "你好，世界"
    finally:
        _关闭(server, thread)


def test_post_json_body与自定义请求头():
    server = DaoHttpServer()

    def 处理函数(req):
        令牌 = None
        for key, value in req["请求头"].items():
            if key.lower() == "x-token":
                令牌 = value
        数据 = req.JSON()
        return {"状态码": 201, "内容": {"消息": 数据["消息"], "令牌": 令牌}}

    server.路由("POST", "/webhook", 处理函数)
    thread = _启动(server)
    try:
        请求体 = json.dumps({"消息": "你好", "数量": 3}).encode("utf-8")
        状态码, 响应体, _ = _请求(
            server.端口,
            "/webhook",
            方法="POST",
            数据=请求体,
            请求头={"Content-Type": "application/json", "X-Token": "secret"},
        )
        assert 状态码 == 201
        assert json.loads(响应体) == {"消息": "你好", "令牌": "secret"}
    finally:
        _关闭(server, thread)


def test_两个并发请求能同时被处理():
    server = DaoHttpServer()
    已进入 = threading.Event()
    放行 = threading.Event()

    def 慢处理(req):
        已进入.set()
        放行.wait(5)
        return {"状态码": 200, "内容": "slow"}

    def 快处理(req):
        return {"状态码": 200, "内容": "fast"}

    server.路由("GET", "/slow", 慢处理)
    server.路由("GET", "/fast", 快处理)
    thread = _启动(server)
    结果 = {}
    try:
        慢线程 = threading.Thread(
            target=lambda: 结果.setdefault("慢", _请求(server.端口, "/slow")),
            daemon=True,
        )
        慢线程.start()
        assert 已进入.wait(3), "慢请求未被处理"
        # 慢请求仍阻塞在 放行.wait() 时，快请求必须立即返回；
        # 若服务器为单线程，此处会一直阻塞直到测试超时。
        状态码, 响应体, _ = _请求(server.端口, "/fast")
        assert 状态码 == 200 and 响应体 == "fast"
    finally:
        放行.set()
        _关闭(server, thread)
    慢线程.join(timeout=5)
    assert "慢" in 结果
    assert 结果["慢"][0] == 200 and 结果["慢"][1] == "slow"


def test_前缀通配路由匹配():
    server = DaoHttpServer()
    server.路由(
        "POST",
        "/webhooks/*",
        lambda req: {"状态码": 200, "内容": req["路径"]},
    )
    thread = _启动(server)
    try:
        状态码, 响应体, _ = _请求(
            server.端口,
            "/webhooks/push",
            方法="POST",
            数据=b"{}",
            请求头={"Content-Type": "application/json"},
        )
        assert 状态码 == 200
        assert 响应体 == "/webhooks/push"
        # query string 存在时仍按前缀匹配
        状态码, 响应体, _ = _请求(
            server.端口,
            "/webhooks/push?source=github",
            方法="POST",
            数据=b"{}",
        )
        assert 状态码 == 200
        assert 响应体.startswith("/webhooks/push")
    finally:
        _关闭(server, thread)


def test_精确路由优先于通配且最长通配优先():
    server = DaoHttpServer()
    server.路由("GET", "/items/*", lambda req: {"状态码": 200, "内容": "通配"})
    server.路由("GET", "/items/special/*", lambda req: {"状态码": 200, "内容": "更具体通配"})
    server.路由("GET", "/items/exact", lambda req: {"状态码": 200, "内容": "精确"})
    thread = _启动(server)
    try:
        assert _请求(server.端口, "/items/exact")[1] == "精确"
        assert _请求(server.端口, "/items/special/abc")[1] == "更具体通配"
        assert _请求(server.端口, "/items/random")[1] == "通配"
    finally:
        _关闭(server, thread)


def test_未匹配路由返回404():
    server = DaoHttpServer()
    server.路由("GET", "/exists", lambda req: {"状态码": 200, "内容": "ok"})
    thread = _启动(server)
    try:
        状态码, 响应体, _ = _请求(server.端口, "/missing")
        assert 状态码 == 404
        assert "未找到" in 响应体
    finally:
        _关闭(server, thread)


def test_请求体超过上限返回413():
    server = DaoHttpServer(最大请求体=10)
    server.路由("POST", "/upload", lambda req: {"状态码": 200, "内容": "ok"})
    thread = _启动(server)
    try:
        状态码, 响应体, _ = _请求(
            server.端口,
            "/upload",
            方法="POST",
            数据=b"x" * 100,
        )
        assert 状态码 == 413
        assert "过大" in 响应体
    finally:
        _关闭(server, thread)


def test_非法Content_Length返回400():
    server = DaoHttpServer()
    server.路由("POST", "/echo", lambda req: {"状态码": 200, "内容": "ok"})
    thread = _启动(server)
    try:
        报文 = (
            "POST /echo HTTP/1.1\r\nHost: localhost\r\n"
            "Content-Length: abc\r\nConnection: close\r\n\r\n"
        )
        状态码, 响应体 = _原始请求(server.端口, 报文)
        assert 状态码 == 400
        assert "长度" in 响应体
    finally:
        _关闭(server, thread)


def test_关闭后线程退出且可重复调用():
    server = DaoHttpServer()
    server.路由("GET", "/ping", lambda req: {"状态码": 200, "内容": "pong"})
    thread = _启动(server)
    状态码, 响应体, _ = _请求(server.端口, "/ping")
    assert 状态码 == 200 and 响应体 == "pong"
    server.关闭()
    thread.join(timeout=5)
    assert not thread.is_alive()
    # 重复调用不报错
    server.关闭()
    server.关闭()


def test_未启动时关闭是空操作():
    server = DaoHttpServer()
    server.关闭()
    assert server.端口 is None


def test_处理函数抛异常返回500():
    server = DaoHttpServer()

    def 出错(req):
        raise ValueError("故意出错")

    server.路由("GET", "/boom", 出错)
    thread = _启动(server)
    try:
        状态码, 响应体, _ = _请求(server.端口, "/boom")
        assert 状态码 == 500
        assert "故意出错" in 响应体
    finally:
        _关闭(server, thread)


class _假道函数(DaoCallable):
    """最小 DaoCallable 替身，用于验证服务器回调解释器路径。"""

    def __init__(self, 返回内容):
        self.返回内容 = 返回内容


def test_道语言函数作为路由处理函数经解释器回调():
    """看板等脚本注册的道函数不是 Python callable，必须借解释器回调。"""
    server = DaoHttpServer()
    解释器 = MagicMock()
    解释器.call_function.side_effect = lambda func, args, kwargs=None: {
        "状态码": 200,
        "内容": f"道函数响应:{args[0]['路径']}",
    }
    server.interpreter = 解释器
    server.路由("GET", "/dao", _假道函数("占位"))
    thread = _启动(server)
    try:
        状态码, 响应体, _ = _请求(server.端口, "/dao")
        assert 状态码 == 200
        assert 响应体 == "道函数响应:/dao"
        解释器.call_function.assert_called_once()
    finally:
        _关闭(server, thread)


def test_中文路由经百分号编码后能匹配():
    """浏览器/curl 会把中文路径编码成 %XX，服务器须解码后再匹配路由。"""
    server = DaoHttpServer()
    server.路由("GET", "/审计", lambda req: {"状态码": 200, "内容": "审计页"})
    thread = _启动(server)
    try:
        状态码, 响应体, _ = _请求(server.端口, urllib.parse.quote("/审计"))
        assert 状态码 == 200
        assert 响应体 == "审计页"
    finally:
        _关闭(server, thread)


def test_道函数处理函数在无解释器时返回500():
    """未绑定解释器时给出明确中文提示，而非静默 500。"""
    server = DaoHttpServer()
    server.路由("GET", "/dao", _假道函数("占位"))
    thread = _启动(server)
    try:
        状态码, 响应体, _ = _请求(server.端口, "/dao")
        assert 状态码 == 500
        assert "未绑定解释器" in 响应体
    finally:
        _关闭(server, thread)
