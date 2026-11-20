# 道语言 Neovim 插件

为「道」语言（中文多范式编程语言）提供文件类型识别、LSP 智能功能、传统正则语法高亮与合理缩进。

适用于 **Neovim 0.8+**（使用内置 `vim.lsp`，无需额外 LSP 客户端插件）。

## 目录结构

```
编辑器插件/neovim/
├── ftdetect/dao.vim    # 识别 *.道 与 *.dao 文件
├── ftplugin/dao.lua    # 启动内置 LSP、设置缩进、定义用户命令
├── lsp/dao_ls.lua      # nvim-lspconfig server 配置（可贡献上游）
├── syntax/dao.vim      # 传统正则语法高亮（无 tree-sitter）
└── README.md
```

## 功能

- **文件类型识别**：打开 `.道` 或 `.dao` 文件自动设置 `filetype=dao`。
- **LSP 智能功能**：诊断（实时报错）、补全、悬停文档、跳转定义、文档符号。
- **语法高亮**：完整关键字表、四种注释、字符串与模板字符串、数值、逻辑变量、宏调用、管道等。
- **缩进**：4 空格缩进（与道语言官方示例一致，词法分析器禁止 Tab 与空格混用）。

## 安装

把本目录（`<项目根目录>/编辑器插件/neovim`）加入 Neovim 的 `runtimepath` 即可。

### 方式一：手工加入 runtimepath

在 `init.lua` 中：

```lua
vim.opt.runtimepath:append("<项目根目录>/编辑器插件/neovim")
filetype plugin indent on
syntax enable
```

### 方式二：使用 pack 目录

```bash
mkdir -p ~/.config/nvim/pack/dao/start
ln -s "<项目根目录>/编辑器插件/neovim" ~/.config/nvim/pack/dao/start/dao
```

`start` 目录下的插件会在启动时自动加入 `runtimepath`，无需额外配置。

### 方式三：lazy.nvim

```lua
{
  dir = "<项目根目录>/编辑器插件/neovim",
  ft = "dao",
}
```

### 方式四：packer.nvim

```lua
use({ "<项目根目录>/编辑器插件/neovim", ft = "dao" })
```

> 注意：请把 `<项目根目录>` 替换为实际路径。插件内部所有源码/解释器路径均相对插件目录动态推导，不含任何固定机器路径。

## LSP 接口说明

插件调用项目自带的 LSP 服务器（JSON-RPC over stdio）：

```
<项目根目录>/源码/.venv/bin/python -m dao.lsp
```

- 工作目录：优先使用文件所在的 git 仓库根目录，否则使用当前工作目录。
- 环境变量：自动把 `<项目根目录>/源码` 加入 `PYTHONPATH`，确保 `dao` 包可被导入；已有的 `PYTHONPATH` 会被保留。
- 服务器能力：全量文档同步、补全、悬停、跳转定义、文档符号，并在打开/修改文档时发布中文诊断。
- 重复启动保护：插件缓存客户端 id，同一会话不会重复拉起进程；打开新的 `.道` 文件会复用已有客户端。

## nvim-lspconfig 接入

`lsp/dao_ls.lua` 提供符合 nvim-lspconfig 约定的 server 配置（返回 `default_config` + `docs`），路径全部相对插件目录动态推导，可原样贡献到上游 `lua/lspconfig/server_configurations/dao_ls.lua`。它复用内置 ftplugin 的语义：同样的解释器、工作目录、`PYTHONPATH`、`root_dir`、`on_attach` 与 `capabilities`，并额外设置 `filetypes = { "dao" }` 与 `single_file_support = true`。

### 方式一：配置已进入 lspconfig（或已放到 server_configurations 目录）

```lua
require('lspconfig').dao_ls.setup({})
```

由于该文件不在仓库内、无法相对推导源码路径，请显式告知源码目录（或在 `setup` 中覆盖 `cmd` / `env`）：

```lua
vim.g.dao_ls_source_dir = '<项目根目录>/源码'
-- 可选：vim.g.dao_ls_python = '<解释器绝对路径>'
require('lspconfig').dao_ls.setup({})
```

### 方式二：直接用本仓库内的文件本地注册

```lua
local dao_dir = '<项目根目录>/编辑器插件/neovim'
package.path = dao_dir .. '/?.lua;' .. package.path

local configs = require('lspconfig.configs')
if not configs.dao_ls then
  configs.dao_ls = require('lsp.dao_ls')  -- 对应 lsp/dao_ls.lua
end
require('lspconfig').dao_ls.setup({})
```

### 与内置 `:DaoLspStart` 的关系

