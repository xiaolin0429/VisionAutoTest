# 测试执行与报告 API

## 1. 模块范围

本模块负责异步执行资源、用例执行明细、步骤结果和报告查询。

## 2. 资源清单

| 资源 | 说明 |
|---|---|
| `test-runs` | 执行批次 |
| `case-runs` | 用例执行实例 |
| `step-results` | 步骤执行结果 |
| `reports` | 报告 |

## 3. 接口定义

### 3.1 创建执行批次

- 方法：`POST`
- 路径：`/api/v1/test-runs`
- 建议请求头：`Idempotency-Key`

请求体：

```json
{
  "test_suite_id": 90001,
  "environment_profile_id": 30001,
  "device_profile_id": 40001,
  "trigger_source": "manual"
}
```

重跑模式（`rerun_from_run_id` 与 `rerun_filter` 同时传入时生效）：

```json
{
  "rerun_from_run_id": 100,
  "rerun_filter": "failed"
}
```

重跑模式说明：

- `rerun_from_run_id`：指定要从哪个已完成的执行批次中提取失败用例。
- `rerun_filter`：目前仅支持 `"failed"`，提取状态为 `failed` 或 `error` 的用例执行实例。
- 重跑模式下 `test_suite_id`、`environment_profile_id`、`device_profile_id` 均可省略，自动继承原批次的配置；若显式传入则覆盖继承值。
- 新批次的 `description` 自动填充为 `"重跑自 #<原批次ID>"`（调用方未传时）。

### 3.2 查询执行批次列表

- 方法：`GET`
- 路径：`/api/v1/test-runs`

### 3.3 查询执行批次详情

- 方法：`GET`
- 路径：`/api/v1/test-runs/{test_run_id}`

### 3.4 更新执行批次状态

- 方法：`PATCH`
- 路径：`/api/v1/test-runs/{test_run_id}`

说明：

- 仅允许由 `queued` 或 `running` 变为 `cancelling`
- 不允许客户端直接写入终态 `passed`、`failed`
- 创建前要求：套件状态必须为 `active`，套件内测试用例与引用组件必须为 `published`

### 3.5 查询批次下用例执行实例

- 方法：`GET`
- 路径：`/api/v1/test-runs/{test_run_id}/case-runs`

### 3.6 查询单个用例执行实例

- 方法：`GET`
- 路径：`/api/v1/case-runs/{case_run_id}`

### 3.7 查询步骤结果

- 方法：`GET`
- 路径：`/api/v1/case-runs/{case_run_id}/step-results`

### 3.8 查询报告详情

- 方法：`GET`
- 路径：`/api/v1/reports/{report_id}`

### 3.9 查询报告产物

- 方法：`GET`
- 路径：`/api/v1/reports/{report_id}/artifacts`

## 4. 状态枚举建议

### 4.1 test-run 状态

- `queued`
- `running`
- `cancelling`
- `cancelled`
- `passed`
- `failed`
- `partial_failed`
- `error`

### 4.2 case-run 状态

- `pending`
- `running`
- `passed`
- `failed`
- `error`
- `skipped`
- `cancelled`

## 5. 业务规则

