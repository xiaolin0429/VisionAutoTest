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
- 用例执行实例和步骤结果为执行流水，不允许逻辑删除。
- 报告为执行结果快照，应与执行批次一一对应。
- 大文件证据链通过 `artifact_url` 或对象存储键返回，不直接内联在响应中。
- MVP 首批浏览器执行闭环会产出真实截图证据；执行截图通过 `step-results.actual_media_object_id` 和 `report_artifacts` 关联。

## 6. 推荐错误码

| 错误码 | 说明 |
|---|---|
| `TEST_RUN_NOT_FOUND` | 执行批次不存在 |
| `TEST_RUN_STATUS_CONFLICT` | 状态流转非法 |
| `CASE_RUN_NOT_FOUND` | 用例执行实例不存在 |
| `REPORT_NOT_FOUND` | 报告不存在 |
| `IDEMPOTENCY_KEY_CONFLICT` | 幂等键冲突 |
| `TEST_SUITE_EMPTY` | 套件未包含任何可执行用例 |
