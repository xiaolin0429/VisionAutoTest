# VisionAutoTest

企业级跨端视觉自动化测试平台。基于 `Playwright + OpenCV + PaddleOCR` 构建视觉执行闭环，支持模板管理、Mask 处理、OCR 分析、测试用例编排、执行调度与差异报告。

## 当前状态

- **当前阶段：MVP 主链路可运行**，前后端已完成联调，视觉执行闭环贯通。
- 已完成：认证与会话管理、工作空间、环境配置、模板资产（含 OCR 分析与 Mask 预览）、测试组件与用例编排、套件、执行调度、执行报告。
- 视觉执行层：Playwright 浏览器驱动（click / input / navigate / scroll / long_press）、OpenCV 模板匹配、PaddleOCR 文本识别、差异图生成。
- 数据库：5 个 Alembic 迁移版本，含初始表结构、基准版本溯源、报告附件链路、组件步骤超时重试、模板 OCR 结果。
- 下一步：补齐通知 / Webhook、引入 Redis + Celery 异步队列、对象存储扩展、CI 集成与可观测性。

## 项目目标

- 基于 `Playwright + OpenCV + OCR` 构建跨端视觉自动化测试能力。
- 支持基准图、忽略区域、数据驱动、任务调度、差异报告和 CI 集成。
- 兼容单机运行与企业级扩展部署。
- 以严格 API 契约和规范化表设计作为实现基线。

## 目录结构

```text
backend/
  app/
    api/v1/          # RESTful 路由：iam / workspaces / assets / cases / executions
    core/            # 配置、安全、存储、HTTP 工具
    db/              # SQLAlchemy session、Alembic 迁移、bootstrap 种子
    models/          # ORM 实体（entities.py）
    schemas/         # Pydantic 契约（contracts.py）
    services/        # 业务逻辑层
    workers/         # 执行引擎：browser / vision / execution / dispatcher
  alembic/           # 数据库迁移脚本
  tests/             # pytest 自动化测试
frontend/
  src/
    api/modules/     # axios 请求模块（按业务域划分）
    auth/            # JWT 会话运行时（自动续期）
    components/      # 公共组件（AppHeader / AppSidebar / TemplateCanvas 等）
    layouts/         # AppShell 主布局
    router/          # Vue Router 路由定义
    stores/          # Pinia 状态：auth / workspace / appError
    types/           # 后端契约类型、前端模型类型
    views/           # 页面组件
doc/
  api/               # RESTful API 设计文档（共 9 个模块）
  backend/           # 服务端技术架构设计文档
  database/          # 数据库设计文档（共 8 个模块）
  frontend/          # 前端技术架构设计文档
  联调文档/          # 前后端联调总览、执行编排联调清单、接口示例
```

## 技术栈

| 层次 | 技术 |
|------|------|
| 后端运行时 | Python 3.11、FastAPI、Uvicorn |
| ORM / 迁移 | SQLAlchemy 2.x、Alembic |
| 数据库 | PostgreSQL |
| 视觉执行 | Playwright、OpenCV、PaddleOCR |
| 认证 | PyJWT（HS256）、会话续期 |
| 前端框架 | Vue 3、Vite、TypeScript |
| 前端状态 | Pinia、Vue Router |
| 前端 UI | Element Plus、@vueuse/core、Tailwind CSS |
| HTTP 客户端 | Axios |

## 快速启动

### 后端

```bash
cd backend
cp .env.example .env          # 填入数据库账号、JWT 密钥、管理员初始密码
pip install -e ".[dev]"
python -m app.db.bootstrap    # 初始化表结构 + 最小种子数据（幂等）
uvicorn app.main:app --reload
```

Swagger 文档：`http://127.0.0.1:8000/docs`

### 前端

```bash
cd frontend
npm install
npm run dev
```

前端开发服务器默认代理 `/api` 与 `/healthz` 到 `http://127.0.0.1:8000`。

### 运行测试

```bash
cd backend
# 配置独立测试库（禁止复用开发库 AutoTestDev）
cp .env.example .env.test.local   # 填入 VAT_TEST_DATABASE_URL
bash scripts/run_pytest.sh
```

## 联调说明

- 登录账号：`admin`，初始密码以 `backend/.env` 中 `VAT_DEFAULT_ADMIN_PASSWORD` 为准。
- 演示目标页：`http://127.0.0.1:8000/demo/acceptance-target`（bootstrap 默认种子）。
- 主链路聚合路径：`test-runs → case-runs → step-results`，执行详情不依赖独立报告 ID。
- 详细接口示例与错误码见 [`doc/联调文档/`](./doc/联调文档/)。

## 文档导航

### 核心业务与架构

- [PRD](./doc/企业级跨端视觉自动化测试平台PRD.md)
- [服务端技术架构设计文档](./doc/backend/服务端技术架构设计文档.md)
- [前端技术架构设计文档](./doc/frontend/前端技术架构设计文档.md)
- [文档索引](./doc/文档索引.md)

### 项目推进

- [MVP 定义](./doc/MVP定义.md)
- [实施路线图](./doc/实施路线图.md)
- [产品后续更新方向（2026-03-31）](./doc/产品后续更新方向-2026-03-31.md)

### API 设计

- [API 设计总览](./doc/api/00-API设计总览.md)
- [认证与身份 API](./doc/api/01-认证与身份API.md)
- [工作空间与成员 API](./doc/api/02-工作空间与成员API.md)
- [环境与设备配置 API](./doc/api/03-环境与设备配置API.md)
- [模板与基准资产 API](./doc/api/04-模板与基准资产API.md)
- [测试组件、用例与套件 API](./doc/api/05-测试组件_用例_套件API.md)
- [测试执行与报告 API](./doc/api/06-测试执行与报告API.md)
- [通知与Webhook API](./doc/api/07-通知与WebhookAPI.md)
- [权限与授权 API](./doc/api/08-权限与授权API.md)
- [媒体对象 API](./doc/api/09-媒体对象API.md)

### 数据库设计

- [数据库设计总览](./doc/database/00-数据库设计总览.md)
- [身份与会话模型](./doc/database/01-身份与权限模型.md)
- [工作空间与配置模型](./doc/database/02-工作空间与配置模型.md)
- [模板与基准资产模型](./doc/database/03-模板与基准资产模型.md)
- [测试编排模型](./doc/database/04-测试编排模型.md)
- [执行与报告模型](./doc/database/05-执行与报告模型.md)
- [通知与集成模型](./doc/database/06-通知与集成模型.md)
- [权限与授权模型](./doc/database/07-权限与授权模型.md)
- [媒体对象与引用模型](./doc/database/08-媒体对象与引用模型.md)

### 联调文档

- [前端联调总览](./doc/联调文档/00-前端联调总览.md)
- [执行编排联调清单](./doc/联调文档/01-执行编排联调清单.md)
- [接口示例与错误处理](./doc/联调文档/02-接口示例与错误处理.md)

## 工程原则

- API 严格使用 RESTful 风格，URL 使用名词复数，不在路径中使用动作语义。
- 数据库优先遵守行业规范：统一命名、显式主外键、必要索引、审计字段、软删除策略、乐观锁字段。
- 先收敛 `MVP`，再扩展企业级功能，避免在第一阶段同时实现多租户、调度集群、复杂报表全部能力。