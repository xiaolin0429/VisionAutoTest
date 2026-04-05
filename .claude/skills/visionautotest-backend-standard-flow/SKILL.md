---
name: visionautotest-backend-standard-flow
description: >
  Use for ALL backend work in VisionAutoTest involving `backend/app`, `backend/tests`, or backend-related `doc/api`, `doc/database`, and `doc/backend` docs.
  Applies to API delivery, schema and model changes, service-layer logic, execution pipeline work, contract alignment, bug fixes, and backend architecture-aware implementation in the MVP.
  MANDATORY TRIGGERS: Any task touching backend/app, FastAPI routes, SQLAlchemy models, Pydantic schemas, backend services, worker logic, database migrations,
  backend tests, API contract changes, or any backend build/test task in this project.
  Also trigger when the user mentions: 后端, 接口, API, 服务端, 数据库, 模型, 契约, 执行链路, 权限, 工作空间隔离, Alembic, or any Chinese description of backend work in VisionAutoTest.
---

# VisionAutoTest Backend Standard Flow

## Overview
This skill standardizes backend delivery in VisionAutoTest. It keeps implementation aligned with the repo's backend architecture, RESTful API contracts, database design baseline, workspace isolation model, and the team's required self-review and validation flow.
Unless the task is explicitly read-only, backend delivery must follow a documentation-first sequence: `对应 API 文档 -> 对应数据库文档 -> schemas -> service -> router -> 测试`.

## Use When
- The task touches `backend/app/api`, `backend/app/schemas`, `backend/app/models`, `backend/app/services`, `backend/app/workers`, `backend/app/core`, `backend/app/db`, or `backend/tests`.
- The task adds or changes backend APIs, request and response contracts, data models, business rules, execution flows, or worker logic.
- The task requires aligning backend code with product, API, database, or backend architecture docs.
- The task requires fixing backend defects without drifting from the current MVP architecture.

Typical prompts:
- "新增模板基准版本切换接口并对齐现有契约"
- "调整 `test-runs` 聚合字段并同步模型与接口"
- "修复工作空间成员权限判断异常"
- "把环境变量存储逻辑替换成正式密钥方案前先收敛接口层"
- "补充执行链路取消逻辑并保证报告状态正确"
- "评估并接入 Alembic / JWT / Celery 改造的后端实现边界"

## Authoritative Sources
Read the smallest viable set before coding:
- Project overview: `README.md` (project root)
- Backend architecture baseline: `doc/backend/服务端技术架构设计文档.md`
- API conventions first: `doc/api/00-API设计总览.md`
- Domain API and database files matching the task under `doc/api/` and `doc/database/`
- Backend truth when docs and code may drift: `backend/app/api/v1/`, `backend/app/schemas/`, `backend/app/models/`

For backend work, prefer this routing:
- IAM and sessions: `doc/api/01-认证与身份API.md`, `doc/database/01-身份与权限模型.md`, `backend/app/services/iam.py`
- Workspaces, environments, devices: `doc/api/02-工作空间与成员API.md`, `doc/api/03-环境与设备配置API.md`, `doc/database/02-工作空间与配置模型.md`, `backend/app/services/workspace.py`
- Templates, baselines, media: `doc/api/04-模板与基准资产API.md`, `doc/api/09-媒体对象API.md`, `doc/database/03-模板与基准资产模型.md`, `doc/database/08-媒体对象与引用模型.md`, `backend/app/services/assets.py`
- Components, test cases, suites: `doc/api/05-测试组件_用例_套件API.md`, `doc/database/04-测试编排模型.md`, `backend/app/services/component_service.py`, `backend/app/services/test_case_service.py`, `backend/app/services/suite_service.py`, `backend/app/services/step_payload_validator.py`, `backend/app/services/branch_validator.py` (`backend/app/services/cases.py` is a compatibility facade)
- Test runs, case runs, reports: `doc/api/06-测试执行与报告API.md`, `doc/database/05-执行与报告模型.md`, `backend/app/services/execution_report.py`, `backend/app/services/execution_status.py`, `backend/app/services/execution_steps.py`, `backend/app/services/execution_readiness.py`, `backend/app/workers/execution.py`, `backend/app/workers/browser.py` (`backend/app/services/execution.py` is a compatibility facade)

