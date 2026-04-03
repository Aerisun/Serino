# Serino

## Quick Start

### 环境准备

- **Node.js (22.x +)**
- **uv**
- **pnpm**

环境准备完成后，进入项目根目录执行：

```bash
# 安装前端所有依赖
pnpm install --frozen-lockfile
# 安装后端依赖
cd backend && uv sync --dev
```

### 启动服务

- 进入项目根目录一键启动开发：

  ```bash
  make dev
  ```

  `make dev` 会使用 `backend/src/aerisun/core/dev_seed.py` 灌入测试/假数据。

  如果要专门调试生产初始化种子，可以使用：

  ```bash
  make dev-pseed
  ```

  `make dev-pseed` 会使用 `backend/src/aerisun/core/seed.py`，并在开发环境下随文件修改触发重新灌入，方便单独调试生产初始化逻辑。

  启动完成后的默认可用地址（多工作树以当前工作树自动生成的 `.env.local` 为准）：
  - 前台：`http://127.0.0.1:8080/`
  - 后台：`http://127.0.0.1:3001/admin/`
  - 默认管理账号密码（针对空数据库创建）：`admin` / `admin123`

- 停止环境：

  ```bash
  make dev-stop
  ```

### 测试

- 最基本的核心路由连通性测试：

  ```bash
  make dev-smoke
  ```

- 执行完整的后端测试和 API Client 契约测试：

  ```bash
  pnpm run test
  ```

## Docker 发布与部署

- 正式镜像固定发布到 Docker Hub：
  - `docker.io/aerisun/serino-api`
  - `docker.io/aerisun/serino-web`
  - `docker.io/aerisun/serino-waline`

- GitHub Actions 行为：
  - `main` 和 Pull Request：只做镜像构建验证，不推送
  - `vX.Y.Z` tag：先跑 smoke，再发布 `1.2.3`、`1.2`、`1`、`latest`
  - `workflow_dispatch`：输入同一个 tag，可手动重发镜像

- 部署前先复制发布环境文件：

  ```bash
  cp .env.release.example .env.release
  ```

- 用户一键启动：

  ```bash
  docker compose --env-file .env.release -f docker-compose.release.yml up -d
  ```

- 默认数据会落到当前目录下的 `./.aerisun-store/`，容器内仍然使用 `/srv/aerisun/store`

- 发布前本地 smoke：

  ```bash
  make docker-smoke
  ```

当前发版与升级以仓库内现有 `Dockerfile*`、`docker-compose*`、`.github/workflows/` 和根脚本为准。

## 仓库结构速览

- `admin/`：管理后台
- `backend/`：后端 API、migration、seed、CLI、测试
- `frontend/`：前台站点
- `packages/api-client/`：OpenAPI 生成客户端与契约测试
- `packages/theme/`：共享主题组件
- `packages/types/`：共享类型
- `packages/utils/`：共享工具函数
- `scripts/`：根级开发脚本，包括端口分配、dev 启停、smoke、OpenAPI 同步
- `docker-compose.release.yml`：面向用户的一键部署清单
- `.store/`：本地运行数据目录，默认包含 SQLite、媒体、密钥、LangGraph 状态
- `.dev/`：本地开发进程 pid、smoke 日志、orval 状态缓存
