# API 设计总览

## 1. 设计原则

- 严格遵循 RESTful 风格。
- URL 只使用资源名词，且统一使用复数。
- 资源层级通过父子关系表达，不在路径中混入流程动作。
- 使用标准 HTTP 方法表达语义。
- 接口版本统一放在路径前缀：`/api/v1`。
- 所有时间字段统一使用 `ISO 8601` UTC 格式。
- 所有响应默认 `application/json; charset=utf-8`。

## 2. 资源命名规范

- 集合资源：`/workspaces`
- 单资源：`/workspaces/{workspace_id}`
- 子资源：`/workspaces/{workspace_id}/members`
- 独立资源：`/test-runs/{run_id}/case-runs`

禁止以下风格：

- `/getWorkspaces`
- `/createCase`
- `/runSuiteNow`

## 3. HTTP 方法规范

| 方法 | 语义 | 说明 |
|---|---|---|
| `GET` | 查询资源 | 不修改服务端状态 |
| `POST` | 创建资源 | 非幂等；支持 `Idempotency-Key` |
| `PUT` | 全量替换资源 | 幂等 |
| `PATCH` | 局部更新资源 | 幂等 |
| `DELETE` | 删除资源 | 默认执行逻辑删除，明细流水除外 |

## 4. 通用请求头

| Header | 必填 | 说明 |
|---|---|---|
| `Authorization: Bearer <token>` | 是 | 用户身份凭证 |
| `X-Workspace-Id` | 视接口而定 | 多租户隔离头，工作空间内接口必填 |
| `Idempotency-Key` | 建议 | 创建执行任务等异步接口建议传入 |
| `X-Request-Id` | 建议 | 便于链路追踪 |

## 5. 通用响应结构

### 5.1 成功响应

```json
{
  "data": {},
  "meta": {
    "request_id": "req_01HV8B4Q0Q7Y4D8TQ7M9Q0R2J6"
  }
}
```

### 5.2 分页响应

```json
{
  "data": [],
  "meta": {
    "page": 1,
    "page_size": 20,
    "total": 186,
    "request_id": "req_01HV8B4Q0Q7Y4D8TQ7M9Q0R2J6"
  }
}
```

### 5.3 错误响应

```json
{
  "error": {
    "code": "WORKSPACE_FORBIDDEN",
    "message": "Current user does not have access to the workspace.",
    "details": [
      {
        "field": "workspace_id",
        "reason": "not_member"
      }
    ]
  },
  "meta": {
    "request_id": "req_01HV8B4Q0Q7Y4D8TQ7M9Q0R2J6"
  }
}
```

## 6. 状态码规范

| 状态码 | 场景 |
|---|---|
| `200 OK` | 查询或更新成功 |
| `201 Created` | 资源创建成功 |
| `204 No Content` | 删除成功 |
| `400 Bad Request` | 参数格式错误 |
| `401 Unauthorized` | 未认证 |
| `403 Forbidden` | 已认证但无权限 |
| `404 Not Found` | 资源不存在 |
| `409 Conflict` | 唯一约束冲突、状态冲突 |
| `422 Unprocessable Entity` | 业务规则校验失败 |
| `429 Too Many Requests` | 触发限流 |
| `500 Internal Server Error` | 未预期服务端异常 |

## 7. 过滤、排序、分页规范

- 分页参数：`page`、`page_size`
- 排序参数：`sort`
- 过滤参数：字段等值过滤直接作为 query string

示例：

```text
GET /api/v1/test-runs?page=1&page_size=20&status=running&sort=-created_at
```

排序规则：

- `created_at` 表示升序
- `-created_at` 表示降序

## 8. 并发与幂等

- `POST /test-runs` 必须支持 `Idempotency-Key`，防止 CI 重复触发。
- `PATCH` 和 `PUT` 建议配合 `version_no` 或 `If-Match` 做乐观锁控制。
- 任务取消采用 `PATCH /test-runs/{run_id}` 修改状态，不新增动作型路径。

## 9. 异步任务资源设计

平台中的执行类请求统一采用“先创建资源、再轮询资源状态”的方式：

1. 客户端 `POST /test-runs`
2. 服务端返回 `201 Created`
3. 响应体中返回 `status=queued`
4. 客户端通过 `GET /test-runs/{run_id}` 或 `GET /test-runs/{run_id}/case-runs` 轮询结果

## 10. 模块拆分

- [01-认证与身份 API](/Users/xiaolin/Dev/VisionAutoTest/doc/api/01-认证与身份API.md)
- [02-工作空间与成员 API](/Users/xiaolin/Dev/VisionAutoTest/doc/api/02-工作空间与成员API.md)
- [03-环境与设备配置 API](/Users/xiaolin/Dev/VisionAutoTest/doc/api/03-环境与设备配置API.md)
- [04-模板与基准资产 API](/Users/xiaolin/Dev/VisionAutoTest/doc/api/04-模板与基准资产API.md)
- [05-测试组件、用例与套件 API](/Users/xiaolin/Dev/VisionAutoTest/doc/api/05-测试组件_用例_套件API.md)
- [06-测试执行与报告 API](/Users/xiaolin/Dev/VisionAutoTest/doc/api/06-测试执行与报告API.md)
- [07-通知与 Webhook API](/Users/xiaolin/Dev/VisionAutoTest/doc/api/07-通知与Webhook API.md)
