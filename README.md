# Serino

![License](https://img.shields.io/badge/License-MIT-yellow.svg)
![Frontend](https://img.shields.io/badge/Frontend-React_18-blue.svg)
![Backend](https://img.shields.io/badge/Backend-FastAPI-009688.svg)
![Agent](https://img.shields.io/badge/Agent-LangGraph-6f42c1.svg)

Serino 设计初衷是打造一个专注内容、方便配置、探索融入 Agent 与自动化的个人博客项目。

> 🙏 **致谢**：本项目参考了 [waline](https://github.com/walinejs/waline)、[Shiro](https://github.com/Innei/Shiro) 、[astro-theme-pure](https://github.com/cworld1/astro-theme-pure)、 [Claude Code](https://github.com/anthropics/claude-code) ，我深深地沉醉于他们的匠心设计，在此由衷感谢和致敬这些项目作者的开源精神。

## ✨ 示例站点

- [Aerisun](https://aerisun.top/)

欢迎体验 Serino 带来的极简之美与灵活运转之便！

---

## 🚀 核心特性

- 🛡️ **绝对隔离**：代码、数据与配置彻底解耦。无损升级确保历史积累与私有存，储零覆写。
- 🚀 **一键安装升级**：一句命令行部署！安装、重启、升级流程收敛，部署维护更省心。
- ⚙️ **舒适配置**：告别修改源码，全站参数均通过分层设计的后台 UI 实时调整，清晰易拓。
- 🎨 **极简美学**：素雅留白搭配内敛交互，带来全端自适应的无干扰沉浸阅读。
- 📝 **扩展语法**：搭载强大的 Markdown 扩展解析引擎，轻松驾驭个性的多样化排版。
- 🤖 **Agent 管家**：内置 LangGraph 自动化工作流，各种编排等你探索
- 🔌 **MCP 原生支持**：内建标准 MCP API，百余能力，借助严密权限域安全对接 openclaw。
- ☁️ **OSS 双活备份**：资源上传下载都经由 OSS 加速，异步本地同步，安全无成本的加速体验。
- 📧 **原生订阅投递**：系统自带 SMTP 引擎，第一时间将新文精美推达读者订阅邮箱。
- 🤝 **社交与 RSS**：轻量的 RSS 抓取构建朋友圈，第一时间了解友站的最新动态

---

## ⚙️ 技术架构

基于现代化的全栈体系构建，看重性能优化与极致分离：

- **Frontend / Admin**：React 18 + Vite (SPA)、TailwindCSS + shadcn/ui、TanStack Query 与 Zod 运行时校验。
- **Backend / API**：Python 3.13 + FastAPI、SQLAlchemy 2.0 异步驱动。
- **Database**：SQLite 3 (WAL 模式并发优化)，业务、评论 (Waline)、工作流 (LangGraph) 实现三库独立切割。
- **AI & Workflow**：LangGraph 1.0+ 状态机、内置 MCP Server。
- **Contract-First**：基于 OpenAPI + Orval 自动生成类型安全的前端通讯层。

---

## 📖 系统设计与文档

想要深入了解 Aerisun 背后“图解化”的核心架构，请阅读：

- [项目架构 (Architecture)](docs/architecture.md)

---

## 🐳 快速开始

### 📦 一键自动化安装（推荐）

面向可连接（可以不是国际）互联网的 `Ubuntu/Debian` Linux 环境。安装器将`自动配置 Docker、防火墙`并以`交互式向导`引导完成启动：

```bash
curl -fsSL https://install.aerisun.top/serino/install.sh | bash

```

### 🐳 Docker Compose 手动部署

如果你偏好手控部署结构：

```bash
mkdir aerisun && cd aerisun
wget https://raw.githubusercontent.com/Aerisun/Aerisun/main/docker-compose.release.yml
wget https://raw.githubusercontent.com/Aerisun/Aerisun/main/.env.production.local.example -O .env.production.local

vim .env.production.local # 必须填写初始化管理员账号、密码等必要配置
docker compose --env-file .env.production.local -f docker-compose.release.yml up -d

```

---

## 💻 本地开发指南

环境要求：`Node.js 22.x+`、`pnpm`、`uv (Python)`。

```bash
# 1.拉取代码
git clone https://github.com/Aerisun/Serino

# 2. 安装前端与后端依赖
pnpm install --frozen-lockfile
cd backend && uv sync --dev

# 3. 启动开发环境（支持多工作树）
make dev        # 启动方式 1：灌入开发用假数据 (Dev Seed)
make dev-pseed  # 启动方式 2：灌入生产初始化数据，用于调整生产种子 (Prod Seed)
# 密码改废进不了后台? 试试 cd backend & uv run aerisun-create-admin

make dev-stop   # 停止整套本地开发环境

curl -fsSL https://install.aerisun.top/serino/dev/vX.Y.Z/install.sh | bash # 测试安装（除了使用最新的 dev 渠道和镜像来源，别的与正式安装器完全一致）
# 单台机器一次只应选择一个渠道，切换先行 `sercli uninstall --force` 再重装；因为 CDN 缓存的关系，所以使用版本号避免错误
```

- 默认前台地址：`http://127.0.0.1:8080/`
- 默认后台地址：`http://127.0.0.1:3001/admin/`
- 开发本地默认管理员账密：`admin / admin123`
