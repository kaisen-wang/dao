// 道语言 VS Code 扩展入口
// 负责以 stdio 方式启动仓库内置的道语言 LSP 服务器。

const vscode = require('vscode');
const path = require('path');
const { LanguageClient, TransportKind } = require('vscode-languageclient/node');

let client;

function activate(context) {
  const config = vscode.workspace.getConfiguration('dao');

  // 源码目录位于插件目录的上两级：编辑器插件/vscode -> 项目根 -> 源码
  const sourceDir = path.resolve(__dirname, '..', '..', '源码');

  // 解析 Python 解释器路径：
  //  - 绝对路径直接使用；
  //  - 相对路径基于插件目录解析（默认值为 ../../源码/.venv/bin/python）；
  //  - 留空则回退到仓库内置的 .venv 解释器。
  const configured = config.get('pythonPath', '');
  let pythonPath;
  if (!configured || !String(configured).trim()) {
    pythonPath = path.join(sourceDir, '.venv', 'bin', 'python');
  } else if (path.isAbsolute(configured)) {
    pythonPath = configured;
  } else {
    pythonPath = path.resolve(__dirname, configured);
  }

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
