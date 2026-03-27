# 认证与身份 API

## 1. 模块范围

本模块负责登录会话、当前用户信息、用户与角色的基础管理。为保持 RESTful 一致性，登录能力抽象为 `sessions` 资源。

## 2. 资源清单

| 资源 | 说明 |
|---|---|
| `sessions` | 登录会话 |
| `users` | 用户主体 |
| `roles` | 角色定义 |

## 3. 接口定义

### 3.1 创建登录会话

- 方法：`POST`
- 路径：`/api/v1/sessions`

请求体：

```json
{
  "username": "qa_admin",
  "password": "******"
}
```

响应体：

```json
{
  "data": {
    "session_id": "ses_01HV8Q2P8KQ6E2R4N4Z8A5P6JG",
    "access_token": "jwt_token",
    "refresh_token": "refresh_token",
    "expires_in": 7200,
    "user": {
      "id": 10001,
      "username": "qa_admin",
      "display_name": "QA Admin"
    }
  }
}
```

### 3.2 获取当前会话

- 方法：`GET`
- 路径：`/api/v1/sessions/current`

### 3.3 删除当前会话

- 方法：`DELETE`
- 路径：`/api/v1/sessions/current`

### 3.4 获取当前用户

- 方法：`GET`
- 路径：`/api/v1/users/current`

### 3.5 查询用户列表

- 方法：`GET`
- 路径：`/api/v1/users`
- 查询参数：`page`、`page_size`、`status`、`keyword`

### 3.6 创建用户

- 方法：`POST`
- 路径：`/api/v1/users`

### 3.7 查询单个用户

- 方法：`GET`
- 路径：`/api/v1/users/{user_id}`

### 3.8 更新用户

- 方法：`PATCH`
- 路径：`/api/v1/users/{user_id}`

允许更新字段：

- `display_name`
- `email`
- `mobile`
- `status`

### 3.9 查询角色列表

- 方法：`GET`
- 路径：`/api/v1/roles`

### 3.10 创建角色

- 方法：`POST`
- 路径：`/api/v1/roles`

### 3.11 更新角色

- 方法：`PATCH`
- 路径：`/api/v1/roles/{role_id}`

## 4. 业务规则

- `username` 全局唯一，不允许复用。
- 删除当前会话后，服务端应立即吊销访问令牌。
- 角色只定义权限集合，不直接附着工作空间；工作空间授权通过成员关系完成。
- `users/current` 仅返回当前操作者可见的基础身份信息，不返回敏感字段。

## 5. 推荐错误码

| 错误码 | 说明 |
|---|---|
| `INVALID_CREDENTIALS` | 用户名或密码错误 |
| `USER_DISABLED` | 账号已禁用 |
| `TOKEN_EXPIRED` | 令牌过期 |
| `TOKEN_REVOKED` | 令牌已失效 |
| `USERNAME_ALREADY_EXISTS` | 用户名冲突 |
