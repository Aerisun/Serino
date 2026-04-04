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

### 开发密钥文件（推荐）

如需本地密钥配置：

```bash
cp .env.development.local.example .env.development.local
```

`make dev` / `make dev-pseed` 会自动加载 `.env.development.local`。

如需提交前密钥检查：

```bash
make install-git-hooks
```

手动全仓检查：

```bash
make check-secrets
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

  启动完成后的默认可用地址（多工作树以当前工作树自动生成的 `.env.development.local` 为准）：
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

- 面向终端用户的 Linux 一键安装命令：

  ```bash
  curl -fsSL https://install.aerisun.com/install.sh | bash
  ```

- v1 安装器面向可联网的主流 `systemd` Linux，安装时会：
  - 自动安装 Docker / Compose（如果系统里还没有）
  - 通过交互式向导收集域名或公网 IP
  - 域名模式自动通过 Caddy 启动 HTTPS；如果 HTTPS 就绪失败，会直接输出 DNS、端口监听和 Caddy 日志相关原因
  - 优先从腾讯云 TCR 拉镜像，失败时自动回退 Docker Hub
  - 把服务安装到 `/opt/aerisun`
  - 把数据目录固定到 `/var/lib/aerisun`
  - 安装完成后提供 `aerisunctl status|logs|restart|upgrade`

- 全新生产部署成功后：
  - 后台管理员用户名和密码由安装向导现场设置
  - 安装器只会在首装时使用这组凭据初始化后台账号
  - 校验成功后，安装器会把一次性初始化密码从 `.env.production.local` 移除
  - 如果是手动执行 `docker compose`，也必须先在 `.env.production.local` 里填写 `AERISUN_BOOTSTRAP_ADMIN_USERNAME` 和 `AERISUN_BOOTSTRAP_ADMIN_PASSWORD`，首装完成并确认可登录后再删除

- 生产安装与升级默认遵循三段式数据流程：
  - 首装：`migration + bootstrap seed`
  - 升级：`migration + data backfill`
  - 开发：`dev seed`
  - 首装只初始化站点基础配置、页面文案、导航和生产安全默认值
  - 升级只执行已注册且未执行的 backfill，不会把 development 假数据灌进生产库
  - 如需关闭首装 scaffold，可把 `.env.production.local` 里的 `AERISUN_SEED_REFERENCE_DATA` 改成 `false`
  - 如需关闭升级回填，可把 `.env.production.local` 里的 `AERISUN_DATA_BACKFILL_ENABLED` 改成 `false`

- 正式镜像同时发布到 Docker Hub 和腾讯云 TCR 个人版：
  - Docker Hub
    - `docker.io/aerisun/serino-api`
    - `docker.io/aerisun/serino-web`
    - `docker.io/aerisun/serino-waline`
  - 腾讯云 TCR
    - `${TCR_REGISTRY}/${TCR_NAMESPACE}/serino-api`
    - `${TCR_REGISTRY}/${TCR_NAMESPACE}/serino-web`
    - `${TCR_REGISTRY}/${TCR_NAMESPACE}/serino-waline`

- GitHub Actions 行为：
  - `main` 和 Pull Request：只做镜像构建验证，不推送
  - `vX.Y.Z` tag：先跑 smoke，再向两个仓库同时发布 `1.2.3`、`1.2`、`1`、`latest`
  - `workflow_dispatch`：输入同一个 tag，可手动重发镜像
  - `vX.Y.Z` tag 同时产出 installer 资产：
    - `install.sh`
    - `aerisun-installer-bundle.tar.gz`
    - `aerisun-installer-manifest.env`
    - `docker-compose.release.yml`
    - `.env.production.local.example`

- 发布作业依赖以下 GitHub 配置：
  - `vars.DOCKERHUB_USERNAME`
  - `secrets.DOCKERHUB_TOKEN`
  - `vars.TCR_REGISTRY`
  - `vars.TCR_NAMESPACE`
  - `secrets.TCR_USERNAME`
  - `secrets.TCR_PASSWORD`

- 部署前先复制发布环境文件：

  ```bash
  cp .env.production.local.example .env.production.local
  ```

- 手动一键启动：

  ```bash
  docker compose --env-file .env.production.local -f docker-compose.release.yml up -d
  ```

- 手动部署时的镜像源契约：

  ```bash
  AERISUN_IMAGE_PRIMARY_REGISTRY=${TCR_REGISTRY}/${TCR_NAMESPACE}
  AERISUN_IMAGE_FALLBACK_REGISTRY=docker.io/aerisun
  AERISUN_IMAGE_REGISTRY=${TCR_REGISTRY}/${TCR_NAMESPACE}
  AERISUN_IMAGE_TAG=latest
  ```

- 安装器会自动维护 `AERISUN_IMAGE_PRIMARY_REGISTRY`、`AERISUN_IMAGE_FALLBACK_REGISTRY`、`AERISUN_IMAGE_REGISTRY` 和 `AERISUN_IMAGE_TAG`，通常不需要手动编辑。

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
