import io
import os
import sys
from unittest.mock import MagicMock, patch

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from urllib.error import HTTPError, URLError

from dao.stdlib.network import (
    _stdlib_URL编码, _stdlib_URL解码, _stdlib_创建服务器, _stdlib_请求,
    DaoHttpServer, DaoHttpResponse, create_module_env,
)
from dao.errors import 运行时错误
from dao.builtins.callables import BuiltinFunction


class TestUrlEncodeDecode:
    def test_url_encode(self):
        result = _stdlib_URL编码("你好 世界")
        assert "%" in result

    def test_url_decode(self):
        encoded = _stdlib_URL编码("你好")
        assert _stdlib_URL解码(encoded) == "你好"

    def test_url_encode_non_string(self):
        with pytest.raises(运行时错误, match="URL编码需要文本类型"):
            _stdlib_URL编码(123)

    def test_url_decode_non_string(self):
        with pytest.raises(运行时错误, match="URL解码需要文本类型"):
            _stdlib_URL解码(123)


class TestHttpServer:
    def test_create_server(self):
        assert isinstance(_stdlib_创建服务器(), DaoHttpServer)

    def test_server_add_route(self):
        server = DaoHttpServer()
        server.路由("GET", "/你好", lambda req: {"状态码": 200, "内容": "你好"})
        assert len(server._routes) == 1


class TestNetworkModuleEnv:
    def test_create_module_env(self):
        env = create_module_env()
        for name in ("请求", "创建服务器", "URL编码", "URL解码"):
            assert name in env.values
        assert set(env.exports) == {"请求", "创建服务器", "URL编码", "URL解码"}


class _FakeResponse:
    """urllib 响应对象的替身，支持 with 语句"""

    def __init__(self, status=200, headers=None, body=b"hello"):
        self.status = status
        self.headers = headers if headers is not None else {"Content-Type": "text/plain"}
        self._body = body

    def read(self):
        return self._body

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False


class TestHttpRequest:
    def test_request_success(self):
        fake = _FakeResponse(200, {"X-Test": "1"}, "你好".encode("utf-8"))
        with patch("urllib.request.urlopen", return_value=fake) as mock_open:
            resp = _stdlib_请求("http://example.com")
        assert isinstance(resp, DaoHttpResponse)
        assert resp.状态码 == 200
        assert resp.响应头 == {"X-Test": "1"}
        assert resp.响应体 == "你好"
        req = mock_open.call_args[0][0]
        assert req.get_method() == "GET"
        assert mock_open.call_args.kwargs["timeout"] == 30

    def test_request_with_options(self):
        fake = _FakeResponse(201, {}, b"ok")
        opts = {
            "方法": "POST",
            "请求头": {"Authorization": "token"},
            "数据": "名称=值",
            "超时": 5,
        }
        with patch("urllib.request.urlopen", return_value=fake) as mock_open:
            resp = _stdlib_请求("http://example.com", opts)
        req = mock_open.call_args[0][0]
        assert req.get_method() == "POST"
        assert req.data == "名称=值".encode("utf-8")
        assert req.get_header("Authorization") == "token"
        assert mock_open.call_args.kwargs["timeout"] == 5
        assert resp.状态码 == 201
        assert resp.响应体 == "ok"

    def test_request_with_non_string_data(self):
        fake = _FakeResponse()
        with patch("urllib.request.urlopen", return_value=fake) as mock_open:
            _stdlib_请求("http://example.com", {"数据": 123})
        assert mock_open.call_args[0][0].data == b"123"

    def test_request_http_error(self):
        err = HTTPError(
            "http://example.com", 404, "Not Found", {"X-Err": "1"},
            io.BytesIO("缺失".encode("utf-8")),
        )
        with patch("urllib.request.urlopen", side_effect=err):
            resp = _stdlib_请求("http://example.com")
        assert resp.状态码 == 404
        assert resp.响应体 == "缺失"
        assert resp.响应头.get("X-Err") == "1"

    def test_request_http_error_without_body(self):
        err = HTTPError("http://example.com", 500, "err", {}, None)
        with patch("urllib.request.urlopen", side_effect=err):
            resp = _stdlib_请求("http://example.com")
        assert resp.状态码 == 500 and resp.响应体 == ""

    def test_request_url_error(self):
        with patch("urllib.request.urlopen", side_effect=URLError("连接失败")):
            with pytest.raises(运行时错误, match="请求失败"):
                _stdlib_请求("http://example.com")

    def test_request_generic_error(self):
        with patch("urllib.request.urlopen", side_effect=ValueError("意外")):
            with pytest.raises(运行时错误, match="请求异常"):
                _stdlib_请求("http://example.com")


