import json
import urllib.error
import urllib.parse
import urllib.request

from ..builtins.callables import BuiltinFunction, DaoCallable, InterpreterBuiltin
from ..environment import Environment
from ..errors import 类型错误, 运行时错误, 道错误


def _解析JSON文本(文本, 来源):
    """把文本解析为道语言数据结构（list/dict），失败时抛出中文错误。"""
    if not isinstance(文本, str):
        raise 运行时错误(f"{来源}不是文本类型，无法解析为JSON")
    try:
        return json.loads(文本)
    except (ValueError, TypeError) as e:
        raise 运行时错误(f"{来源}不是有效的JSON格式，无法解析: {e}")


class DaoHttpResponse:
    """HTTP 响应对象，包含状态码、响应头与响应体。"""

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
    """HTTP 服务器对象，可注册路由并启动监听。"""

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
    """发起 HTTP 请求并返回响应对象。

    参数：选项可指定方法、请求头、数据与超时，默认使用 GET 方法。
    """
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


def _执行流式请求(URL, 选项, 处理函数, interpreter):
    """逐行读取 HTTP 响应，把每一行交给道语言回调处理。

    与「请求」不同，这里不会一次性 read() 完整个响应体；每读到一行就立即
    回调「处理函数」，因此可以边收边打印（ollama /api/chat 的 NDJSON 流、
    SSE 等）。回调收到一行原始文本，返回「假」可提前终止读取。

    参数：选项为「方法/请求头/数据/超时」字典；返回实际回调的行数。
    """
    if interpreter is None:
        raise 运行时错误("流式请求无法获取解释器上下文")
    if not isinstance(URL, str):
        raise 类型错误("流式请求的 URL 必须是文本类型")
    if not isinstance(处理函数, DaoCallable):
        raise 类型错误("流式请求的处理函数必须是函数")
    if 选项 is None:
        选项 = {}
    if not isinstance(选项, dict):
        raise 类型错误("流式请求的选项必须是字典")

    method = 选项.get("方法", "GET")
    headers = 选项.get("请求头", {})
    data = 选项.get("数据", None)
    timeout = 选项.get("超时", 30)

    req = urllib.request.Request(URL, method=method)
    for key, value in headers.items():
        req.add_header(key, value)
    if data is not None:
        req.data = data.encode("utf-8") if isinstance(data, str) else str(data).encode("utf-8")

    行数 = 0
    try:
        with urllib.request.urlopen(req, timeout=timeout) as response:
            while True:
                raw = response.readline()
                if not raw:
                    break
                行 = raw.decode("utf-8", errors="replace") if isinstance(raw, bytes) else str(raw)
                行 = 行.strip()
                if not 行:
                    continue
                行数 += 1
                # 回调返回「假」表示提前结束；道语言的异常原样向上传播
                if interpreter.call_function(处理函数, [行]) is False:
                    break
    except 道错误:
        raise
    except urllib.error.HTTPError as e:
        体 = e.read().decode("utf-8", errors="replace") if e.fp else ""
        raise 运行时错误(f"流式请求失败: HTTP {e.code} {体}") from None
    except urllib.error.URLError as e:
        raise 运行时错误(f"流式请求失败: {e.reason}") from None
    except Exception as e:  # noqa: BLE001 - 兜底转成中文运行时错误
        raise 运行时错误(f"流式请求异常: {e}") from None
    return 行数


def _流式请求实现(interpreter, URL, 选项, 处理函数):
    """逐行读取 HTTP 响应并回调处理函数，返回读取的行数。

    参数：选项与「请求」相同（方法/请求头/数据/超时）；处理函数收到一行
    原始文本，返回「假」可提前终止。适用于 ollama 流式 NDJSON、SSE 等。
    """
    return _执行流式请求(URL, 选项, 处理函数, interpreter)


def _stdlib_创建服务器():
    """创建一个 HTTP 服务器对象。"""
    return DaoHttpServer()


def _stdlib_URL编码(文本):
    """对文本进行 URL 编码。"""
    if not isinstance(文本, str):
        raise 运行时错误("URL编码需要文本类型参数")
    return urllib.parse.quote(文本)


def _stdlib_URL解码(文本):
    """对 URL 编码的文本进行解码。"""
    if not isinstance(文本, str):
        raise 运行时错误("URL解码需要文本类型参数")
    return urllib.parse.unquote(文本)


def create_module_env(interpreter=None) -> Environment:
    """创建网络模块的导出环境。"""
    env = Environment()
    env.define("请求", BuiltinFunction("请求", _stdlib_请求, -1))
    env.define("创建服务器", BuiltinFunction("创建服务器", _stdlib_创建服务器, 0))
    env.define("URL编码", BuiltinFunction("URL编码", _stdlib_URL编码, 1))
    env.define("URL解码", BuiltinFunction("URL解码", _stdlib_URL解码, 1))

    # 用 InterpreterBuiltin 取得当前解释器才能回调道语言函数；
    # func 定义在模块级，保证工厂重复调用时元数据稳定（docgen 依赖此约束）。
    流式请求 = InterpreterBuiltin("流式请求", _流式请求实现, 3)
    if interpreter is not None:
        流式请求.set_interpreter(interpreter)
    env.define("流式请求", 流式请求)
    env.exports = list(env.values.keys())
    return env
