# VisionAutoTest

企业级跨端视觉自动化测试平台的设计仓库。当前仓库以产品、架构、API 和数据库设计文档为主，目标是在正式编码前先固定业务边界、接口契约和数据模型，降低后续实现偏差。

## 当前状态

- 当前阶段：在文档基线之上开始进入 `MVP` 骨架实现。
- 已完成：PRD、前后端架构设计、RESTful API 设计、数据库分模块设计、MVP 与路线图。
- 新增进展：`frontend/` 已落地 `Vue 3 + Vite + Pinia + Element Plus + Tailwind CSS` 的前端 MVP 骨架。
- 下一步：继续补齐后端契约层、视觉执行链路与前后端联调。

## 项目目标

- 基于 `Playwright + OpenCV + OCR` 构建跨端视觉自动化测试能力。
- 支持基准图、忽略区域、数据驱动、任务调度、差异报告和 CI 集成。
- 兼容单机运行与企业级扩展部署。
- 以严格 API 契约和规范化表设计作为实现基线。

## 文档导航

### 核心业务与架构

- [PRD](./doc/企业级跨端视觉自动化测试平台PRD.md)
- [服务端技术架构设计文档](./doc/backend/服务端技术架构设计文档.md)
- [前端技术架构设计文档](./doc/frontend/前端技术架构设计文档.md)
- [文档索引](./doc/文档索引.md)

### 项目推进

- [MVP 定义](./doc/MVP定义.md)
- [实施路线图](./doc/实施路线图.md)

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

## 建议源码目录

正式进入实现阶段后，建议采用如下目录：

```text
backend/
  app/
    api/
    core/
    models/
    schemas/
    services/
    workers/
frontend/
  src/
    api/
    components/
    layouts/
    stores/
    views/
infra/
  docker/
  scripts/
tests/
  unit/
  integration/
```

## 前端 MVP 骨架

- 位置：`./frontend`
- 技术栈：`Vue 3`、`Vite`、`TypeScript`、`Pinia`、`Vue Router`、`Element Plus`、`Tailwind CSS`
- 当前覆盖页面：登录页、工作台、环境配置页、模板管理页、用例编辑页、套件管理页、执行记录页、执行详情页、404 页、全局异常页
- 当前运行模式：默认通过 Vite 代理直连本地后端 `FastAPI /api/v1`，前端字段与后端实际定义代码保持一致

启动方式：

```bash
cd frontend
npm install
npm run dev
```

开发联调说明：

- 前端开发服务器默认代理 `/api` 与 `/healthz` 到 `http://127.0.0.1:8000`
- 登录默认账号：`admin / admin123456`
- 当前主链路以 `test-runs -> case-runs -> step-results` 聚合执行详情，不再依赖旧 mock 的报告 ID

## 工程原则

- API 严格使用 RESTful 风格，URL 使用名词复数，不在路径中使用动作语义。
- 数据库优先遵守行业规范：统一命名、显式主外键、必要索引、审计字段、软删除策略、乐观锁字段。
- 先收敛 `MVP`，再扩展企业级功能，避免在第一阶段同时实现多租户、调度集群、复杂报表全部能力。
