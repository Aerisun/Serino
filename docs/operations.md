# 生产运维方案

本文描述当前 Serino 的生产运维模型。目标不是列出所有脚本，而是把生产环境里真正应该依赖的路径、顺序和边界讲清楚。

## 总体原则

- 生产环境只有一条正式变更路径：`installer` / `sercli`
- 数据演进分三层：`schema migration` -> `production baseline` -> `versioned data migration`
- API 进程启动只负责启动服务，不负责偷偷修改生产数据
- 重型数据修复走后台车道，避免把升级窗口拖得越来越长
- 开发种子和生产 baseline 严格分离

## 生产布局

标准布局如下：

- 程序目录：`/opt/serino`
- 配置目录：`/etc/serino`
- 环境文件：`/etc/serino/serino.env`
- 数据目录：`/var/lib/serino`
- 日志目录：`/var/log/serino`
- 备份目录：`/var/backups/serino`
- 命令入口：`/usr/local/bin/sercli`
- systemd 服务：`serino.service`

运行时的核心数据都在 `/var/lib/serino` 下：

- 主业务库：`aerisun.db`
- Waline 数据库：`waline.db`
- LangGraph 数据库：`langgraph.db`
- 媒体和资源文件：`media/`
- 密钥与运行时私有文件：`secrets/`

这也是升级失败时整机回滚的主要恢复单元。

## 生产安装链路

正式安装路径由安装器负责完成，顺序固定：

1. 写入生产配置与部署布局
2. 拉取镜像
3. 执行 `schema migration`
4. 应用 `production baseline`
5. 执行所有可达的 `blocking data migrations`
6. 初始化首次管理员
7. 启动服务并等待 `readyz`
8. 调度 `background data migrations`

这里的三个概念要区分清楚：

- `schema migration`
  只负责数据库结构
- `production baseline`
  只负责“新生产环境必须具备的确定性默认数据和标准形态”
- `versioned data migration`
  负责版本升级时对旧数据做增量修复

## 生产升级链路

升级路径由 `sercli upgrade vX.Y.Z` 触发，顺序是：

1. 备份当前安装和整个 `/var/lib/serino`
2. 停服务
3. 安装新版本 payload
4. 拉取新镜像
5. 执行 `schema migration`
6. 执行 `blocking data migrations`
7. 启动服务并等待 `readyz`
8. 调度 `background data migrations`

几个关键约束：

- 升级失败时，阻塞式阶段会回滚到升级前备份
- 不依赖应用启动时补跑 migration
- 生产不再依赖 `AERISUN_SEED_REFERENCE_DATA` / `AERISUN_DATA_BACKFILL_ENABLED` 这类软开关保证正确性

## 数据演进模型

### 1. Schema Migration

- 由 Alembic 维护
- 当前活跃链已重置到新的 production baseline 起点
- baseline 之前的旧 Alembic 历史已从仓库和运行时路径彻底移除

### 2. Production Baseline

- 当前生产只有一个正式 baseline
- baseline 是代码维护的，不是预制数据库文件
- baseline 只包含：
  - 当前生产 head 对应的结构前提
  - 确定性的 reference/default data
  - 新安装必须具备的标准资源引用和配置形态
- baseline 不包含：
  - 首次管理员账号
  - 密钥、密码、环境相关动态值

### 3. Versioned Data Migration

每个未来版本的数据修复都按 revision 管理。

规则如下：

- 一个 Alembic revision 最多对应一个同前缀 data migration
- data migration 必须显式声明：
  - `migration_key`
  - `schema_revision`
  - `summary`
  - `mode=blocking|background`
  - `apply(...)`
- 已发布 data migration 只能追加，不能原地修改
- 所有 data migration 必须幂等

## 迁移执行

### Blocking

适合：

- 小而快
- 必须在新版本服务对外前完成
- 修改量可控

这类迁移在安装/升级期间同步执行，失败会阻断上线。

### Background(一般不使用)

适合：

- 大表扫描
- 跨库重写
- 耗时长但不影响新版本立即对外