## Backend Development Map
Use this map to decide where to start and which files to touch.

### 1. Entry Checklist
- If the task changes API behavior, read the matching file under `doc/api/` first.
- If the task changes fields, constraints, status, or relationships, read the matching file under `doc/database/` next.
- Then locate the current contract in `backend/app/schemas/contracts.py`.
- Then locate the business rule owner in `backend/app/services/`.
- Then locate the protocol adapter in `backend/app/api/v1/`.
- Only after that decide whether `backend/app/models/`, `backend/app/workers/`, `backend/app/core/`, or `backend/app/db/` also need changes.

### 2. Domain-to-File Map
- **IAM / 登录 / 会话**: `backend/app/api/v1/iam.py` -> `backend/app/services/iam.py` -> `backend/app/models/entities.py`
- **工作空间 / 成员 / 环境 / 设备**: `backend/app/api/v1/workspaces.py` -> `backend/app/services/workspace.py` -> `backend/app/models/entities.py`
- **媒体 / 模板 / 基准 / 忽略区域**: `backend/app/api/v1/assets.py` -> `backend/app/services/assets.py` -> `backend/app/models/entities.py`
- **组件 / 用例 / 套件 / 步骤编排**: `backend/app/api/v1/cases.py` -> `backend/app/services/component_service.py` / `backend/app/services/test_case_service.py` / `backend/app/services/suite_service.py` / `backend/app/services/step_payload_validator.py` / `backend/app/services/branch_validator.py` -> `backend/app/models/entities.py`
- **执行批次 / 用例执行 / 步骤结果 / 报告**: `backend/app/api/v1/executions.py` -> `backend/app/services/execution_report.py` / `backend/app/services/execution_status.py` / `backend/app/services/execution_steps.py` / `backend/app/services/execution_readiness.py` -> `backend/app/workers/execution.py` -> `backend/app/workers/browser.py`
- Compatibility facades: `backend/app/services/cases.py` and `backend/app/services/execution.py` are compatibility-only aggregation layers. Read them only to understand current exports or old callers; do not place new business logic there.

### 3. Change-Type Map
- **只改接口字段或响应结构**: 先改 `doc/api/`，再改 `backend/app/schemas/contracts.py`，最后对齐 router/service 返回。
- **只改业务规则**: 先改 `doc/api/` 或 `doc/database/` 中对应规则，再改 `backend/app/services/`，最后检查 router 是否仍然保持轻薄。
- **新增或修改持久化字段**: 先改 `doc/database/`，再改 `backend/app/models/entities.py`，再补 `schemas`、`services`、Alembic 迁移。
- **新增执行链路能力**: 先看 `doc/api/06-*` 与 `doc/database/05-*`，再改 `backend/app/services/execution.py`，必要时再改 `backend/app/workers/execution.py` 与 `backend/app/workers/browser.py`。
- **改鉴权、请求头、错误结构、全局基础设施**: 优先看 `backend/app/api/deps.py`、`backend/app/core/http.py`、`backend/app/core/security.py`、`backend/app/db/session.py`，并先确认不会破坏现有统一协议。

### 4. Layer Responsibilities Map
- `backend/app/schemas`: 只负责契约、字段校验、DTO 边界，不承载业务流程。
- `backend/app/services`: 负责业务规则、状态流转、权限校验、资源编排，是默认的核心落点。
- `backend/app/api/v1`: 只负责 HTTP 协议映射、依赖注入、入参与出参拼装。
- `backend/app/models`: 负责实体与约束表达，不直接承载接口语义。
- `backend/app/workers`: 负责异步、长耗时、执行器相关逻辑，不反向侵入 router。
- `backend/app/core` / `backend/app/db`: 负责配置、安全、响应协议、数据库会话与迁移，不承载业务域规则。

