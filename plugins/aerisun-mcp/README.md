# Aerisun MCP Plugin

这是 Codex 与 Claude Code 共用的 Aerisun MCP + Skills 插件。它不内置站点地址或密钥；请始终从你的 Aerisun 域名安装，让安装器绑定当前站点的 `/api/mcp/`。

## 安装

Codex：

1. 在 Serino 管理台复制并运行 Codex 安装命令：

   ```sh
   curl -fsSL https://你的域名/mcp/install/codex.sh | sh
   ```

2. 按终端提示输入 Serino MCP API Key。

安装器会自动安装 MCP 插件和 Skills、写入 MCP 配置、安全保存 Key、安装换 Key 工具，并让 Codex 自动重连。通过 npm、pnpm、bun 或官网安装的 Codex CLI 都不需要额外的激活命令。

Claude Code：

```sh
curl -fsSL https://你的域名/mcp/install/claude.sh | sh
```

安装器会从终端隐藏读取一次 API Key，并持久写入权限为 `0600` 的 `~/.config/aerisun/mcp-api-key`。Codex 只在自动启动或重启 app-server daemon 时把密钥注入该进程；`~/.codex/.env` 是兼容副本。Claude Code 通过不含密钥的 `headersHelper` 读取私有凭据。密钥不会进入插件、URL 或客户端命令参数。

之后运行 `~/.local/bin/serino-mcp-key` 即可离线轮换密钥；Codex 会自动重连，Claude Code 用户需要重启客户端。

## 包含的 Skills

- `aerisun-mcp-bootstrap`：确认连接并读取当前 Key 可见的能力目录。
- `aerisun-mcp-readonly`：执行读取、搜索、检查和总结。
- `aerisun-mcp-guarded-write`：只在用户明确要求变更时执行当前 Key 已授权的写操作，不重复确认。

仓库中的 `companions/aerisun-mcp/` 仅用于本地诊断和生成运行时快照，不是日常安装的必要条件。
