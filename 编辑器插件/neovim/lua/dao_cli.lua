-- 道语言打包 / 运行命令（VS Code 与 Neovim 能力对齐）。
-- 由 ftplugin/dao.lua 与 ftplugin/daoconfig.lua 共同调用，只注册一次。

local M = {}

function M.setup(python_bin, source_dir, find_root_dir)
  if vim.g.dao_cli_commands_loaded then
    return
  end

  local function project_root()
    return find_root_dir(vim.fn.expand("%"))
  end

  local function run_dao(subcommand, args)
    if vim.fn.executable(python_bin) ~= 1 then
      vim.notify("道语言命令执行失败：找不到解释器 " .. python_bin, vim.log.levels.WARN)
      return
    end
    local main_py = source_dir .. "/main.py"
    if vim.fn.filereadable(main_py) ~= 1 then
      vim.notify("道语言命令执行失败：找不到入口 " .. main_py, vim.log.levels.WARN)
      return
    end
    local cmd = { python_bin, main_py, subcommand }
    vim.list_extend(cmd, args or {})
    vim.fn.jobstart(cmd, {
      cwd = project_root(),
      term = true,
      on_exit = function(_, code)
        if code ~= 0 then
          vim.notify("道语言命令退出码：" .. code, vim.log.levels.WARN)
        end
      end,
    })
  end

  vim.api.nvim_create_user_command("DaoPack", function()
    run_dao("pack", { project_root() })
  end, { desc = "道语言：把当前项目打包为依赖包" })

  vim.api.nvim_create_user_command("DaoBuild", function()
    run_dao("build", { project_root() })
  end, { desc = "道语言：把当前项目打包为可运行应用" })

  vim.api.nvim_create_user_command("DaoInstall", function(opts)
    local file = opts.args ~= "" and opts.args or vim.fn.input("依赖包文件（.道包）: ")
    if file == "" then
      return
    end
    run_dao("install", { file, "-p", project_root() })
  end, { nargs = "?", desc = "道语言：安装依赖包到当前项目" })

  vim.api.nvim_create_user_command("DaoRunApp", function(opts)
    local file = opts.args ~= "" and opts.args or vim.fn.input("应用包文件（.道应用）: ")
    if file == "" then
      return
    end
    run_dao("run", { file })
  end, { nargs = "?", desc = "道语言：运行 .道应用 包" })

  vim.g.dao_cli_commands_loaded = true
end

return M