两种方式启动的是**同一个** `python -m dao.lsp` 服务器，但客户端不同（内置为 `dao`，lspconfig 为 `dao_ls`）。**任选其一即可，同时启用会拉起两个客户端并重复设置按键。** 默认是内置方式：只要把插件目录加入 `runtimepath`，`ftplugin/dao.lua` 就会在打开 `.道` / `.dao` 文件时自动启动。

若改用 lspconfig 独占，请不要把 `<项目根目录>/编辑器插件/neovim` 整体加入 `runtimepath`（否则 ftplugin 仍会自动启动），改为按需加载文件类型识别与语法高亮：

```lua
local dao_dir = '<项目根目录>/编辑器插件/neovim'

vim.api.nvim_create_autocmd({ 'BufRead', 'BufNewFile' }, {
  pattern = { '*.道', '*.dao' },
  callback = function()
    vim.bo.filetype = 'dao'
    vim.cmd('source ' .. dao_dir .. '/syntax/dao.vim')
  end,
})

package.path = dao_dir .. '/?.lua;' .. package.path
local configs = require('lspconfig.configs')
if not configs.dao_ls then
  configs.dao_ls = require('lsp.dao_ls')
end
require('lspconfig').dao_ls.setup({})
```

> 也可在保留内置方式的前提下仅试验 lspconfig：打开道语言文件后执行 `:DaoLspStop` 停止内置客户端，但下次打开文件仍会自动启动，因此不推荐长期并用。

## 命令与按键

### 用户命令

| 命令 | 说明 |
| --- | --- |
| `:DaoLspStart` | 启动（或复用）道语言 LSP 服务器 |
| `:DaoLspStop` | 停止道语言 LSP 服务器 |

打开 `.道` / `.dao` 文件时会自动调用启动逻辑，通常无需手动执行。

### LSP 快捷键（仅在道语言缓冲区生效）

| 按键 | 功能 |
| --- | --- |
| `K` | 悬停查看关键字 / 内置函数 / 标准库的中文说明 |
| `gd` | 跳转到定义 |
| `[d` / `]d` | 上一个 / 下一个诊断 |
| `<leader>d` | 显示当前行的诊断浮窗 |
| `<leader>ds` | 列出当前文档的符号（变量、函数、类等） |
| `<C-x><C-o>` | 插入模式下触发 LSP 补全（基于 `omnifunc`） |

诊断信息也会由 Neovim 内置机制显示在行号旁与位置列表中。

## 故障排查

**1. 没有语法高亮**

- 确认已开启 `syntax enable` 或 `syntax on`。
- 执行 `:set filetype?` 应为 `dao`；若为其他值，检查 `ftdetect` 目录是否在 `runtimepath` 中。
- 执行 `:echo b:current_syntax` 应为 `dao`。

**2. LSP 无法启动 / 提示找不到解释器**

- 确认存在 `<项目根目录>/源码/.venv/bin/python` 且可执行。
- 确认可执行文件 `python -m dao.lsp` 能正常启动（不会立即退出）。
- 执行 `:DaoLspStart` 手动重试；查看 `:messages` 中的中文错误提示。
- 若使用自定义 Python 环境，请确保 `dao` 包可被导入，必要时自行设置 `PYTHONPATH`。

**3. 补全不生效**

- LSP 补全通过 `omnifunc` 提供，需在插入模式按 `<C-x><C-o>` 触发。
- 若使用 nvim-cmp 等补全框架，请自行把 `vim.lsp.protocol.make_client_capabilities()` 替换为框架提供的 `capabilities`（本插件使用 Neovim 内置能力）。

**4. 悬停 / 跳转无反应**

- 确认 LSP 已启动：`:LspInfo`（若安装了 lsp-info 类插件）或查看 `:messages`。
- 服务器对未识别的词不返回悬停内容；请把光标移到关键字、内置函数名或标准库模块名上。

**5. 缩进不符合预期**

- 插件在缓冲区局部设置 `expandtab`、`tabstop=4`、`shiftwidth=4`、`softtabstop=4`。
- 若被其他插件覆盖，可在 `ftplugin/dao.lua` 中调整对应数值。

## 已知限制

- 道语言目前没有 tree-sitter grammar，因此使用传统 Vim 正则高亮；嵌套 `/* */` 注释由语法区域递归处理，但极复杂的嵌套场景可能高亮不完整。
- 词法分析器中 `//` 在表达式上下文可能表示整除（如 `7 // 2`），而正则高亮统一将其视为注释；这是传统高亮无法完全区分语义上下文的固有限制，不影响 LSP 诊断结果。
- LSP 跳转定义基于当前文档内的 AST 符号，暂不支持跨文件跳转。
- 服务器使用全量文档同步，超大文件的诊断刷新可能略有延迟。
