# Aerisun MCP Plugin

这是 Codex 与 Claude Code 共用的 Aerisun MCP + Skills 插件。它不内置站点地址或密钥；请始终从你的 Aerisun 域名安装，让安装器绑定当前站点的 `/api/mcp/`。

## 安装

Codex：

```sh
curl -fsSL https://你的域名/mcp/install/codex.sh | sh
```

Claude Code：

```sh
curl -fsSL https://你的域名/mcp/install/claude.sh | sh
```

安装器会从终端隐藏读取一次 API Key，并持久写入权限为 `0600` 的用户私有凭据。Codex 使用 `~/.codex/.env`；Claude Code 通过不含密钥的 `headersHelper` 读取 `~/.config/aerisun/mcp-api-key`。密钥不会进入插件、URL 或客户端命令参数。之后运行本地的 `~/.local/bin/serino-mcp-key` 即可离线轮换密钥；安装或换 Key 后启动新的 Codex 任务或重启 Claude Code。

## 包含的 Skills

- `aerisun-mcp-bootstrap`：确认连接并读取当前 Key 可见的能力目录。
- `aerisun-mcp-readonly`：执行读取、搜索、检查和总结。
- `aerisun-mcp-guarded-write`：只在用户明确要求变更时执行当前 Key 已授权的写操作，不重复确认。

仓库中的 `companions/aerisun-mcp/` 仅用于本地诊断和生成运行时快照，不是日常安装的必要条件。
