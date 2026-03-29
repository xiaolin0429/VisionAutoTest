---
name: visionautotest-frontend-standard-flow
description: Use for frontend work in VisionAutoTest involving `frontend/src` pages, components, layouts, stores, router, API modules, types, styles, or frontend docs. Applies to feature delivery, refactors, bug fixes, backend contract alignment, workspace-aware flows, loading and error states, and build verification in the Vue 3 MVP.
---

# VisionAutoTest Frontend Standard Flow

## Overview
This skill standardizes frontend delivery in VisionAutoTest. It keeps implementation aligned with the repo's Vue 3 MVP architecture, RESTful API contracts, workspace isolation model, and the team's required self-review and validation flow.

## Use When
- The task touches `frontend/src/views`, `frontend/src/components`, `frontend/src/layouts`, `frontend/src/router`, `frontend/src/stores`, `frontend/src/api`, `frontend/src/types`, or `frontend/src/styles`.
- The task turns product, API, backend, or database design into frontend behavior.
- The task requires adding or adjusting loading, empty, error, permission, or workspace-switching behavior.
- The task requires checking whether frontend fields, routes, and interactions still match backend contracts.

Typical prompts:
- “给模板页增加可编辑忽略区域能力”
- “把执行详情页改成实时轮询”
- “对齐后端新增的 `test-runs` 字段”
- “修复 workspace 切换后的页面数据错乱”

## Authoritative Sources
Read the smallest viable set before coding:
- Project overview: `../../../README.md`
- Frontend architecture baseline: `../../../doc/frontend/前端技术架构设计文档.md`
- API conventions first: `../../../doc/api/00-API设计总览.md`
- Domain API file matching the task under `../../../doc/api/`
- Backend truth when docs and code may drift: `../../../backend/app/api/v1/`, `../../../backend/app/schemas/`, `../../../backend/app/models/`
- Frontend development decision tree for change classification, file landing, risk checks, and validation hints: `./references/frontend-development-decision-tree.md`

For frontend work, prefer this routing:
- Login/session: `../../../doc/api/01-认证与身份API.md`
- Workspace/member boundary: `../../../doc/api/02-工作空间与成员API.md`
- Environments/devices: `../../../doc/api/03-环境与设备配置API.md`
- Templates/baselines/media: `../../../doc/api/04-模板与基准资产API.md`, `../../../doc/api/09-媒体对象API.md`
- Cases/suites: `../../../doc/api/05-测试组件_用例_套件API.md`
- Runs/reports: `../../../doc/api/06-测试执行与报告API.md`
- Permissions: `../../../doc/api/08-权限与授权API.md`

Read `./references/frontend-development-decision-tree.md` when:
- You need to decide where a new frontend change belongs before editing.
- You need a yes/no style path to choose between view, component, store, API module, type, or util changes.
- You want quick reminders about current hotspots, risks, and validation focus before implementation.

## Standard Workflow
1. **Define the boundary**
   - Clarify the business domain, affected routes, required API resources, and whether the change is page-level, component-level, store-level, or API-mapping-level.
   - For multi-file work, create a short plan before editing.

2. **Read only the necessary context**
   - Start from one overview file and one or two domain files.
   - Then inspect the exact frontend modules already implementing the domain.
   - If a contract is unclear, verify backend route and schema code before changing UI fields.

3. **Implement in the correct layer**
   - `frontend/src/views`: route-level pages and page orchestration.
   - `frontend/src/components`: reusable UI blocks and focused business widgets.
   - `frontend/src/layouts`: shell and global frame composition.
   - `frontend/src/stores`: cross-route state, persistence, and workspace-aware state.
   - `frontend/src/api/modules`: request functions plus DTO-to-model mapping.
   - `frontend/src/types/backend.ts`: backend DTOs in backend naming.
   - `frontend/src/types/models.ts`: UI-facing models in frontend naming.
   - `frontend/src/utils`: formatting and shared non-visual helpers.

4. **Follow project implementation rules**
   - Use `Vue 3` Composition API with `<script setup lang="ts">`.
   - Keep route components lazy-loaded unless there is a strong reason not to.
   - Prefer `Element Plus` for enterprise controls and `Tailwind` for layout and spacing.
   - Keep backend `snake_case` inside DTOs and API mapping code; do not leak it into page state and templates.
   - Reuse the existing request client, `ApiError`, router guards, and global error reporting flow.
   - Respect workspace isolation through the existing `X-Workspace-Id` mechanism; do not add ad-hoc workspace headers unless the current client flow cannot cover the case.
   - Keep RESTful resource semantics aligned with docs and backend routes; do not invent action-style endpoints in frontend code.

5. **Design UX states explicitly**
   - Every changed page or panel should account for loading, empty, success, and failure states.
   - Destructive or important actions should expose user feedback through clear status text or `ElMessage`.
   - Long-running execution flows should keep future polling or SSE extension in mind and avoid hard-coding one-shot assumptions.

6. **Self-review after each completed code segment**
   - Check contract alignment: request path, params, body, and mapped fields.
   - Check architectural placement: view vs component vs store vs API module.
   - Check naming consistency: backend DTO vs frontend model vs rendered label.
   - Check reactive correctness: `ref`, `computed`, `watch`, `onMounted` usage is minimal and correct.
   - Check UX completeness: loading, empty, error, disabled, and success feedback are covered.
   - Check scope discipline: no unrelated refactors, no duplicate abstractions, no dead code.

7. **Validate before handoff**
   - Run the narrowest useful verification first.
   - For frontend code changes, default to `cd frontend && npm run build`.
   - If a specific flow is risky, inspect the changed route, API mapping, or state path before broadening validation.
   - If validation is blocked by environment issues, report the exact blocker and the likely impact.

## Frontend Guardrails
- Prefer extending existing patterns over introducing new libraries or architectural layers.
- Keep page data aggregation close to the route view unless multiple pages reuse the same orchestration.
- Keep reusable data transformation inside API modules instead of duplicating conversion logic across views.
- Favor small, focused components; avoid turning views into giant mixed concerns files.
- Do not bypass `frontend/src/api/client.ts` for normal HTTP calls.
- Do not mix mock structures with real contract structures in the same view.

## Handoff Expectations
When finishing a frontend task, report:
- What changed
- Which files were touched
- Which contract or architecture sources guided the change
- What validation was run
- Any remaining risk, warning, or follow-up suggestion
