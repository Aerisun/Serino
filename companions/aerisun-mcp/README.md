# Aerisun MCP Companion

这个 companion 用来把 Aerisun 的 MCP 接入能力安全地交给 AI 使用。

它包含三类东西：

- `skills/`：给 AI 的 skill 集合，按“连接准备 / 只读使用 / 受控写入”拆分
- `.env` / `.env.example`：本地保存 MCP API Key 和安全策略
- `scripts/`：验证连接、拉取 usage 文档、生成 AI 可直接消费的运行时文件

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
  skills/
    aerisun-mcp-bootstrap/
    aerisun-mcp-readonly/
    aerisun-mcp-guarded-write/
```

## 快速开始

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

4. 把下面这些东西交给 AI：

   - `companions/aerisun-mcp/skills/`
   - `companions/aerisun-mcp/runtime/briefing.md`
   - `companions/aerisun-mcp/runtime/companion-manifest.json`
   - `companions/aerisun-mcp/runtime/usage.json`
   - `companions/aerisun-mcp/runtime/mcp-client.template.json`
   - `companions/aerisun-mcp/runtime/openai.responses-mcp-tools.template.json`
   - 本地 `.env` 文件

## 安全模型

- 真实 API Key 只放在本地 `.env`，不会写进仓库跟踪文件。
- `prepare_ai_bundle.py` 默认不会把明文密钥写入任何生成文件。
- companion 默认开启 `AERISUN_MCP_REQUIRE_READONLY=true`。
- 即使关闭只读模式，写入能力也仍然需要 `AERISUN_MCP_ALLOWED_WRITE_TOOLS` 或 `AERISUN_MCP_ALLOWED_WRITE_RESOURCES` 白名单。
- `aerisun-mcp-guarded-write` skill 默认要求先读取当前状态，再执行写入，并优先遵守显式确认。

## 运行时输出

脚本会生成：

- `runtime/usage.json`
- `runtime/mcp-meta.json`
- `runtime/mcp-client.template.json`
- `runtime/openai.responses-mcp-tools.template.json`
- `runtime/companion-manifest.json`
- `runtime/briefing.md`

这些文件都不包含明文 API Key，可以直接作为 AI 的上下文或配置模板。
