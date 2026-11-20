-- 道语言 Neovim 文件类型插件
-- 负责：启动 LSP、设置缓冲区局部选项、提供用户命令。
-- 所有路径均相对本插件目录动态推导，不依赖任何本机绝对路径。

local M = {}

-- 记录本插件启动的 LSP 客户端 id，避免重复启动
local client_id = nil

-- ------------------------------------------------------------------
-- 路径计算
-- 本文件位于 编辑器插件/neovim/ftplugin/dao.lua，
-- 源码位于 编辑器插件/neovim/../../源码，
-- 解释器位于 源码/.venv/bin/python。
-- ------------------------------------------------------------------
local function plugin_root()
  local source = debug.getinfo(1, "S").source
  if source:sub(1, 1) == "@" then
    return vim.fn.fnamemodify(source:sub(2), ":h:h") -- 回退到 编辑器插件/neovim/
  end
  return vim.fn.fnamemodify(vim.fn.expand("<sfile>:p"), ":h:h")
end

local plugin_dir = plugin_root()
local source_dir = vim.fn.fnamemodify(plugin_dir .. "/../../源码", ":p")
local python_bin = vim.fn.fnamemodify(source_dir .. "/.venv/bin/python", ":p")

-- 构造 PYTHONPATH：把 源码/ 放在前面，并保留用户已有的配置
local function build_pythonpath()
  local existing = vim.env.PYTHONPATH
  if existing and existing ~= "" then
    local sep = vim.fn.has("win32") == 1 and ";" or ":"
    return source_dir .. sep .. existing
  end
  return source_dir
end

-- root_dir：优先 git 仓库根目录，失败时回退到当前工作目录
local function find_root_dir(fname)
  local dir = vim.fn.fnamemodify(fname, ":p:h")
  local lines = vim.fn.systemlist({ "git", "-C", dir, "rev-parse", "--show-toplevel" })
  if vim.v.shell_error == 0 and lines[1] and lines[1] ~= "" then
    return vim.fn.fnamemodify(lines[1], ":p")
  end
  return vim.fn.getcwd()
end

-- ------------------------------------------------------------------
-- 缓冲区局部选项
-- 道语言官方示例统一使用 4 空格缩进（词法分析器禁止 Tab 与空格混用）
-- ------------------------------------------------------------------
vim.bo.expandtab = true
vim.bo.tabstop = 4
vim.bo.shiftwidth = 4
vim.bo.softtabstop = 4
vim.bo.autoindent = true
vim.bo.commentstring = "// %s"

-- ------------------------------------------------------------------
-- LSP
-- ------------------------------------------------------------------
local function on_attach(_, bufnr)
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

local function client_config()
  return {
    name = "dao",
    cmd = { python_bin, "-m", "dao.lsp" },
    -- 较新版本 Neovim 支持 cmd_cwd；旧版忽略该字段，
    -- 但 PYTHONPATH 已足以让 python 找到 dao 包。
    cmd_cwd = source_dir,
    env = { PYTHONPATH = build_pythonpath() },
    root_dir = find_root_dir,
    on_attach = on_attach,
    capabilities = vim.lsp.protocol.make_client_capabilities(),
  }
end

function M.start()
  local bufnr = vim.api.nvim_get_current_buf()

  -- 已启动过则复用 / 重新附着，避免重复拉起进程
  if client_id then
    local existing = vim.lsp.get_client_by_id(client_id)
    if existing then
      if vim.lsp.buf_is_attached and not vim.lsp.buf_is_attached(bufnr, client_id) then
        vim.lsp.buf_attach_client(bufnr, client_id)
      end
      return client_id
    end
    client_id = nil
  end

  if vim.fn.executable(python_bin) ~= 1 then
    vim.notify("道语言 LSP 启动失败：找不到解释器 " .. python_bin, vim.log.levels.WARN)
    return nil
  end

  local ok, result = pcall(vim.lsp.start, client_config(), { bufnr = bufnr })
  if not ok then
    vim.notify("道语言 LSP 启动失败：" .. tostring(result), vim.log.levels.ERROR)
    return nil
  end
  if result then
    client_id = result
  end
  return result
end

function M.stop()
  if not client_id then
    vim.notify("道语言 LSP 未在运行", vim.log.levels.INFO)
    return
  end
  vim.lsp.stop_client(client_id)
  client_id = nil
  vim.notify("道语言 LSP 已停止", vim.log.levels.INFO)
end

-- 用户命令只定义一次
if not vim.g.dao_lsp_commands_loaded then
  vim.api.nvim_create_user_command("DaoLspStart", function()
    M.start()
  end, { desc = "启动道语言 LSP 服务器" })

  vim.api.nvim_create_user_command("DaoLspStop", function()
    M.stop()
  end, { desc = "停止道语言 LSP 服务器" })

  vim.g.dao_lsp_commands_loaded = true
end

-- 打开 .道 / .dao 文件时自动启动
M.start()

return M
