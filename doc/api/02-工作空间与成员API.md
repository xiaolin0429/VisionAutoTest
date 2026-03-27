# 工作空间与成员 API

## 1. 模块范围

本模块负责多租户隔离的核心资源，包括工作空间、空间成员和成员角色。

## 2. 资源清单

| 资源 | 说明 |
|---|---|
| `workspaces` | 工作空间 |
| `members` | 工作空间成员 |

## 3. 接口定义

### 3.1 查询工作空间列表

- 方法：`GET`
- 路径：`/api/v1/workspaces`

查询参数：

- `page`
- `page_size`
- `status`
- `keyword`

### 3.2 创建工作空间

- 方法：`POST`
- 路径：`/api/v1/workspaces`

### 3.3 查询工作空间详情

- 方法：`GET`
- 路径：`/api/v1/workspaces/{workspace_id}`

### 3.4 更新工作空间

- 方法：`PATCH`
- 路径：`/api/v1/workspaces/{workspace_id}`

允许更新字段：

- `name`
- `description`
- `status`

### 3.5 查询工作空间成员

- 方法：`GET`
- 路径：`/api/v1/workspaces/{workspace_id}/members`

### 3.6 新增工作空间成员

- 方法：`POST`
- 路径：`/api/v1/workspaces/{workspace_id}/members`

请求体：

```json
{
  "user_id": 10001,
  "workspace_role": "workspace_admin"
}
```

### 3.7 更新成员角色

- 方法：`PATCH`
- 路径：`/api/v1/workspaces/{workspace_id}/members/{member_id}`

### 3.8 移除成员

- 方法：`DELETE`
- 路径：`/api/v1/workspaces/{workspace_id}/members/{member_id}`

## 4. 业务规则

- 工作空间编码 `workspace_code` 全局唯一。
- 至少保留 1 名 `workspace_admin`，不得移除最后一个管理员。
- 工作空间内的所有业务资源必须通过 `X-Workspace-Id` 或路径参数强绑定空间。
- 非系统管理员只能看到自己有成员关系的工作空间。

## 5. 推荐错误码

| 错误码 | 说明 |
|---|---|
| `WORKSPACE_NOT_FOUND` | 工作空间不存在 |
| `WORKSPACE_CODE_EXISTS` | 工作空间编码重复 |
| `WORKSPACE_FORBIDDEN` | 无该空间访问权限 |
| `WORKSPACE_LAST_ADMIN_PROTECTED` | 不允许删除最后一个管理员 |
| `WORKSPACE_MEMBER_EXISTS` | 用户已是该空间成员 |
