-- 道语言 LSP 的 nvim-lspconfig server 配置
-- ====================================================================
-- 用途：本文件提供符合 nvim-lspconfig 约定的 server 配置模块，可直接
--       贡献到上游 nvim-lspconfig 的
--       lua/lspconfig/server_configurations/dao_ls.lua。配置语义与仓库内
--       编辑器插件/neovim/ftplugin/dao.lua 的 client_config() 保持一致
--       （解释器、工作目录、PYTHONPATH、root_dir、on_attach、capabilities）。
--       所有路径均相对本文件所在插件目录动态推导，不含任何机器绝对路径。
--
-- 注册方法一（已贡献/已放入 lspconfig 的 server_configurations 目录）：
--   require('lspconfig').dao_ls.setup({})
--
-- 注册方法二（尚未进入上游，使用本仓库内的文件本地注册）：
--   local plugin_dir = '<项目根目录>/编辑器插件/neovim'
--   package.path = plugin_dir .. '/?.lua;' .. package.path
--   local configs = require('lspconfig.configs')
--   if not configs.dao_ls then
--     configs.dao_ls = require('lsp.dao_ls')  -- 对应 lsp/dao_ls.lua
--   end
--   require('lspconfig').dao_ls.setup({})
--
-- 与内置 :DaoLspStart 的关系：二者都会启动同一个 `python -m dao.lsp`
--   服务器，任选其一即可；同时启用会拉起两个客户端。本插件的 ftplugin
--   默认自动调用 :DaoLspStart，若改用 lspconfig，请见 neovim/README.md
--   的「nvim-lspconfig 接入」小节关闭自动启动。
-- ====================================================================

-- 本文件位于 编辑器插件/neovim/lsp/dao_ls.lua，
-- 插件根目录为其上两级（编辑器插件/neovim/）。
local function plugin_root()
  local source = debug.getinfo(1, "S").source
  local path = source:sub(1, 1) == "@" and source:sub(2) or vim.fn.expand("<sfile>:p")
  return vim.fn.fnamemodify(path, ":h:h")
end

local plugin_dir = plugin_root()

-- 源码目录与解释器：优先使用用户显式覆盖，否则按插件目录相对推导。
-- 贡献到上游后，本文件不在仓库内，使用者应设置 vim.g.dao_ls_source_dir
-- 或在 setup({ cmd = ... }) 中覆盖。
local source_dir = vim.g.dao_ls_source_dir
  and vim.fn.fnamemodify(vim.g.dao_ls_source_dir, ":p")
  or vim.fn.fnamemodify(plugin_dir .. "/../../源码", ":p")

local function default_python(base)
  if vim.fn.has("win32") == 1 then
    return base .. "/.venv/Scripts/python.exe"
  end
  return base .. "/.venv/bin/python"
end

local python_bin = vim.g.dao_ls_python
  and vim.fn.fnamemodify(vim.g.dao_ls_python, ":p")
  or default_python(source_dir)

-- 构造 PYTHONPATH：把 源码/ 放在前面，并保留用户已有的配置。
local function build_pythonpath()
  local existing = vim.env.PYTHONPATH
  local sep = vim.fn.has("win32") == 1 and ";" or ":"
  if existing and existing ~= "" then
    return source_dir .. sep .. existing
  end
  return source_dir
end

-- root_dir：优先 git 仓库根目录，失败时回退到当前工作目录。
local function find_root_dir(fname)
  local dir = vim.fn.fnamemodify(fname, ":p:h")
  local lines = vim.fn.systemlist({ "git", "-C", dir, "rev-parse", "--show-toplevel" })
  if vim.v.shell_error == 0 and lines[1] and lines[1] ~= "" then
    return vim.fn.fnamemodify(lines[1], ":p")
  end
  return vim.fn.getcwd()
end

-- on_attach：与 ftplugin/dao.lua 的按键语义一致，另加缓冲区级防重复映射。
local function on_attach(_, bufnr)
  if vim.b[bufnr].dao_ls_keymaps then
    return
  end
  vim.b[bufnr].dao_ls_keymaps = true
  vim.bo[bufnr].omnifunc = "v:lua.vim.lsp.omnifunc"

  local map = function(mode, keys, func, desc)
    vim.keymap.set(mode, keys, func, {
      buffer = bufnr,
      silent = true,
      desc = "道语言 LSP：" .. desc,
    })
  end

  map("n", "K", vim.lsp.buf.hover, "悬停查看文档")
  map("n", "gd", vim.lsp.buf.definition, "跳转到定义")
  map("n", "[d", vim.diagnostic.goto_prev, "上一个诊断")
  map("n", "]d", vim.diagnostic.goto_next, "下一个诊断")
  map("n", "<leader>d", vim.diagnostic.open_float, "显示当前行诊断")
  map("n", "<leader>ds", vim.lsp.buf.document_symbol, "列出文档符号")
end

-- nvim-lspconfig server 配置：顶层返回 default_config + docs。
return {
  default_config = {
    cmd = { python_bin, "-m", "dao.lsp" },
    cmd_cwd = source_dir,
    filetypes = { "dao" },
    root_dir = find_root_dir,
    single_file_support = true,
    env = { PYTHONPATH = build_pythonpath() },
    on_attach = on_attach,
    capabilities = vim.lsp.protocol.make_client_capabilities(),
  },
  docs = {
    description = [[
道语言（中文多范式编程语言）的内置 LSP 服务器。

服务器随道语言仓库提供，无第三方依赖，通过 stdio 通信：
  <源码目录>/.venv/bin/python -m dao.lsp

默认假设本配置文件位于道语言仓库的 编辑器插件/neovim/lsp/ 下；
若贡献到 nvim-lspconfig 上游，使用者应设置 vim.g.dao_ls_source_dir
指向仓库的 源码/ 目录，或在 setup 中覆盖 cmd / env。

提供诊断、补全、悬停、跳转定义与文档符号能力。
]],
    default_config = {
      root_dir = [[root_dir: git 仓库根目录，找不到时回退当前工作目录]],
    },
  },
}
