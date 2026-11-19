# 14. LSP 语言服务器

"道"语言提供一个基于 Language Server Protocol（LSP）的语言服务器，让 VS Code、Neovim 等编辑器获得语法诊断、补全、悬停、跳转与大纲视图等能力。

服务器使用 **纯 Python 标准库** 实现（`json`、`re`、`sys`、`io` 等），通过 **JSON-RPC 2.0 over stdio** 与编辑器通信，不依赖 `pygls` 等任何第三方库。消息采用 `Content-Length` 帧头，长度按正文 **UTF-8 编码后的字节数** 计算，天然支持中文源码与中文诊断消息。

## 14.1 能力清单

| 能力 | LSP 方法 | 说明 |
|------|----------|------|
| 生命周期 | `initialize` / `initialized` / `shutdown` / `exit` | 返回 `serverInfo` 与 `capabilities` |
| 文档同步 | `textDocument/didOpen` / `didChange` / `didClose` | 全量同步（`textDocumentSync = 1`），内存维护文档 |
| 诊断 | `textDocument/publishDiagnostics` | 调用 `Lexer` / `Parser` 捕获词法、语法错误，转为中文诊断 |
| 补全 | `textDocument/completion` | 关键字、内置函数、标准库模块名、文档内标识符 |
| 悬停 | `textDocument/hover` | 关键字、内置函数、标准库模块的中文说明 |
| 跳转 | `textDocument/definition` | 当前文档内的函数 / 类 / 变量定义位置 |
| 符号 | `textDocument/documentSymbol` | 基于 AST 的大纲符号（含类成员等嵌套子符号） |

诊断消息一律为中文，来源标记为 `道语言`；错误类型（`词法错误` / `语法错误`）作为消息前缀。LSP 使用 **0-based** 行列，服务器会把道语言错误与 AST 的 **1-based** 行列统一转换（并对个别携带 `0` 坐标的词法错误做下限钳制，避免出现负坐标）。

## 14.2 启动方式

在 `源码` 目录下以模块方式启动（务必使用项目隔离解释器，保证依赖一致）：

```bash
cd 源码 && ./.venv/bin/python -m dao.lsp
```

服务器启动后从 **stdin** 读取 JSON-RPC 帧、向 **stdout** 写回帧。除协议帧外不会向 stdout 打印任何内容（日志、调试信息都不得写入 stdout，否则会破坏帧流）。收到 `exit` 通知或输入流关闭（EOF）时正常退出；未经 `shutdown` 直接 `exit` 时退出码为 `1`。

> 提示：单独运行该命令时终端会等待输入，属正常现象；服务器设计为由编辑器作为子进程托管。

## 14.3 模块结构

代码位于 `源码/dao/lsp/`：

| 文件 | 职责 |
|------|------|
| `protocol.py` | JSON-RPC 帧编解码：`encode_message` / `write_message` / `read_message`，`Content-Length` 按 UTF-8 字节数计算 |
| `features.py` | 与传输解耦的语言特性：诊断、补全、悬停、符号、跳转、光标取词 |
| `server.py` | `LanguageServer` 类：生命周期、文档同步、请求分派、`serve()` stdio 主循环 |
| `__main__.py` | `python -m dao.lsp` 入口 |
| `__init__.py` | 导出 `LanguageServer` |

`features.py` 依赖现有前端组件，不重复实现解析逻辑：

- `dao.lexer.Lexer(source).tokenize()` 与 `dao.parser.Parser(tokens).parse()` 做诊断与符号提取；
- `dao.tokens.KEYWORDS` 提供关键字；
- `dao.builtins.functions.get_builtins()` 与 `dao.builtins.hof.get_interpreter_builtins()` 提供内置函数名；
- `dao.stdlib.registry.STDLIB_REGISTRY` 提供标准库模块名；
- `dao.errors.道错误` 及其子类携带 `.line` / `.column` / `.message`。

所有对分析器的调用都做了异常兜底：源码有错时特性函数仍返回已有信息（例如补全继续返回静态候选与正则提取的标识符），单个消息的处理异常会被兜底为 JSON-RPC 错误响应，服务器不会崩溃。

## 14.4 VS Code 最小配置

VS Code 需通过一个微型扩展，用 `vscode-languageclient` 启动本服务器。先在扩展的 `package.json` 中把 `.道` 文件关联到语言 id `dao`：

