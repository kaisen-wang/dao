-- 道.配置 文件类型插件：字段补全与注释设置。
-- 字段列表与 源码/dao/package/config.py 的 PackageConfig 保持一致。

-- 与 ftplugin/dao.lua 相同的路径推导，用于注册打包 / 运行命令。
local function plugin_root()
  local source = debug.getinfo(1, "S").source
  if source:sub(1, 1) == "@" then
    return vim.fn.fnamemodify(source:sub(2), ":h:h")
  end
  return vim.fn.fnamemodify(vim.fn.expand("<sfile>:p"), ":h:h")
end

local source_dir = vim.fn.fnamemodify(plugin_root() .. "/../../源码", ":p")
local python_bin = vim.fn.fnamemodify(source_dir .. "/.venv/bin/python", ":p")

local function find_root_dir(fname)
  local dir = vim.fn.fnamemodify(fname, ":p:h")
  local lines = vim.fn.systemlist({ "git", "-C", dir, "rev-parse", "--show-toplevel" })
  if vim.v.shell_error == 0 and lines[1] and lines[1] ~= "" then
    return vim.fn.fnamemodify(lines[1], ":p")
  end
  return vim.fn.getcwd()
end

require("dao_cli").setup(python_bin, source_dir, find_root_dir)

local fields = {
  { word = "名称", menu = "包名" },
  { word = "版本", menu = "包版本" },
  { word = "道版本", menu = "所需道语言版本约束" },
  { word = "作者", menu = "作者" },
  { word = "描述", menu = "描述" },
  { word = "入口", menu = "入口文件" },
  { word = "依赖", menu = "依赖分节" },
  { word = "开发依赖", menu = "开发依赖分节" },
}

function _G.DaoConfigComplete(findstart, base)
  if findstart == 1 then
    local line = vim.api.nvim_get_current_line()
    local col = vim.fn.col(".") - 1
    local start = col
    while start > 0 and line:sub(start, start) ~= " " and line:sub(start, start) ~= "\t" do
      start = start - 1
    end
    if line:sub(start + 1, start + 1) == " " then
      start = start + 1
    end
    return start
  end

  local items = {}
  for _, field in ipairs(fields) do
    if base == "" or field.word:find(base, 1, true) then
      table.insert(items, field)
    end
  end
  return items
end

vim.bo.omnifunc = "v:lua.DaoConfigComplete"
vim.bo.commentstring = "// %s"
