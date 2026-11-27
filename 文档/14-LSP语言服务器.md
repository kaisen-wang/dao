# 14. LSP 语言服务器

"道"语言提供一个基于 Language Server Protocol（LSP）的语言服务器，让 VS Code、Neovim 等编辑器获得语法诊断、补全、悬停、跳转、大纲视图、格式化与重命名等能力。

服务器使用 **纯 Python 标准库** 实现（`json`、`re`、`sys`、`io` 等），通过 **JSON-RPC 2.0 over stdio** 与编辑器通信，不依赖 `pygls` 等任何第三方库。消息采用 `Content-Length` 帧头，长度按正文 **UTF-8 编码后的字节数** 计算，天然支持中文源码与中文诊断消息。

## 14.1 能力清单

| 能力 | LSP 方法 | 说明 |
|------|----------|------|
| 生命周期 | `initialize` / `initialized` / `shutdown` / `exit` | 返回 `serverInfo` 与 `capabilities` |
| 文档同步 | `textDocument/didOpen` / `didChange` / `didClose` | 增量同步（`textDocumentSync = {openClose: true, change: 2}`），内存维护文档并按 `version` 丢弃乱序变更；兼容全量帧 |
| 诊断 | `textDocument/publishDiagnostics` | 调用 `Lexer` / `Parser` 捕获词法、语法错误，转为中文诊断 |
| 补全 | `textDocument/completion` | 关键字、内置函数、标准库模块名、文档内标识符；按前缀与作用域分层过滤，声明 `triggerCharacters`，支持 `completionItem/resolve` |
| 悬停 | `textDocument/hover` | 关键字、内置函数、标准库模块及用户声明的中文说明与签名 |
| 跳转 | `textDocument/definition` / `textDocument/references` | 当前文档与跨文件（解析 `导入`）的定义跳转；工作区内引用查找 |
| 符号 | `textDocument/documentSymbol` | 基于 AST 的大纲符号（含类成员等嵌套子符号） |
| 格式化 | `textDocument/formatting` | 基于缩进的整篇规范化：统一缩进宽度、删除行尾空白、折叠空行、规范关键字与赋值号空格；字符串与注释内容原样保留 |
| 重命名 | `textDocument/rename` / `textDocument/prepareRename` | 基于工作区引用的标识符重命名，返回 `WorkspaceEdit`；预览返回范围与占位文本，非法目标返回中文错误 |

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
| `formatting.py` | 词法安全的格式化核心：缩进层级栈、空白与空行规范、字符串/注释保护；LSP 与 CLI 共用 |
| `features.py` | 与传输解耦的语言特性：诊断、补全（作用域过滤）、悬停、符号、跳转、引用、重命名编辑、格式化、工作区索引、光标取词 |
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

若使用 `nvim-lspconfig`，仓库已提供可直接贡献上游的 server 配置 `编辑器插件/neovim/lsp/dao_ls.lua`（含 `cmd` / `cmd_cwd` / `filetypes` / `root_dir` / `on_attach` / `capabilities` 等，路径相对插件目录动态推导）。按该文件头部注释注册后即可：

```lua
require('lspconfig').dao_ls.setup({})
```

注意：该配置与 Neovim 插件内置的 `:DaoLspStart` 二选一即可，同时启用会拉起两个客户端。

## 14.6 格式化与重命名使用说明

**编辑器侧格式化**：客户端发送 `textDocument/formatting`，并可在 `options.tabSize` 指定一级缩进的空格数（默认 4，道语言不使用制表符）。服务器返回一个覆盖整篇文档的 `TextEdit`；若源码已符合规范则返回空数组，避免无意义改动。

**编辑器侧重命名**：把光标放在标识符上执行“重命名符号”。服务器先通过 `textDocument/prepareRename` 返回 `{range, placeholder}`（关键字、内置函数与标准库模块名会返回中文错误、不提供预览），再由 `textDocument/rename` 依据 `newName` 返回 `WorkspaceEdit`。作用范围严格限于当前工作区内的 `.道` 文件；未初始化工作区时只改当前文档。字符串字面量与注释中的同名词不会被改写，因此改名前仍建议检查 diff。