```json
{
  "contributes": {
    "languages": [{
      "id": "dao",
      "extensions": [".道"],
      "aliases": ["道", "Dao"]
    }]
  }
}
```

`extension.js`（把 `道项目根目录` 替换为实际绝对路径）：

```javascript
const path = require('path');
const { LanguageClient, TransportKind } = require('vscode-languageclient/node');

let client;
function activate(context) {
  const root = path.join('道项目根目录', '源码');
  const serverOptions = {
    command: path.join(root, '.venv', 'bin', 'python'),
    args: ['-m', 'dao.lsp'],
    options: { cwd: root },
    transport: TransportKind.stdio,
  };
  const clientOptions = {
    documentSelector: [{ scheme: 'file', language: 'dao' }],
  };
  client = new LanguageClient('dao', '道语言服务器', serverOptions, clientOptions);
  client.start();
}
function deactivate() {
  return client ? client.stop() : undefined;
}
module.exports = { activate, deactivate };
```

`vscode-languageclient` 仅是编辑器侧客户端依赖，服务器本身仍是零第三方依赖的 Python 进程。

## 14.5 Neovim 最小配置

Neovim 0.8+ 可用内置 LSP API，无需额外插件（同样把路径替换为实际绝对路径），写入 `init.lua`：

```lua
vim.filetype.add({ extension = { dao = 'dao' } })

vim.api.nvim_create_autocmd('FileType', {
  pattern = 'dao',
  callback = function()
    vim.lsp.start({
      name = 'dao_ls',
      cmd = {
        '/道项目根目录/源码/.venv/bin/python',
        '-m', 'dao.lsp',
      },
      root_dir = vim.fn.getcwd(),
    })
  end,
})
```

若使用 `nvim-lspconfig`，也可注册一个自定义 server：

```lua
local configs = require('lspconfig.configs')
configs.dao_ls = {
  default_config = {
    cmd = { '/道项目根目录/源码/.venv/bin/python', '-m', 'dao.lsp' },
    filetypes = { 'dao' },
    root_dir = function() return vim.fn.getcwd() end,
  },
}
require('lspconfig').dao_ls.setup({})
```

## 14.6 协议限制

当前实现聚焦"可用"的最小闭环，存在以下限制：

- **全量同步**：`didChange` 每帧都是完整文本，未实现增量同步（`textDocumentSync = 2`）。
- **补全无上下文**：返回全部候选，不做前缀 / 作用域 / 类型推断过滤，由客户端按 `label` 自行筛选；不支持 `completionItem/resolve`。
- **诊断仅前端**：只覆盖词法与语法错误，不做类型检查、未定义变量检查或运行时诊断；一次分析只上报第一条错误。
- **跳转仅当前文档**：`definition` 在已解析 AST 内按名字查找，不解析 `导入` 的跨文件 / 跨模块符号。
- **符号覆盖有限**：`documentSymbol` 收集函数、类、变量、枚举、特征、宏、逻辑块等声明节点及其直接子体；控制流语句（如 `如果` 分支）内部的声明可能不出现在大纲中；由于 AST 不记录结束位置，`range` 以声明所在行行末为终点。
- **悬停范围**：仅关键字、内置函数、标准库模块有中文说明，不含用户自定义符号的签名或文档注释。
- **无工作区能力**：不提供 `workspace/symbol`、引用查找、重命名、格式化、语义高亮、代码操作（quick fix）、折叠范围等。
- **行列单位**：按 Unicode 码点计算。中文等 BMP 字符与 LSP 的 UTF-16 code unit 一致；增补平面字符（如部分 emoji）的列偏移可能有偏差。
- **无取消 / 进度 / 配置**：不处理 `$/cancelRequest`、`$/progress`、`workspace/configuration` 等高级交互；损坏的帧会被跳过而非报错退出。

## 14.7 后续可扩展点

- 增量文档同步与触发字符、`completionItem/resolve` 惰性补全；
- 基于符号表的跨文件索引，扩展 `definition`、`references`、`rename`、`workspace/symbol`；
- 接入 `dao/types` 做类型检查诊断，并提供 `codeAction` 快速修复；
- 悬停展示用户函数签名、参数与 `///` 文档注释；
- `documentHighlight`、`foldingRange`、`semanticTokens`、`documentFormatting` 等编辑增强；
- 语义化诊断分级（错误 / 警告 / 提示）与多错误聚合上报；
- 支持 `workspace/didChangeWatchedFiles` 与项目级配置，缓存解析结果以降低重复分析开销。
