# 认证与身份 API

## 1. 模块范围

本模块负责登录会话、令牌续期、当前用户信息，以及最小范围的用户主体管理。  
角色权限绑定与用户系统角色授权已拆分到 [08-权限与授权 API](./08-权限与授权API.md)，避免单篇文档过长。

## 2. 资源清单

| 资源 | 说明 |
|---|---|
| `sessions` | 登录会话 |
| `session-refreshes` | 令牌续期请求 |
| `users` | 用户主体 |

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

### 3.2 创建令牌续期请求

- 方法：`POST`
- 路径：`/api/v1/session-refreshes`

请求体：

```json
{
  "refresh_token": "refresh_token"
}
```

响应体：

```json
{
  "data": {
    "access_token": "new_jwt_token",
    "refresh_token": "new_refresh_token",
    "expires_in": 7200
  }
}
```

### 3.3 获取当前会话

- 方法：`GET`
- 路径：`/api/v1/sessions/current`

### 3.4 删除当前会话

- 方法：`DELETE`
- 路径：`/api/v1/sessions/current`

### 3.5 获取当前用户

- 方法：`GET`
- 路径：`/api/v1/users/current`

### 3.6 查询用户列表

- 方法：`GET`
- 路径：`/api/v1/users`
- 查询参数：`page`、`page_size`、`status`、`keyword`

### 3.7 创建用户

- 方法：`POST`
- 路径：`/api/v1/users`

### 3.8 查询单个用户

- 方法：`GET`
- 路径：`/api/v1/users/{user_id}`

### 3.9 更新用户

- 方法：`PATCH`
- 路径：`/api/v1/users/{user_id}`

允许更新字段：

- `display_name`
- `email`
- `mobile`
- `status`

## 4. 业务规则

- `username` 全局唯一，不允许复用。
- `access_token` 应短期有效，`refresh_token` 应支持轮换续期。
- 删除当前会话后，服务端应立即吊销当前访问令牌及其活跃刷新令牌。
- `users/current` 仅返回当前操作者可见的基础身份信息，不返回敏感字段。

## 5. 推荐错误码

| 错误码 | 说明 |
|---|---|
| `INVALID_CREDENTIALS` | 用户名或密码错误 |
| `USER_DISABLED` | 账号已禁用 |
| `TOKEN_EXPIRED` | 令牌过期 |
| `TOKEN_REVOKED` | 令牌已失效 |
| `REFRESH_TOKEN_INVALID` | 刷新令牌非法或已失效 |
| `SESSION_NOT_FOUND` | 会话不存在 |
| `USERNAME_ALREADY_EXISTS` | 用户名冲突 |