这类迁移在服务就绪后调度执行，状态会被记录到 migration journal。失败不会直接把已经成功启动的服务拉下线，但必须尽快处理。

## Migration Journal

生产系统用 `_aerisun_data_migrations` 作为统一 journal，记录：

- `migration_key`
- `schema_revision`
- `kind`
- `mode`
- `status`
- `checksum`
- `applied_at`
- `last_error`

当前它同时记录：

- baseline 是否已应用
- blocking data migration 是否已完成
- background data migration 是否待调度、运行中或失败

`sercli doctor` 和 `sercli migrate status` 都以这张表为真相源，不再靠 bootstrap 时代的推断逻辑。

## 推荐运维命令

### 日常查看

```bash
sercli status --verbose
sercli status --json
sercli doctor
sercli wait --timeout 180
sercli logs --since 15m api waline caddy
sercli logs --list-services
```

### 显式升级

```bash
sercli upgrade --check vX.Y.Z
sercli upgrade vX.Y.Z
sercli doctor
sercli migrate status
```

生产上建议始终显式指定版本号，不建议裸跑 `sercli upgrade` 去追踪渠道最新。
如果升级窗口比默认就绪等待更长，可以显式传入 `sercli upgrade --ready-timeout 300 vX.Y.Z`。

### 手工执行 migration

```bash
sercli migrate schema
sercli migrate data --mode blocking
sercli migrate data --mode background
sercli migrate status
```

这组命令主要用于诊断、补跑和故障处理，不应替代正常安装/升级流程。

## 发布前 Smoke Gate

仓库根目录提供了一条发布前 smoke gate：

```bash
bash scripts/release-smoke-gate.sh
```

它默认会串行执行三层检查：

- shell 语法检查：安装器、`sercli`、关键 backend runtime 脚本
- 运维核心回归：baseline、data migration、`sercli`、install/upgrade/rollback 生命周期测试
- Docker release smoke：真实构建 release 镜像并校验首页、admin、Waline、`readyz`

如果本地只想先跑前两层，可以先跳过容器烟测：

```bash
bash scripts/release-smoke-gate.sh --skip-docker-smoke
```

## 手动 Compose 部署

手动 `docker compose up -d` 已经不再等价于“完整生产安装”，因为 API 启动不会自动执行 baseline 和生产数据迁移。

如果必须手控部署，最少应按下面顺序执行：

```bash
docker compose --env-file .env.production.local -f docker-compose.release.yml pull
docker compose --env-file .env.production.local -f docker-compose.release.yml run --rm --no-deps api /bin/bash /app/backend/scripts/migrate.sh
docker compose --env-file .env.production.local -f docker-compose.release.yml run --rm --no-deps api /bin/bash /app/backend/scripts/baseline-prod.sh
docker compose --env-file .env.production.local -f docker-compose.release.yml run --rm --no-deps api /bin/bash /app/backend/scripts/data-migrate.sh apply --mode blocking
docker compose --env-file .env.production.local -f docker-compose.release.yml run --rm --no-deps api /bin/bash /app/backend/scripts/first-admin-prod.sh
docker compose --env-file .env.production.local -f docker-compose.release.yml up -d
docker compose --env-file .env.production.local -f docker-compose.release.yml run --rm --no-deps api /bin/bash /app/backend/scripts/data-migrate.sh schedule --mode background
```

如果不是为了特殊调试，仍然推荐直接用安装器和 `sercli`。

## 开发与生产的边界

- `dev_seed.py` 只服务开发和测试
- `seed_profile` 只服务开发/测试流程
- 生产运维不要把 dev seed 当成 prod baseline 的替代
- 生产数据问题应通过新的 versioned data migration 体系解决

## 约束

- 不要修改已发布的 Alembic revision 和 data migration 语义
- 新版本如需改数据，优先新增 data migration，不要把逻辑偷偷塞回 baseline
- baseline 不是“随便堆默认值”的地方，只放“所有新生产实例都必须拥有的确定性初始状态”
- 大迁移先判断是否必须 blocking；不是必须，就走 background
- 任何需要运行时自动修库的想法，都应先回答：为什么不能进入 install/upgrade 的正式链路
