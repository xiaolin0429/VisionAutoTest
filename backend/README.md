# VisionAutoTest Backend

本文档面向后端研发，聚焦 `backend/` 目录的本地运行、测试、执行链路和开发约束。

如果你想先了解项目整体定位、产品能力和当前阶段，请先看仓库根目录 `README.md`。

## 1. 后端当前状态

当前后端已经不是单纯的 MVP 骨架，而是已可支撑主链路运行的服务端实现，覆盖：

- 身份认证与会话续期
- 工作空间、成员、环境档案、环境变量、设备预设
- 模板、基准版本、Mask 区域、OCR 分析
- 测试组件、测试用例、测试套件
- `test-runs / case-runs / step-results / reports`
- 基于 `Playwright + OpenCV + PaddleOCR` 的执行闭环

近期已完成一轮后端结构治理：

- `services/execution.py` 已收口为兼容聚合层
- `services/cases.py` 已收口为兼容聚合层
- `models/entities.py` 与 `schemas/contracts.py` 已退化为兼容导出层
- workspace 相关 router 已拆分为多文件聚合
- browser worker 已引入 step registry / handler 模式

这意味着新增需求时，应优先进入领域模块，而不是继续回填到旧的聚合大文件。

## 2. 本地启动

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
cp .env.example .env
pip install -e ".[dev]"
.venv/bin/playwright install chromium
.venv/bin/python -m app.db.bootstrap
.venv/bin/uvicorn app.main:app --reload
```

Swagger 文档：`http://127.0.0.1:8000/docs`

## 3. 本地环境说明

### 3.1 开发环境文件

- `backend/.env` 仅用于本地开发，不提交仓库
- 请基于 `backend/.env.example` 创建
- 不要把真实凭据回写到 `README.md` 或 `.env.example`

### 3.2 测试环境文件

- `backend/.env.test.local` 仅用于本地测试，不提交仓库
- 请基于 `backend/.env.test.sample` 创建
- `VAT_TEST_DATABASE_URL` 必须指向独立测试库，不能复用开发库

### 3.3 常用环境变量

- `VAT_DATABASE_URL`：业务库连接
- `VAT_DATABASE_ADMIN_URL`：开发环境自动建库使用的管理库连接
- `VAT_DEFAULT_ADMIN_USERNAME` / `VAT_DEFAULT_ADMIN_PASSWORD`：默认管理员初始化配置
- `VAT_JWT_SECRET_KEY` / `VAT_JWT_ALGORITHM` / `VAT_JWT_ISSUER`：JWT 配置
- `VAT_DATA_ENCRYPTION_KEY`：敏感配置加密密钥
- `VAT_LOCAL_STORAGE_PATH`：本地媒体和执行产物目录
- `VAT_DEMO_TARGET_BASE_URL`：默认演示页地址
- `VAT_PLAYWRIGHT_HEADLESS`：是否无头执行
- `VAT_PLAYWRIGHT_NAVIGATION_TIMEOUT_MS`：浏览器导航超时
- `VAT_EXECUTION_DISPATCH_BACKEND`：执行调度后端，默认 `background_tasks`
- `VAT_EXECUTION_WORKER_BATCH_SIZE`：`deferred` 模式下单次 worker 扫描大小
- `VAT_DATABASE_AUTO_CREATE` / `VAT_DATABASE_AUTO_MIGRATE`：仅建议本地开发启用

## 4. 数据库与初始化

- `.venv/bin/python -m app.db.bootstrap` 会在开发环境下完成数据库初始化
- 默认会执行 Alembic 迁移，并幂等写入最小演示数据
- 如需跳过演示种子数据，可使用 `--skip-seed-demo-data`

默认演示资源包括：

- 默认管理员
- 演示工作空间
- 环境档案和设备预设
- 占位模板
- 演示用例和套件

默认演示目标页：`http://127.0.0.1:8000/demo/acceptance-target`

## 5. 测试

推荐运行方式：

```bash
cd backend
bash scripts/run_pytest.sh
```

如果直接运行：

```bash
.venv/bin/pytest -q
```

注意事项：

- 后端测试依赖独立测试库
- 不要复用开发库 `AutoTestDev`
- 当前后端 API 测试建议串行执行
- 并发执行可能导致测试库重建和 DDL 冲突

## 6. 执行链路说明

当前真实执行链路已支持：

- `navigate`
- `wait`
- `click`
- `input`
- `scroll`
- `long_press`
- `conditional_branch`
- `template_assert`
- `ocr_assert`

执行产物会写入：

- `media-objects`
- `report-artifacts`

当前默认调度模式：

- `BackgroundTasks` 进程内执行

可选解耦模式：

- 设置 `VAT_EXECUTION_DISPATCH_BACKEND=deferred`
- 在该模式下，`POST /api/v1/test-runs` 只创建 queued 资源
- 需要单独运行 `vat-worker-run-queued`

## 7. 视觉依赖说明

本地运行视觉断言前，需确保已安装相关依赖：

```bash
cd backend
source .venv/bin/activate
pip install -e ".[dev]"
.venv/bin/playwright install chromium
```

- `template_assert` 依赖 `opencv-python-headless`
- `ocr_assert` 依赖 `paddleocr` 及其 CPU 运行依赖

若本地未安装相关依赖，仅对应步骤会在运行时报错，普通浏览器步骤不受影响。

## 8. 开发约束

- 保持 API 契约与数据库模型文档一致
- 新逻辑不要继续回填到兼容聚合层
- 优先修改拆分后的领域模块
- 保持 `test-runs -> case-runs -> step-results` 主链路稳定
- 后端测试优先覆盖主链路和回归风险点

## 9. 后端相关文档

建议按以下顺序阅读：

1. `../README.md`
2. `../doc/README.md`
3. `../doc/backend/README.md`
4. `../doc/backend/服务端技术架构设计文档.md`
5. `../doc/api/00-API设计总览.md`
6. `../doc/database/00-数据库设计总览.md`

其他常用后端文档：

- `../doc/backend/认证生命周期规范.md`
- `../doc/backend/报告与证据模型规范.md`
- `../doc/backend/基准维护闭环规范.md`
- `../doc/backend/执行基础设施抽象规范.md`