**命令行格式化器**：与 LSP 共用 `formatting.py`，适合脚本或 CI 使用（在 `源码` 目录下运行）：

```bash
# 原地格式化一个或多个文件
./.venv/bin/python -m dao.tools.formatter 文件.道 [另一个.道 ...]

# 只检查，不写文件；存在需要格式化的文件时退出码为 1
./.venv/bin/python -m dao.tools.formatter --check 文件.道

# 把格式化结果打印到 stdout，不修改文件（仅限单个文件）
./.venv/bin/python -m dao.tools.formatter --stdout 文件.道

# 指定一级缩进宽度（默认 4）
./.venv/bin/python -m dao.tools.formatter --indent-width 2 文件.道
```

三类模式均保留原文件的 UTF-8 编码与 CRLF/LF 换行风格；`--check` 可用于提交前检查。

## 14.7 协议限制

当前实现聚焦"可用"的最小闭环，存在以下限制：

- **同步以增量为主**：`didChange` 按 `range` 应用编辑（中文等 BMP 字符按 code point 与 UTF-16 一致），无 `range` 的全量帧仍兼容；按 `version` 丢弃乱序 / 重复变更。
- **补全无类型推断**：按前缀与作用域过滤（局部变量 / 参数优先，其次用户声明、静态候选、文档标识符），声明 `triggerCharacters`，支持 `completionItem/resolve`；暂不按类型推断排序。
- **诊断仅前端**：只覆盖词法与语法错误，不做类型检查、未定义变量检查或运行时诊断；一次分析只上报第一条错误。
- **跨文件跳转范围**：`definition` 解析 `导入` / `从…导入` 跳到目标 `.道` 文件的符号，`references` 返回工作区内全部引用；动态拼装的模块路径尚不解析。
- **符号覆盖有限**：`documentSymbol` 收集函数、类、变量、枚举、特征、宏、逻辑块等声明节点及其直接子体；由于 AST 不记录结束位置，`range` 以声明所在行行末为终点。
- **悬停范围**：关键字、内置函数、标准库模块及用户声明有中文说明与签名，不含 `///` 文档注释正文。
- **格式化仅做排版**：统一缩进与空白、折叠空行，不改变 Token 语义；不做语句重排、引号风格统一或 import 排序；跨行字符串所在行的剩余部分不做二次格式化。
- **重命名基于词匹配**：复用工作区 `references` 的文本匹配并过滤字符串/注释，不区分局部变量作用域与同名符号；动态拼装的导入路径、非 `.道` 文件不在范围内。
- **工作区能力有限**：已提供 `references`、重命名与格式化；`workspace/symbol`、语义高亮、代码操作（quick fix）、折叠范围等仍未实现。
- **行列单位**：按 Unicode 码点计算。中文等 BMP 字符与 LSP 的 UTF-16 code unit 一致；增补平面字符（如部分 emoji）的列偏移可能有偏差。
- **无取消 / 进度 / 配置**：不处理 `$/cancelRequest`、`$/progress`、`workspace/configuration` 等高级交互；损坏的帧会被跳过而非报错退出。

## 14.8 后续可扩展点

- 更丰富的触发字符与基于类型推断的补全排序；
- 基于 AST 的作用域感知重命名，区分局部变量与同名符号；
- 扩展 `workspace/symbol`、`documentHighlight`；`definition` / `references` / `rename` / `formatting` 已实现；
- 接入 `dao/types` 做类型检查诊断，并提供 `codeAction` 快速修复；
- 悬停展示用户函数签名、参数与 `///` 文档注释；
- `documentRangeFormatting`、`foldingRange`、`semanticTokens` 等编辑增强；
- 语义化诊断分级（错误 / 警告 / 提示）与多错误聚合上报；
- 支持 `workspace/didChangeWatchedFiles` 与项目级配置，缓存解析结果以降低重复分析开销。