### 5. Validation Map
- 改 `schemas` / `service` / `router` 后，至少补一次对应接口或对应业务链路测试。
- 改执行链路时，优先验证 `test-runs -> case-runs -> step-results -> reports` 主链路。
- 改工作空间隔离时，必须验证 `Authorization` 与 `X-Workspace-Id` 的联合行为。
- 改媒体或模板引用时，必须验证引用关系不会破坏删除保护或执行证据链。

## Backend Decision Tree
Use this tree when deciding the first move for a backend task.

### 1. If the task is read-only analysis
- Read the smallest matching files under `doc/api/`, `doc/database/`, and the target backend module.
- Do not propose code changes before confirming the current contract and runtime truth.

### 2. If the task adds or changes an API
- Start at the matching `doc/api/` document.
- Then read the matching `doc/database/` document if fields, status, or relationships are involved.
- Then update `backend/app/schemas/contracts.py`.
- Then implement the rule in `backend/app/services/`.
- Then wire or adjust the endpoint in `backend/app/api/v1/`.
- Then run the narrowest API or workflow test.

### 3. If the task adds or changes persistence fields
- Start at the matching `doc/database/` document.
- Confirm whether the API contract also changes; if yes, update `doc/api/` in the same turn.
- Then update `backend/app/models/entities.py`.
- Then add or adjust Alembic migration files.
- Then align `schemas`, `services`, and `router`.
- Then verify create/read/update flows for that resource.

### 4. If the task changes only business rules
- Start from the matching API or database rule document.
- Then change `backend/app/services/` first.
- Touch `schemas` only if validation shape or response shape changes.
- Touch `router` only if request parsing or response assembly must change.
- Add or update tests that prove the rule.

### 5. If the task touches execution, worker, or browser automation
- Start at `doc/api/06-测试执行与报告API.md` and `doc/database/05-执行与报告模型.md`.
- Then inspect the specialized execution modules under `backend/app/services/` first: `execution_report.py`, `execution_status.py`, `execution_steps.py`, `execution_readiness.py`.
- Then inspect `backend/app/workers/execution.py`.
- Then inspect `backend/app/workers/browser.py` if browser behavior changes.
- Preserve the current MVP truth: `BackgroundTasks + process_test_run + Playwright screenshot artifact`.

### 6. If the task touches authentication, session, or permission headers
- Start at `doc/api/01-认证与身份API.md` and the workspace-related API docs if `X-Workspace-Id` is involved.
- Then inspect `backend/app/api/deps.py`, `backend/app/services/iam.py`, and `backend/app/services/helpers.py`.
- Touch `backend/app/core/security.py` only when token or secret behavior truly changes.
- Re-check every affected endpoint for `401`, `403`, and workspace isolation behavior.

### 7. If the task touches shared infrastructure
- For response shape and request tracing: inspect `backend/app/core/http.py`.
- For settings and environment switches: inspect `backend/app/core/config.py`.
- For database lifecycle and sessions: inspect `backend/app/db/session.py`, `backend/app/db/bootstrap.py`, and `backend/app/db/migrations.py`.
- Do not move business-domain rules into `core` or `db`.

### 8. If the task seems to require edits in many layers
- Stop and classify the task first: contract change, data change, rule change, or execution change.
- Follow the default order `对应 API 文档 -> 对应数据库文档 -> schemas -> service -> router -> 测试`.
- Only add `models`, `workers`, `core`, or `db` when the classified change genuinely requires them.

## Standard Workflow
1. **Define the boundary**
   - Clarify the business domain, affected resources, and whether the change touches API contracts, database models, worker behavior, or only internal backend logic.
   - For multi-file work, create a short plan before editing.

2. **Read only the necessary context**
   - Start from one overview file and one or two domain files.
   - Then inspect the exact backend modules already implementing the domain.
   - If a contract is unclear, verify route, schema, model, and service code before changing behavior.
   - For implementation tasks, always follow this order before coding: `对应 API 文档 -> 对应数据库文档 -> schemas -> service -> router -> 测试`.

