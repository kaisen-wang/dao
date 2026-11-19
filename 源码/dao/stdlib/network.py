import json
import urllib.parse
import urllib.request

from ..builtins.callables import BuiltinFunction
from ..environment import Environment
from ..errors import 运行时错误


def _解析JSON文本(文本, 来源):
    """把文本解析为道语言数据结构（list/dict），失败时抛出中文错误。"""
    if not isinstance(文本, str):
        raise 运行时错误(f"{来源}不是文本类型，无法解析为JSON")
    try:
        return json.loads(文本)
    except (ValueError, TypeError) as e:
        raise 运行时错误(f"{来源}不是有效的JSON格式，无法解析: {e}")


class DaoHttpResponse:
    def __init__(self, status_code: int, headers: dict, body: str):
        self.状态码 = status_code
        self.响应头 = headers
        self.响应体 = body

    def JSON(self):
        """把响应体解析为道语言数据结构（list/dict）。"""
        return _解析JSON文本(self.响应体, "响应体")

    def __repr__(self):
        return f"<HTTP响应 状态码={self.状态码}>"


class DaoHttpRequest(dict):
    """HTTP 请求对象：兼容 dict 接口，并提供 JSON() 解析请求体。"""

    def __init__(self, 方法, 路径, 请求头, 请求体):
        super().__init__(方法=方法, 路径=路径, 请求头=请求头, 请求体=请求体)

    def JSON(self):
        """把请求体解析为道语言数据结构（list/dict）。"""
        return _解析JSON文本(self["请求体"], "请求体")


class DaoHttpServer:
    def __init__(self):
        self._routes: list[tuple] = []

    def 路由(self, 方法, 路径, 处理函数):
        self._routes.append((方法, 路径, 处理函数))

    def 启动(self, 端口=8080):
        from http.server import HTTPServer, BaseHTTPRequestHandler

        routes = self._routes

        class DaoHandler(BaseHTTPRequestHandler):
            def do_GET(self):
                self._handle("GET")

            def do_POST(self):
                self._handle("POST")

            def do_PUT(self):
                self._handle("PUT")

            def do_DELETE(self):
                self._handle("DELETE")

            def _handle(self, method):
                for route_method, route_path, handler in routes:
                    if route_method == method and route_path == self.path:
                        content_length = int(self.headers.get("Content-Length", 0))
                        body = self.rfile.read(content_length).decode("utf-8") if content_length else ""
                        request_obj = DaoHttpRequest(method, self.path, dict(self.headers), body)
                        try:
                            if isinstance(handler, BuiltinFunction):
                                result = handler.call([request_obj], {})
                            elif callable(handler):
                                result = handler(request_obj)
                            else:
                                result = {"状态码": 500, "内容": "处理函数无效"}

                            if isinstance(result, dict):
                                status_code = result.get("状态码", 200)
                                content = result.get("内容", "")
                                self.send_response(status_code)
                                self.send_header("Content-Type", "application/json; charset=utf-8")
                                self.end_headers()
                                if isinstance(content, str):
                                    self.wfile.write(content.encode("utf-8"))
                                else:
                                    import json
                                    self.wfile.write(json.dumps(content, ensure_ascii=False).encode("utf-8"))
                            else:
                                self.send_response(200)
                                self.end_headers()
                                self.wfile.write(str(result).encode("utf-8"))
                        except Exception as e:
                            self.send_response(500)
                            self.end_headers()
                            self.wfile.write(f"服务器错误: {e}".encode("utf-8"))
                        return
                self.send_response(404)
                self.end_headers()
                self.wfile.write("未找到路由".encode("utf-8"))

            def log_message(self, format, *args):
                pass

        try:
            server = HTTPServer(("", 端口), DaoHandler)
            server.serve_forever()
        except OSError as e:
            raise 运行时错误(f"无法启动服务器: {e}")

    def __repr__(self):
        return f"<HTTP服务器 路由数={len(self._routes)}>"


def _stdlib_请求(URL, 选项=None):
    if 选项 is None:
        选项 = {}
    method = 选项.get("方法", "GET")
    headers = 选项.get("请求头", {})
    data = 选项.get("数据", None)
    timeout = 选项.get("超时", 30)

    req = urllib.request.Request(URL, method=method)
    for key, value in headers.items():
        req.add_header(key, value)

    if data is not None:
        if isinstance(data, str):
            req.data = data.encode("utf-8")
        else:
            req.data = str(data).encode("utf-8")

    try:
        with urllib.request.urlopen(req, timeout=timeout) as response:
            body = response.read().decode("utf-8")
            resp_headers = dict(response.headers)
            return DaoHttpResponse(response.status, resp_headers, body)
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8") if e.fp else ""
        return DaoHttpResponse(e.code, dict(e.headers), body)
    except urllib.error.URLError as e:
        raise 运行时错误(f"请求失败: {e.reason}")
    except Exception as e:
        raise 运行时错误(f"请求异常: {e}")


def _stdlib_创建服务器():
    return DaoHttpServer()


def _stdlib_URL编码(文本):
    if not isinstance(文本, str):
        raise 运行时错误("URL编码需要文本类型参数")
    return urllib.parse.quote(文本)


def _stdlib_URL解码(文本):
    if not isinstance(文本, str):
        raise 运行时错误("URL解码需要文本类型参数")
    return urllib.parse.unquote(文本)


def create_module_env(interpreter=None) -> Environment:
    env = Environment()
    env.define("请求", BuiltinFunction("请求", _stdlib_请求, -1))
    env.define("创建服务器", BuiltinFunction("创建服务器", _stdlib_创建服务器, 0))
    env.define("URL编码", BuiltinFunction("URL编码", _stdlib_URL编码, 1))
    env.define("URL解码", BuiltinFunction("URL解码", _stdlib_URL解码, 1))
    env.exports = list(env.values.keys())
    return env