# Aerisun MCP Companion

这个 companion 是 Aerisun MCP 2026-07-28 的可选本地诊断工具。日常使用请直接从你的 Aerisun 域名安装共享插件；无需复制文件，也不依赖 companion 运行。

- 域名安装入口：`https://你的域名/mcp/install`
- Codex 安装脚本：`https://你的域名/mcp/install/codex.sh`
- Claude Code 安装脚本：`https://你的域名/mcp/install/claude.sh`
- 共用 Skills：`plugins/aerisun-mcp/skills/`

companion 只负责在仓库开发或排障时拉取 usage 文档、运行连接检查和生成不含密钥的快照。

## 目录

```text
companions/aerisun-mcp/
  .env
  .env.example
  .gitignore
  README.md
  scripts/
    init_env.sh
    prepare_ai_bundle.py

plugins/aerisun-mcp/
  .codex-plugin/plugin.json
  .claude-plugin/plugin.json
  skills/
    aerisun-mcp-bootstrap/
    aerisun-mcp-readonly/
    aerisun-mcp-guarded-write/
```

## 日常安装

Codex 用户只需两步：

1. 在 Serino 管理台复制并运行安装命令：

   ```bash
   curl -fsSL https://你的域名/mcp/install/codex.sh | sh
   ```

2. 在隐藏提示中输入 Serino MCP API Key。

安装器会完成 MCP 插件与 Skills 安装、MCP 配置、Key 安全保存、换 Key 工具安装和 Codex 自动重连。npm、pnpm、bun 与官网安装的 Codex CLI 都受支持，不需要额外激活。

Claude Code 用户运行：

```bash
curl -fsSL https://你的域名/mcp/install/claude.sh | sh
```

安装器会安装共享 Skills，把客户端连接到这个域名的 `/api/mcp/`，并将 Key 写入仅当前用户可读的客户端私有凭据，同时安装 `~/.local/bin/serino-mcp-key`。以后运行该本地命令即可离线更新 Key，无需再次请求站点安装脚本；Codex 会自动重连，Claude Code 用户需要重启客户端。

## 本地诊断

1. 初始化本地环境文件：

   ```bash
   bash companions/aerisun-mcp/scripts/init_env.sh
   ```

2. 打开 `companions/aerisun-mcp/.env`，填入：

   - `AERISUN_MCP_API_KEY`
   - 如有需要，再调整 `AERISUN_MCP_BASE_URL`

3. 生成给 AI 使用的运行时上下文：

   ```bash
   python3 companions/aerisun-mcp/scripts/prepare_ai_bundle.py
   ```

4. 可选：跑一次 MCP smoke test，确认 usage、meta、health、tools/resources 和只读示例调用都正常：

   ```bash
   set -a
   source companions/aerisun-mcp/.env
   set +a
   uv run --directory backend python ../scripts/mcp-smoke.py \
     --base-url "$AERISUN_MCP_BASE_URL" \
     --api-key "$AERISUN_MCP_API_KEY"
   ```

5. 排障时可以把下面这些不含密钥的内容交给 AI：

   - `plugins/aerisun-mcp/skills/`
   - `companions/aerisun-mcp/runtime/briefing.md`
   - `companions/aerisun-mcp/runtime/companion-manifest.json`
   - `companions/aerisun-mcp/runtime/usage.json`
   - `companions/aerisun-mcp/runtime/mcp-client.template.json`
   - `companions/aerisun-mcp/runtime/openai.responses-mcp-tools.template.json`

   在 MCP 客户端的安全环境变量或密钥设置中配置 API Key；不要把 `.env` 文件作为上下文交给 AI。

## 安全模型

- 日常客户端的真实 API Key 只放在权限为 `0600` 的用户私有凭据；companion 排障 Key 只放在本地 `.env`，两者都不会写进仓库跟踪文件。
- `prepare_ai_bundle.py` 默认不会把明文密钥写入任何生成文件。
- companion 默认开启 `AERISUN_MCP_REQUIRE_READONLY=true`。
- 即使关闭只读模式，写入工具也仍然需要 `AERISUN_MCP_ALLOWED_WRITE_TOOLS` 白名单。
- `aerisun-mcp-guarded-write` Skill 将用户明确提出的写入请求视为该项操作的授权，不再重复确认。
- 客户端必须先调用 `ClientSession.discover()`，再列出或调用能力。

## 运行时输出

脚本会生成：

- `runtime/usage.json`
- `runtime/mcp-meta.json`
- `runtime/mcp-client.template.json`
- `runtime/openai.responses-mcp-tools.template.json`
- `runtime/companion-manifest.json`
- `runtime/briefing.md`

这些文件都不包含明文 API Key，可以直接作为 AI 的上下文或配置模板。
