# Aerisun

Aerisun 是一个个人发布系统，包含 FastAPI 后端、前台站点、管理后台，
并支持使用 Docker 进行 SQLite、Litestream 以及备份/恢复相关流程。

## 工具链基线

- Node.js：推荐 `24.x`（当前 CI 也使用 Node 24）
- pnpm：由根 `package.json` 固定为 `pnpm@10.31.0`
- Python：`3.13`

安装依赖时，前端工作区走根目录 `pnpm install`，后端走 `cd backend && uv sync --dev`。

## 根级质量脚本

日常代码质量检查统一从仓库根目录执行：

```bash
pnpm run generate:api
pnpm run lint
pnpm run test
pnpm run check
```

这些命令分别负责：

- `generate:api`：只在 `packages/api-client` 中执行 Orval 代码生成
- `lint`：串行执行前端/后台 lint，以及 backend 的 Ruff format check
- `test`：执行 backend `pytest` 和 `@serino/api-client` 契约/schema 测试
- `check`：串行跑完生成、lint、test 和两个前端应用的生产构建

`Makefile` 仍然保留给 Linux/macOS 本地进程编排；代码质量和构建入口以根 `package.json` 为准。

## 本地开发

日常开发和多工作树并行开发都建议走这条路径。

### 推荐启动方式

1. 进入你要使用的工作树。
2. 执行：

```bash
make dev
```

`make dev` 会按顺序做三件事：

- 运行 `scripts/setup-ports.sh`
- 启动带 `--reload` 的后端 bootstrap 脚本
- 启动前台和管理端的 Vite 开发服务器

如果你需要停掉当前工作树里的开发进程，可以运行：

```bash
make dev-stop
```

它只会停止当前工作树自己启动的后端、前台和管理端，不会影响其他工作树。

开发运行时的 pid 文件会放在项目根目录的 `.dev/` 下，`.store/` 只保留数据和配置。

如果你想做一次自动化冒烟检查，可以运行：

```bash
make dev-smoke
```

它会启动本地开发栈，并等待后端健康检查、前台首页和管理后台都可访问后再退出。

### 端口脚本做什么

`scripts/setup-ports.sh` 会在当前工作树里生成 `.env.local`，并为以下服务分配可用端口：

- 后端
- 前台站点
- 管理后台

同时它还会写入前台和管理后台需要的预览地址与上游地址，用来正确打开站点预览链接。

### 如果你手动启动

如果你不使用 `make dev`，请先执行端口分配脚本：

```bash
./scripts/setup-ports.sh
```

然后在同一个工作树里启动后端、前台和管理端，让它们读取同一份 `.env.local`。

### 为什么多工作树时要这样做

每个工作树都应该有自己独立的 `.env.local`。

如果两个工作树共用同一组固定端口，可能出现这些问题：

- 后端重复绑定同一个端口
- 前台重复绑定同一个端口
- 管理后台重复绑定同一个端口
- 管理后台的预览按钮打开了别的工作树对应的前台站点

生成出来的 `.env.local` 可以让每个工作树都使用自己的端口集合。

### 开发启动链路

后端 bootstrap 脚本在本地开发时会做这些事：

1. 确保数据、媒体和密钥目录存在。
2. 检查当前分支的数据库兼容性。
3. 执行 Alembic migrations。
4. 在需要时执行种子数据初始化或重灌。
5. 启动 FastAPI。

启动时还会记录种子数据指纹，方便下次启动时判断种子定义是否发生变化。

### 本地开发常用地址

实际端口会写入 `.env.local`，常见默认值如下：

- 前台站点：`http://localhost:8080`
- 管理后台：`http://localhost:3001/admin/`
- 后端：`http://localhost:8000`
- Waline：`http://localhost:8360`

## 常见问题

### 1. `make fire` 不存在

请使用 `make dev`。

### 2. 端口已经被占用

一般说明另一个工作树或者本地进程已经占用了该端口。

处理方法：

```bash
./scripts/setup-ports.sh
```

然后在同一个工作树里重新启动应用。

### 2.1. 需要强制停止当前工作树的开发进程

如果 `Ctrl+C` 没有生效，或者终端已经丢了，就运行：

```bash
make dev-stop
```

它会根据当前工作树的 pid 文件停止这一套开发进程。

### 3. 预览按钮打开了错误的站点

通常是管理后台没有读取当前工作树的 `.env.local`。

处理方法：

- 重新执行 `./scripts/setup-ports.sh`
- 在该工作树里重启管理后台

### 4. 切换分支后数据库看起来还是旧的

后端有开发预检逻辑，会比较 Alembic revisions 和种子指纹。

如果分支差异较大，它会自动重建 SQLite 数据库并重新灌入参考数据。

### 5. 不要在多个工作树之间共用 `.env.local`

每个工作树都应该生成自己的 `.env.local`。

如果把一个工作树的 `.env.local` 复制到另一个工作树，两个工作树可能会指向同一组端口和同一组预览地址。

## Docker 部署

如果你要走部署流程，先把 `.env.example` 复制为 `.env`，然后填好备份主机相关配置。

接着启动整套服务：

```bash
docker compose up --build -d
```

API 容器会运行 `backend/scripts/bootstrap.sh`，负责确保目录存在、执行迁移并启动 FastAPI。

在应用启动时，FastAPI 的生命周期钩子会执行参考数据初始化，因此默认站点配置、页面和简历数据会通过运行时链路补齐。

这套部署里，两个前端应用仍然是宿主机上的 Vite 开发/运行进程：

- 前台站点：`frontend`，地址 `http://localhost:8080`
- 管理后台：`admin`，地址 `http://localhost:3001/admin/`

`Caddy` 会反向代理：

- `/` 到 `${AERISUN_FRONTEND_UPSTREAM}`
- `/admin/*` 到 `${AERISUN_ADMIN_UPSTREAM}`
- `/api/*` 到 FastAPI 后端

## 备份

运行宿主机侧脚本：

```bash
./backend/scripts/backup.sh
```

它会先对本地 SQLite 数据库做 checkpoint，然后让 Litestream 继续同步副本，最后通过 `rsync` 把媒体文件、密钥和备份清单同步到备份主机。

## 恢复

运行宿主机侧脚本：

```bash
./backend/scripts/restore.sh
```

它会停止整套服务，从 Litestream 副本恢复 SQLite 数据库，同步回媒体和密钥，然后重新启动服务。

## 路径

- 数据库：`${AERISUN_DB_PATH}`
- 媒体文件：`${AERISUN_MEDIA_DIR}`
- 密钥文件：`${AERISUN_SECRETS_DIR}`
