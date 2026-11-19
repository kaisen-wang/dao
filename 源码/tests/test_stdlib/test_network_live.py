"""真实网络端到端测试（需要联网，离线时自动跳过）。

运行方式：
    .venv313/bin/python -m pytest tests/test_stdlib/test_network_live.py -q

这些测试会访问 httpbin.org（稳定的公开 HTTP 测试服务），超时均控制在 10 秒以内。
"""

import os
import sys
import time
import urllib.request
import warnings

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from dao.errors import 运行时错误
from dao.stdlib.network import DaoHttpResponse, _stdlib_请求

# 本文件不能修改 pytest 配置文件，这里仅抑制自定义 network 标记的未知标记告警
warnings.filterwarnings("ignore", category=pytest.PytestUnknownMarkWarning)

pytestmark = pytest.mark.network

_TIMEOUT = 8  # 单次请求最长等待秒数（≤10s）


def _网络可用():
    """用短超时探测网络连通性，供离线跳过使用。"""
    try:
        with urllib.request.urlopen("https://httpbin.org/get", timeout=_TIMEOUT) as resp:
            return resp.status == 200
    except Exception:
        return False


@pytest.fixture(scope="module")
def 需要网络():
    if os.environ.get("DAO_SKIP_NETWORK") == "1":
        pytest.skip("已通过 DAO_SKIP_NETWORK=1 显式跳过真实网络测试")
    if not _网络可用():
        pytest.skip("离线或网络不可达，跳过真实网络测试")


class TestLiveHttp:
    def test_get_200_状态码与响应头(self, 需要网络):
        resp = _stdlib_请求("https://httpbin.org/get", {"超时": _TIMEOUT})
        assert isinstance(resp, DaoHttpResponse)
        assert resp.状态码 == 200
        assert resp.响应体
        headers_lower = {k.lower(): v for k, v in resp.响应头.items()}
        assert "content-type" in headers_lower
        assert "application/json" in headers_lower["content-type"]

    def test_get_响应体_json解析(self, 需要网络):
        resp = _stdlib_请求("https://httpbin.org/get", {"超时": _TIMEOUT})
        数据 = resp.JSON()
        assert isinstance(数据, dict)
        assert "url" in 数据
        assert "httpbin.org/get" in 数据["url"]
        assert isinstance(数据["headers"], dict)

    def test_http_error_404转为响应对象(self, 需要网络):
        resp = _stdlib_请求("https://httpbin.org/status/404", {"超时": _TIMEOUT})
        assert isinstance(resp, DaoHttpResponse)
        assert resp.状态码 == 404

    def test_无效域名urlerror中文报错(self, 需要网络):
        with pytest.raises(运行时错误, match="请求失败"):
            _stdlib_请求("http://nonexistent-domain-xyz.invalid/", {"超时": 5})

    def test_超时参数生效(self):
        """用本地慢速服务器验证超时参数：走真实 socket，但时序完全可控。

        不用 httpbin 的 /delay/5，因其响应时序受网络波动影响，
        在覆盖率模式等慢速环境下偶发超时断言失败（flaky）。
        """
        import threading
        from http.server import BaseHTTPRequestHandler, HTTPServer

        class 慢速处理器(BaseHTTPRequestHandler):
            def do_GET(self):
                time.sleep(3)
                self.send_response(200)
                self.end_headers()

            def log_message(self, *args):
                pass

        服务器 = HTTPServer(("127.0.0.1", 0), 慢速处理器)
        线程 = threading.Thread(target=服务器.serve_forever, daemon=True)
        线程.start()
        端口 = 服务器.server_address[1]
        try:
            开始 = time.monotonic()
            with pytest.raises(运行时错误, match="请求失败|请求异常"):
                _stdlib_请求(f"http://127.0.0.1:{端口}/slow", {"超时": 1})
            耗时 = time.monotonic() - 开始
            assert 耗时 < 2.5, f"超时参数疑似未生效，实际耗时 {耗时:.2f} 秒"
        finally:
            服务器.shutdown()
            服务器.server_close()