- `test-runs` 一经创建即生成独立资源，不使用同步阻塞返回最终结果。
- 空套件不允许创建执行批次；套件至少需要包含 1 个可执行用例。
- `component_call` 步骤在执行时会展开为组件内部的真实执行步骤；`step-results` 返回展开后的线性步骤结果。
- 步骤执行结果中的 `failed` 表示断言不通过；`error` 表示依赖缺失、载荷非法或运行时异常。
- `wait/click/input/navigate/scroll/long_press/component_call` 不产出 `failed`，仅可能为 `passed` 或 `error`。
- 用例执行实例和步骤结果为执行流水，不允许逻辑删除。
- 报告为执行结果快照，应与执行批次一一对应。
- 大文件证据链通过 `artifact_url` 或对象存储键返回，不直接内联在响应中。
- MVP 首批浏览器执行闭环会产出真实截图证据；执行截图通过 `step-results.actual_media_object_id` 和 `report_artifacts` 关联。
- `template_assert` 会在 `step-results` 中写入 `expected_media_object_id / actual_media_object_id / diff_media_object_id`，用于定位基准图、实际截图和差异图。
- `ocr_assert` 会在 `step-results` 中写入 `actual_media_object_id`，用于回溯 OCR 截图证据。
- `step-results` 额外返回执行后修复定位元信息：`repair_resource_type / repair_resource_id / repair_route_path / repair_step_no`。
- 修复定位优先级建议为：`template` > `component` > `test_case`，用于前端在失败后直接回跳到最合适的修复资源。
- `report.summary_status` 必须与 `test-run.status` 保持一致；报告摘要中的结构化状态不得与执行终态冲突。
- 报告摘要 `summary_json` 当前固定包含：
  - `status`
  - `counts.total/passed/failed/error/cancelled`
  - `failure.code/summary`
  - `timing.started_at/finished_at/duration_ms`
  - `artifacts.total/by_type`
- `summary_json.failure` 在 `failed/error/partial_failed/cancelled` 场景下必须返回稳定可消费的结构；仅 `passed` 场景允许为 `null`。
- `case-runs.failure_reason_code` 与 `case-runs.failure_summary` 在 `failed/error/cancelled` 场景下必须稳定返回，前端不应自行从步骤明细反推主失败原因。
- 当前报告产物类型收口为：
  - `run_screenshot`
  - `step_actual`
  - `step_diff`
  - `step_ocr`
- `report_artifacts` 作为报告级索引，允许同时关联 `case_run_id` 与 `step_result_id`，前端不应再依赖文件名或备注推断证据来源。
- `report_artifacts.artifact_url` 当前定义为稳定访问路径，统一返回 `/api/v1/media-objects/{media_object_id}/content`；它不再等价于底层对象键。

## 6. 推荐错误码

| 错误码 | 说明 |
|---|---|
| `TEST_RUN_NOT_FOUND` | 执行批次不存在 |
| `TEST_RUN_STATUS_CONFLICT` | 状态流转非法 |
| `CASE_RUN_NOT_FOUND` | 用例执行实例不存在 |
| `REPORT_NOT_FOUND` | 报告不存在 |
| `IDEMPOTENCY_KEY_CONFLICT` | 幂等键冲突 |
| `TEST_SUITE_EMPTY` | 套件未包含任何可执行用例 |
| `NO_FAILED_CASES_TO_RERUN` | 原批次中没有失败或异常的用例，无法创建重跑批次 |
| `TEST_SUITE_NOT_ACTIVE` | 套件未处于可执行状态 |
| `PUBLISHED_VERSION_REQUIRED` | 套件内引用了未发布的用例或组件 |
| `STEP_CONFIGURATION_INVALID` | 步骤配置与模板策略不兼容 |
| `BASELINE_REVISION_REQUIRED` | 模板缺少可执行的当前基准版本 |
| `STEP_NOT_SUPPORTED` | 当前版本暂不支持该步骤类型 |
| `STEP_EXECUTION_TIMEOUT` | 步骤执行超时 |
| `STEP_EXECUTION_ERROR` | 步骤运行时异常 |
| `BROWSER_EXECUTION_ERROR` | 浏览器初始化或运行环境异常 |
| `SCREENSHOT_CAPTURE_FAILED` | 执行完成后截图证据生成失败 |
| `TEMPLATE_ASSERTION_FAILED` | 模板断言失败 |
| `OCR_ASSERTION_FAILED` | OCR 断言失败 |
| `TEST_RUN_EXECUTION_ERROR` | 执行批次在流程级别发生异常 |
| `TEST_RUN_CANCELLED` | 执行批次被取消 |
