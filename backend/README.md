# VisionAutoTest Backend MVP

服务端 MVP 骨架，基于 `FastAPI + SQLAlchemy 2.x`，对应仓库中的 MVP、API 与数据库设计文档。

## 当前骨架覆盖

- 身份与会话
- 工作空间与成员
- 环境档案、环境变量、设备预设
- 媒体对象、模板、基准版本、忽略区域
- 测试组件、测试用例、测试套件
- 异步执行批次、用例执行实例、步骤结果、报告
- 基于 Playwright 的浏览器截图闭环（首批支持 `wait`、`click`、`input`）

## 本地启动

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
cp .env.example .env
vim .env
playwright install chromium
python -m app.db.bootstrap
uvicorn app.main:app --reload
```

`.env` 使用说明：

- `backend/.env` 仅用于本地开发，不提交到代码仓库
- 请基于 `backend/.env.example` 创建，并填写你自己的本地数据库凭据
- `backend/.env.example` 只提供安全示例，不提供真实账号密码
- 启动前必须替换所有占位符值；占位符或示例口令不会再被应用接受

默认使用本地 PostgreSQL 开发库：

- 数据库：`AutoTestDev`
- 业务库连接：通过本地 `backend/.env` 中的 `VAT_DATABASE_URL` 配置
- 管理库连接：通过本地 `backend/.env` 中的 `VAT_DATABASE_ADMIN_URL` 配置
- 媒体目录：`backend/.data/media`
- 运行环境：建议本地固定为 `VAT_APP_ENV=development`

常用本地环境变量：

- `VAT_DATABASE_URL`：业务库连接串
- `VAT_DATABASE_ADMIN_URL`：开发环境自动建库时使用的管理库连接串
- `VAT_DEFAULT_ADMIN_USERNAME` / `VAT_DEFAULT_ADMIN_PASSWORD`：默认管理员初始化配置
- `VAT_LOCAL_STORAGE_PATH`：本地媒体与执行产物目录
- `VAT_PLAYWRIGHT_HEADLESS`：是否启用无头浏览器
- `VAT_PLAYWRIGHT_NAVIGATION_TIMEOUT_MS`：浏览器页面导航超时
- `VAT_DATABASE_AUTO_CREATE` / `VAT_DATABASE_AUTO_MIGRATE`：仅建议本地开发启用

安全说明：

- 不要把真实数据库账号、密码、Token、证书或个人环境变量回写到 `README.md` 或 `.env.example`
- `backend/.env` 为本地私有文件，若需要共享示例，只修改 `backend/.env.example`
- `staging` / `production` 环境不允许启用自动建库和自动迁移

数据库初始化说明：

- `python -m app.db.bootstrap`：创建开发库 `AutoTestDev`（若不存在）、执行 Alembic 迁移、初始化默认管理员
- 应用启动时只有在显式开启 `VAT_DATABASE_AUTO_CREATE=true` 或 `VAT_DATABASE_AUTO_MIGRATE=true` 时才会执行对应动作
- 测试数据库不由应用自动创建，测试阶段需通过环境变量提供独立测试库连接

测试环境补充说明：

- 后端测试依赖独立测试库，不应复用本地开发库 `AutoTestDev`
- 运行测试前请单独提供 `VAT_TEST_DATABASE_URL`
- `backend/tests/test_app.py` 会在测试前重建测试库结构，并使用独立的本地媒体目录

执行链路补充说明：

- 当前 MVP 首批真实浏览器执行支持 `wait`、`click`、`input`
- 用例执行完成后会产出真实截图，并写入 `media-objects` 与 `report-artifacts`
- 当前尚未接入 `OpenCV` / `OCR` 的视觉断言闭环，模板比对与 OCR 断言留待下一阶段实现

初始化时会自动创建一个默认管理员：

- 仅当 `VAT_DEFAULT_ADMIN_USERNAME` 与 `VAT_DEFAULT_ADMIN_PASSWORD` 同时提供时才会初始化
- 默认管理员密码必须由本地环境显式提供，不能使用示例占位符

## 后续建议

- 将当前示例令牌替换为 JWT
- 将环境变量“伪加密”替换为正式密钥管理方案
- 将执行 Worker 从进程内任务平滑升级为 `Celery + Redis`