def _capture_handler(routes, port=8080):
    """启动服务器（拦截阻塞），返回内部生成的 DaoHandler 类"""
    server = DaoHttpServer()
    for route in routes:
        server.路由(*route)
    captured = {}

    class FakeServer:
        def __init__(self, addr, handler_cls):
            captured["addr"] = addr
            captured["handler"] = handler_cls

        def serve_forever(self):
            captured["served"] = True

    with patch("http.server.HTTPServer", FakeServer):
        server.启动(port)
    return captured


def _make_handler(handler_cls, path, headers=None, body=b""):
    """用 object.__new__ 构造 handler 实例，绕过真实的 socket 初始化"""
    handler = object.__new__(handler_cls)
    handler.path = path
    handler.headers = headers if headers is not None else {}
    handler.rfile = io.BytesIO(body)
    handler.wfile = io.BytesIO()
    handler.send_response = MagicMock()
    handler.send_header = MagicMock()
    handler.end_headers = MagicMock()
    return handler


class TestHttpServerHandler:
    def test_server_start_and_dict_route(self):
        captured = _capture_handler([
            ("GET", "/你好", lambda req: {"状态码": 201, "内容": {"消息": "你好"}})
        ])
        assert captured["addr"] == ("", 8080)
        assert captured["served"] is True
        handler = _make_handler(captured["handler"], "/你好", {"Content-Length": "0"})
        handler.do_GET()
        assert "你好" in handler.wfile.getvalue().decode("utf-8")
        handler.send_response.assert_called_with(201)
        handler.send_header.assert_called()

    def test_server_post_with_body(self):
        captured = _capture_handler([
            ("POST", "/回显", lambda req: {"状态码": 200, "内容": req["请求体"]})
        ])
        handler = _make_handler(
            captured["handler"], "/回显", {"Content-Length": "5"}, b"abcde"
        )
        handler.do_POST()
        assert "abcde" in handler.wfile.getvalue().decode("utf-8")

    def test_server_builtin_handler(self):
        bf = BuiltinFunction("h", lambda req: {"状态码": 200, "内容": "内置"})
        captured = _capture_handler([("GET", "/b", bf)])
        handler = _make_handler(captured["handler"], "/b")
        handler.do_GET()
        assert "内置" in handler.wfile.getvalue().decode("utf-8")

    def test_server_invalid_handler(self):
        captured = _capture_handler([("GET", "/bad", 12345)])
        handler = _make_handler(captured["handler"], "/bad")
        handler.do_GET()
        handler.send_response.assert_called_with(500)
        assert "处理函数无效" in handler.wfile.getvalue().decode("utf-8")

    def test_server_handler_exception(self):
        def boom(req):
            raise ValueError("崩溃")

        captured = _capture_handler([("GET", "/err", boom)])
        handler = _make_handler(captured["handler"], "/err")
        handler.do_GET()
        handler.send_response.assert_called_with(500)
        assert "服务器错误" in handler.wfile.getvalue().decode("utf-8")

    def test_server_non_dict_result(self):
        captured = _capture_handler([("GET", "/s", lambda req: "纯文本")])
        handler = _make_handler(captured["handler"], "/s")
        handler.do_GET()
        handler.send_response.assert_called_with(200)
        assert "纯文本" in handler.wfile.getvalue().decode("utf-8")

    def test_server_route_not_found(self):
        captured = _capture_handler([])
        handler = _make_handler(captured["handler"], "/不存在")
        handler.do_PUT()
        handler.send_response.assert_called_with(404)
        assert "未找到路由" in handler.wfile.getvalue().decode("utf-8")
        handler2 = _make_handler(captured["handler"], "/不存在")
        handler2.do_DELETE()
        handler2.send_response.assert_called_with(404)

    def test_server_start_oserror(self):
        with patch("http.server.HTTPServer", side_effect=OSError("端口占用")):
            with pytest.raises(运行时错误, match="无法启动服务器"):
                DaoHttpServer().启动(9999)

    def test_reprs(self):
        assert "HTTP响应" in repr(DaoHttpResponse(200, {}, "x"))
        assert "路由数=0" in repr(DaoHttpServer())
