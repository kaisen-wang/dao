import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from dao.stdlib.network import (
    _stdlib_URL编码, _stdlib_URL解码, _stdlib_创建服务器,
    DaoHttpServer,
    create_module_env,
)
from dao.errors import 运行时错误


class TestUrlEncodeDecode:
    def test_url_encode(self):
        result = _stdlib_URL编码("你好 世界")
        assert "%" in result

    def test_url_decode(self):
        encoded = _stdlib_URL编码("你好")
        decoded = _stdlib_URL解码(encoded)
        assert decoded == "你好"

    def test_url_encode_non_string(self):
        try:
            _stdlib_URL编码(123)
            assert False, "应抛出运行时错误"
        except 运行时错误:
            pass

    def test_url_decode_non_string(self):
        try:
            _stdlib_URL解码(123)
            assert False, "应抛出运行时错误"
        except 运行时错误:
            pass


class TestHttpServer:
    def test_create_server(self):
        server = _stdlib_创建服务器()
        assert isinstance(server, DaoHttpServer)

    def test_server_add_route(self):
        server = DaoHttpServer()
        server.路由("GET", "/你好", lambda req: {"状态码": 200, "内容": "你好"})
        assert len(server._routes) == 1


class TestNetworkModuleEnv:
    def test_create_module_env(self):
        env = create_module_env()
        assert "请求" in env.values
        assert "URL编码" in env.values