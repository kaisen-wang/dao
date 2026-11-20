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
}

function deactivate() {
  if (!client) {
    return undefined;
  }
  return client.stop();
}

module.exports = { activate, deactivate };
