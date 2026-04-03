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
.venv/bin/playwright install chromium
.venv/bin/python -m app.db.bootstrap
.venv/bin/uvicorn app.main:app --reload
```

首次启动后的默认验收资源：

- `bootstrap` 会在开发环境幂等创建一套最小演示数据：默认管理员、演示工作空间、环境档案、设备预设、占位模板、演示用例、演示套件
- 默认演示环境 `base_url` 指向后端内置页面 `http://127.0.0.1:8000/demo/acceptance-target`
- 如本地服务不跑在 `127.0.0.1:8000`，可通过 `VAT_DEMO_TARGET_BASE_URL` 覆盖
- 可直接用这套资源触发一次执行验收，不再依赖额外被测页服务

`.env` 使用说明：

- `backend/.env` 仅用于本地开发，不提交到代码仓库
- 请基于 `backend/.env.example` 创建，并填写你自己的本地数据库凭据
- `backend/.env` 只用于开发服务启动、手工联调和本地 API 调试
- `backend/.env.example` 只提供安全示例，不提供真实账号密码
- 启动前必须替换所有占位符值；占位符或示例口令不会再被应用接受

`.env.test.local` 使用说明：

- `backend/.env.test.local` 仅用于本地后端自动化测试，不提交到代码仓库
- 请基于 `backend/.env.test.sample` 创建，并填写独立测试库连接
- `VAT_TEST_DATABASE_URL` 必须指向与 `backend/.env` 中 `VAT_DATABASE_URL` 不同的数据库
- 后端测试会重建测试库结构，禁止复用开发库 `AutoTestDev`

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
- `VAT_JWT_SECRET_KEY` / `VAT_JWT_ALGORITHM` / `VAT_JWT_ISSUER`：JWT 签名与声明配置
- `VAT_DATA_ENCRYPTION_KEY`：环境变量等敏感配置的应用级加密密钥
- `VAT_LOCAL_STORAGE_PATH`：本地媒体与执行产物目录
- `VAT_DEMO_TARGET_BASE_URL`：默认演示环境指向的内置被测页地址
- `VAT_PLAYWRIGHT_HEADLESS`：是否启用无头浏览器
- `VAT_PLAYWRIGHT_NAVIGATION_TIMEOUT_MS`：浏览器页面导航超时
- `VAT_EXECUTION_DISPATCH_BACKEND`：执行调度后端，默认 `background_tasks`，可切到 `deferred`
- `VAT_EXECUTION_WORKER_BATCH_SIZE`：`deferred` 模式下单次 worker 扫描的 queued 批次数
- `VAT_DATABASE_AUTO_CREATE` / `VAT_DATABASE_AUTO_MIGRATE`：仅建议本地开发启用

安全说明：

- 不要把真实数据库账号、密码、Token、证书或个人环境变量回写到 `README.md` 或 `.env.example`
- `backend/.env` 为本地私有文件，若需要共享示例，只修改 `backend/.env.example`
- `staging` / `production` 环境不允许启用自动建库和自动迁移

数据库初始化说明：

- `.venv/bin/python -m app.db.bootstrap`：创建开发库 `AutoTestDev`（若不存在）、执行 Alembic 迁移、初始化默认管理员
- `.venv/bin/python -m app.db.bootstrap` 默认还会在开发环境幂等初始化演示验收数据；如需跳过可使用 `--skip-seed-demo-data`
- 应用启动时只有在显式开启 `VAT_DATABASE_AUTO_CREATE=true` 或 `VAT_DATABASE_AUTO_MIGRATE=true` 时才会执行对应动作
- 测试数据库不由应用自动创建，测试阶段需通过环境变量提供独立测试库连接

测试环境补充说明：

- 后端测试依赖独立测试库，不应复用本地开发库 `AutoTestDev`
- 运行测试前请提供 `VAT_TEST_DATABASE_URL`，推荐写入 `backend/.env.test.local`
- `backend/tests/test_app.py` 会在测试前重建测试库结构，并使用独立的本地媒体目录
- 推荐运行方式：`./scripts/run_pytest.sh`
- 若直接执行命令，请使用后端虚拟环境：`.venv/bin/pytest -q`

执行链路补充说明：

- 当前 MVP 首批真实浏览器执行支持 `wait`、`click`、`input`
- 当前后端已扩展 `template_assert`、`ocr_assert` 执行链路；前端步骤编辑与联调仍可按后续节奏接入
- 用例执行完成后会产出真实截图，并写入 `media-objects` 与 `report-artifacts`
- 本地运行视觉断言前请确认已安装 OpenCV / PaddleOCR 相关依赖
- 默认执行调度后端为 `BackgroundTasks`；若需要把执行与 API 进程解耦，可设置 `VAT_EXECUTION_DISPATCH_BACKEND=deferred`
- `deferred` 模式下，`POST /api/v1/test-runs` 只创建 queued 资源，不会在请求进程内启动执行；需要单独运行 `vat-worker-run-queued`

视觉断言本地依赖补充说明：

```bash
cd backend
source .venv/bin/activate
pip install -e ".[dev]"
.venv/bin/playwright install chromium
```

- `template_assert` 依赖 `opencv-python-headless`
- `ocr_assert` 依赖 `paddleocr` 及其 CPU 运行依赖
- 若本地未安装上述依赖，仅在执行对应步骤时会返回运行时错误，普通 `wait/click/input` 链路不受影响

初始化时会自动创建一个默认管理员：

- 仅当 `VAT_DEFAULT_ADMIN_USERNAME` 与 `VAT_DEFAULT_ADMIN_PASSWORD` 同时提供时才会初始化
- 默认管理员密码必须由本地环境显式提供，不能使用示例占位符

默认验收建议路径：

```text
1. 执行 `.venv/bin/python -m app.db.bootstrap`
2. 启动后端 `.venv/bin/uvicorn app.main:app --reload`
3. 打开 `http://127.0.0.1:8000/demo/acceptance-target` 确认演示页可访问
4. 使用默认管理员登录前端，直接选择 seeded 的工作空间和演示套件发起执行
```

## 后续建议

- 将执行 Worker 从进程内任务平滑升级为 `Celery + Redis`
- 将本地文件存储平滑升级为对象存储抽象层的远端实现
