# 权限与授权 API

## 1. 模块范围

本模块负责系统角色、权限点、角色权限绑定，以及用户系统角色授权。  
为避免与工作空间成员授权混淆，本模块只处理“系统级授权”；工作空间内授权仍以 `workspaces/{workspace_id}/members` 为准。

## 2. 资源清单

| 资源 | 说明 |
|---|---|
| `roles` | 系统角色 |
| `permissions` | 权限点字典 |
| `role-permissions` | 角色与权限点绑定关系 |
| `user-roles` | 用户与系统角色绑定关系 |

## 3. 接口定义

### 3.1 查询权限点列表

- 方法：`GET`
- 路径：`/api/v1/permissions`

查询参数：

- `module_name`
- `keyword`
- `status`

### 3.2 查询单个权限点

- 方法：`GET`
- 路径：`/api/v1/permissions/{permission_id}`

### 3.3 查询角色权限集合

- 方法：`GET`
- 路径：`/api/v1/roles/{role_id}/permissions`

### 3.4 全量替换角色权限集合

- 方法：`PUT`
- 路径：`/api/v1/roles/{role_id}/permissions`

请求体：

```json
{
  "permission_ids": [
    101,
    102,
    201
  ]
}
```

### 3.5 查询用户系统角色集合

- 方法：`GET`
- 路径：`/api/v1/users/{user_id}/roles`

### 3.6 全量替换用户系统角色集合

- 方法：`PUT`
- 路径：`/api/v1/users/{user_id}/roles`

请求体：

```json
{
  "role_ids": [
    1,
    2
  ]
}
```

## 4. 业务规则

- `permissions` 为系统字典资源，MVP 阶段建议只读，不开放在线新增。
- `roles` 负责聚合权限点，不直接绑定工作空间成员关系。
- `users/{user_id}/roles` 仅管理系统级角色；工作空间内身份使用 `workspace_role` 管理。
- 角色权限与用户角色均采用全量替换语义，避免增量接口导致授权状态难以推断。
- 删除角色前必须先解除其与用户、权限点的绑定关系，或由服务端进行级联校验拦截。

## 5. 推荐错误码

| 错误码 | 说明 |
|---|---|
| `ROLE_NOT_FOUND` | 角色不存在 |
| `PERMISSION_NOT_FOUND` | 权限点不存在 |
| `ROLE_PERMISSION_BINDING_INVALID` | 角色权限绑定非法 |
| `USER_ROLE_BINDING_INVALID` | 用户角色绑定非法 |
| `SYSTEM_ROLE_DELETE_FORBIDDEN` | 系统内置角色不允许删除 |