3. **Implement in the required order**
   - Default delivery order is fixed: `对应 API 文档 -> 对应数据库文档 -> schemas -> service -> router -> 测试`.
   - Update the matching API document first when the contract or business rule changes.
   - Update the matching database document next when storage fields, constraints, or relationships change.
   - Then implement request and response contracts in `backend/app/schemas`.
   - Then implement business rules in `backend/app/services`.
   - Then connect the protocol layer in `backend/app/api/v1`.
   - Finally run the narrowest useful backend tests.
   - `backend/app/workers`, `backend/app/core`, and `backend/app/db` are supporting layers and should be changed only when the task truly requires them.

4. **Follow project implementation rules**
   - Keep APIs strictly RESTful; do not introduce action-style paths.
   - Keep resource names, status enums, and field naming aligned with the authoritative API and database docs.
   - Respect workspace isolation through the existing `X-Workspace-Id` mechanism; do not introduce ad-hoc tenancy handling.
   - Keep route handlers thin; do not push business rules into the router layer.
   - Prefer extending existing patterns over introducing new abstractions or unrelated refactors.
- Treat the current `FastAPI + SQLAlchemy + SQLite` MVP as the runtime truth unless the task explicitly upgrades the architecture.
- When touching `JWT`, `Alembic`, `Celery + Redis`, object storage, or secret management, first compare the current codebase with `doc/backend/服务端技术架构设计文档.md` and `backend/README.md` to avoid implementing against the wrong target state.
- Treat `backend/app/services/cases.py` and `backend/app/services/execution.py` as frozen compatibility facades. New business logic must go into the specialized modules they export from, not back into the facade files.

5. **Synchronize docs when contracts change**
   - If API paths, request or response fields, status transitions, business rules, or model fields change, update the matching API and database docs in the same turn.
   - Keep API, schema, service behavior, and model naming aligned together.

6. **Self-review after each completed code segment**
   - Check boundary placement: router vs schema vs model vs service vs worker.
   - Check contract alignment: path, params, headers, body, response, and error code.
   - Check data alignment: entity fields, schema fields, and doc terms remain consistent.
   - Check rule completeness: permissions, workspace scope, status transitions, and idempotency behavior are covered.
   - Check engineering discipline: no unrelated refactors, no duplicate logic, no dead code.
   - Follow the repository rule that every produced code segment must be self-reviewed before moving on.

7. **Validate before handoff**
   - Run the narrowest useful verification first.
   - For backend changes, default to `cd backend && pytest -q`.
   - If the change is isolated, prefer a narrower test path before broadening.
   - If validation is blocked by environment issues, report the exact blocker and likely impact.

## Backend Guardrails
- Do not read the whole documentation tree by default; use the smallest viable document set.
- Do not skip the default implementation order: `对应 API 文档 -> 对应数据库文档 -> schemas -> service -> router -> 测试`, unless the user explicitly requests a different scope such as read-only analysis.
- Do not let router files become mixed protocol and business-rule layers.
- Do not change API behavior without checking the matching contract document first.
- Do not change schema or model names in code without aligning docs and dependent layers.
- Do not bypass existing error response and request ID patterns in `backend/app/core/http.py`.
- Do not implement speculative enterprise architecture if the task only requires MVP-compatible delivery.
- Do not add new business logic to frozen compatibility facades: `backend/app/services/cases.py` and `backend/app/services/execution.py`.
- When a change relates to orchestration or execution, implement it in the specialized modules first, then export through the facade only if an existing caller still depends on that symbol.
- If you touch a compatibility facade, the default expectation is "rewire exports only". If you believe real logic must be added there, explicitly justify why the specialized module route is insufficient before coding.

## Handoff Expectations
When finishing a backend task, report:
- What changed
- Which files were touched
- Which docs or architecture sources guided the change
- What validation was run
- Any remaining risk, warning, or follow-up suggestion
