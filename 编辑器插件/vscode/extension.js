// 道语言 VS Code 扩展入口
// 负责以 stdio 方式启动仓库内置的道语言 LSP 服务器。

const vscode = require('vscode');
const path = require('path');
const fs = require('fs');
const { LanguageClient, TransportKind } = require('vscode-languageclient/node');

let client;

/**
 * 定位道语言源码目录（内含 dao/ 与 .venv/bin/python）。
 *
 * 两种运行形态：
 *  1. 开发模式（F5 从仓库加载插件）：源码在插件目录上两级的「源码」；
 *  2. 安装模式（.vsix 装到 ~/.vscode/extensions）：插件目录不再与仓库相邻，
 *     此时从当前工作区各根目录寻找「源码」子目录。
 *
 * 取第一个同时含 dao/lsp/__init__.py 的候选，确保 `-m dao.lsp` 可导入。
 */
function resolveSourceDir() {
  const candidates = [path.resolve(__dirname, '..', '..', '源码')];
  const folders = vscode.workspace.workspaceFolders || [];
  for (const folder of folders) {
    const root = folder.uri.fsPath;
    candidates.push(path.join(root, '源码'));
    candidates.push(root);
  }
  for (const dir of candidates) {
    if (fs.existsSync(path.join(dir, 'dao', 'lsp', '__init__.py'))) {
      return dir;
    }
  }
  // 均未命中时返回开发模式默认位置，让 LSP 启动报错可见、便于排查。
  return candidates[0];
}

/**
 * 解析 Python 解释器路径：
 *  - 绝对路径直接使用；
 *  - 相对路径基于插件目录解析（兼容既有配置语义）；
 *  - 留空则使用已定位源码目录下的 .venv 解释器。
 */
function resolvePythonPath(configured, sourceDir) {
  if (!configured || !String(configured).trim()) {
    return path.join(sourceDir, '.venv', 'bin', 'python');
  }
  if (path.isAbsolute(configured)) {
    return configured;
  }
  return path.resolve(__dirname, configured);
}

function workspaceRoot() {
  const folders = vscode.workspace.workspaceFolders || [];
  return folders.length ? folders[0].uri.fsPath : undefined;
}

/** 在集成终端运行道语言 CLI 子命令。 */
function runDaoCli(subcommand, args, sourceDir, pythonPath) {
  const cwd = workspaceRoot();
  if (!cwd) {
    vscode.window.showErrorMessage('请先打开一个道语言项目目录');
    return;
  }
  const mainPy = path.join(sourceDir, 'main.py');
  if (!fs.existsSync(mainPy)) {
    vscode.window.showErrorMessage(`找不到道语言入口：${mainPy}`);
    return;
  }
  const quote = (value) => `"${String(value).replace(/"/g, '\\"')}"`;
  const command = [pythonPath, mainPy, subcommand, ...args].map(quote).join(' ');
  const terminal = vscode.window.createTerminal({ name: `道语言 ${subcommand}`, cwd });
  terminal.show();
  terminal.sendText(command);
}

/** 选择 .道包 / .道应用 文件；从资源管理器调用时直接使用传入的 uri。 */
async function pickDaoFile(uri, extension, label) {
  if (uri && uri.fsPath) {
    return uri.fsPath;
  }
  const selected = await vscode.window.showOpenDialog({
    canSelectFiles: true,
    canSelectFolders: false,
    canSelectMany: false,
    filters: { [label]: [extension] },
  });
  return selected && selected.length ? selected[0].fsPath : undefined;
}

function activate(context) {
  const config = vscode.workspace.getConfiguration('dao');
  const sourceDir = resolveSourceDir();
  const pythonPath = resolvePythonPath(config.get('pythonPath', ''), sourceDir);
  const traceServer = config.get('trace.server', 'off');

  const serverOptions = {
    command: pythonPath,
    args: ['-m', 'dao.lsp'],
    options: { cwd: sourceDir },
    transport: TransportKind.stdio,
  };

  const clientOptions = {
    documentSelector: [{ scheme: 'file', language: 'dao' }],
    synchronize: {
      configurationSection: 'dao',
      fileEvents: vscode.workspace.createFileSystemWatcher('**/*.道'),
    },
    trace: { server: traceServer },
  };

  client = new LanguageClient('dao', '道语言服务', serverOptions, clientOptions);
  context.subscriptions.push(client.start());

  // 道.配置 的字段补全：本地提供，不依赖 LSP 是否支持该语言。
  context.subscriptions.push(
    vscode.languages.registerCompletionItemProvider(
      { language: 'dao-config' },
      {
        provideCompletionItems() {
          const fields = [
            ['名称', '包名'],
            ['版本', '包版本（语义化版本）'],
            ['道版本', '所需道语言版本约束，如 >=1.3.0'],
            ['作者', '作者'],
            ['描述', '包描述'],
            ['入口', '入口文件'],
            ['依赖', '依赖分节'],
            ['开发依赖', '开发依赖分节'],
          ];
          return fields.map(([label, detail]) => {
            const item = new vscode.CompletionItem(label, vscode.CompletionItemKind.Property);
            item.detail = detail;
            return item;
          });
        },
      }
    )
  );

  // 打包 / 运行命令：复用已有的源码目录与 Python 路径解析。
  context.subscriptions.push(
    vscode.commands.registerCommand('dao.pack', () => {
      runDaoCli('pack', [workspaceRoot()], sourceDir, pythonPath);
    }),
    vscode.commands.registerCommand('dao.build', () => {
      runDaoCli('build', [workspaceRoot()], sourceDir, pythonPath);
    }),
    vscode.commands.registerCommand('dao.install', async (uri) => {
      const file = await pickDaoFile(uri, '道包', '道语言依赖包');
      if (file) {
        runDaoCli('install', [file, '-p', workspaceRoot()], sourceDir, pythonPath);
      }
    }),
    vscode.commands.registerCommand('dao.runApp', async (uri) => {
      const file = await pickDaoFile(uri, '道应用', '道语言应用包');
      if (file) {
        runDaoCli('run', [file], sourceDir, pythonPath);
      }
    })
  );
}

function deactivate() {
  if (!client) {
    return undefined;
  }
  return client.stop();
}

module.exports = { activate, deactivate };
