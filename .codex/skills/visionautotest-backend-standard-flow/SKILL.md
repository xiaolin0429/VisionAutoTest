---
name: visionautotest-backend-standard-flow
description: Use for backend work in VisionAutoTest involving `backend/app`, `backend/tests`, or backend-related `doc/api`, `doc/database`, and `doc/backend` docs. Applies to API delivery, schema and model changes, service-layer logic, execution pipeline work, contract alignment, bug fixes, and backend architecture-aware implementation in the MVP.
---

# VisionAutoTest Backend Standard Flow

## Overview
This skill standardizes backend delivery in VisionAutoTest. It keeps implementation aligned with the repo's backend architecture, RESTful API contracts, database design baseline, workspace isolation model, and the team's required self-review and validation flow.

## Use When
- The task touches `backend/app/api`, `backend/app/schemas`, `backend/app/models`, `backend/app/services`, `backend/app/workers`, `backend/app/core`, `backend/app/db`, or `backend/tests`.
- The task adds or changes backend APIs, request and response contracts, data models, business rules, execution flows, or worker logic.
- The task requires aligning backend code with product, API, database, or backend architecture docs.
- The task requires fixing backend defects without drifting from the current MVP architecture.

Typical prompts:
- “新增模板基准版本切换接口并对齐现有契约”
- “调整 `test-runs` 聚合字段并同步模型与接口”
- “修复工作空间成员权限判断异常”
- “把环境变量存储逻辑替换成正式密钥方案前先收敛接口层”
- “补充执行链路取消逻辑并保证报告状态正确”
- “评估并接入 Alembic / JWT / Celery 改造的后端实现边界”

## Authoritative Sources
Read the smallest viable set before coding:
- Project overview: `../../../README.md`
- Backend architecture baseline: `../../../doc/backend/服务端技术架构设计文档.md`
- API conventions first: `../../../doc/api/00-API设计总览.md`
- Domain API and database files matching the task under `../../../doc/api/` and `../../../doc/database/`
- Backend truth when docs and code may drift: `../../../backend/app/api/v1/`, `../../../backend/app/schemas/`, `../../../backend/app/models/`

For backend work, prefer this routing:
- IAM and sessions: `../../../doc/api/01-认证与身份API.md`, `../../../doc/database/01-身份与权限模型.md`, `../../../backend/app/services/iam.py`
- Workspaces, environments, devices: `../../../doc/api/02-工作空间与成员API.md`, `../../../doc/api/03-环境与设备配置API.md`, `../../../doc/database/02-工作空间与配置模型.md`, `../../../backend/app/services/workspace.py`
- Templates, baselines, media: `../../../doc/api/04-模板与基准资产API.md`, `../../../doc/api/09-媒体对象API.md`, `../../../doc/database/03-模板与基准资产模型.md`, `../../../doc/database/08-媒体对象与引用模型.md`, `../../../backend/app/services/assets.py`
- Components, test cases, suites: `../../../doc/api/05-测试组件_用例_套件API.md`, `../../../doc/database/04-测试编排模型.md`, `../../../backend/app/services/cases.py`
- Test runs, case runs, reports: `../../../doc/api/06-测试执行与报告API.md`, `../../../doc/database/05-执行与报告模型.md`, `../../../backend/app/services/execution.py`, `../../../backend/app/workers/execution.py`

## Standard Workflow
1. **Define the boundary**
   - Clarify the business domain, affected resources, and whether the change touches API contracts, database models, worker behavior, or only internal backend logic.
   - For multi-file work, create a short plan before editing.

2. **Read only the necessary context**
   - Start from one overview file and one or two domain files.
   - Then inspect the exact backend modules already implementing the domain.
   - If a contract is unclear, verify route, schema, model, and service code before changing behavior.

3. **Implement in the correct layer**
   - `backend/app/api/v1`: request parsing, dependency injection, protocol mapping, and response assembly only.
   - `backend/app/schemas`: request and response contracts, DTO boundaries, validation shape.
   - `backend/app/models`: persistence entities and storage structure.
   - `backend/app/services`: business rules, access checks, lifecycle transitions, and orchestration.
   - `backend/app/workers`: asynchronous execution flow and long-running processing logic.
   - `backend/app/core` and `backend/app/db`: shared infrastructure, configuration, security helpers, and session management.

4. **Follow project implementation rules**
   - Keep APIs strictly RESTful; do not introduce action-style paths.
   - Keep resource names, status enums, and field naming aligned with the authoritative API and database docs.
   - Respect workspace isolation through the existing `X-Workspace-Id` mechanism; do not introduce ad-hoc tenancy handling.
   - Keep route handlers thin; do not push business rules into the router layer.
   - Prefer extending existing patterns over introducing new abstractions or unrelated refactors.
   - Treat the current `FastAPI + SQLAlchemy + SQLite` MVP as the runtime truth unless the task explicitly upgrades the architecture.
   - When touching `JWT`, `Alembic`, `Celery + Redis`, object storage, or secret management, first compare the current codebase with `../../../doc/backend/服务端技术架构设计文档.md` and `../../../backend/README.md` to avoid implementing against the wrong target state.

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
- Do not let router files become mixed protocol and business-rule layers.
- Do not change API behavior without checking the matching contract document first.
- Do not change schema or model names in code without aligning docs and dependent layers.
- Do not bypass existing error response and request ID patterns in `backend/app/core/http.py`.
- Do not implement speculative enterprise architecture if the task only requires MVP-compatible delivery.

## Handoff Expectations
When finishing a backend task, report:
- What changed
- Which files were touched
- Which docs or architecture sources guided the change
- What validation was run
- Any remaining risk, warning, or follow-up suggestion
