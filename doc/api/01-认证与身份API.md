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
    "token_type": "Bearer",
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
    "token_type": "Bearer",
    "expires_in": 7200
  }
}
```

### 3.3 获取当前会话

- 方法：`GET`
- 路径：`/api/v1/sessions/current`

说明：

- 前端在应用启动、进入受保护路由前，以及本地存在历史会话的公共页面恢复阶段，会使用该接口校验当前服务端会话锚点。
- 若服务端返回 `TOKEN_REVOKED` 或 `SESSION_NOT_FOUND`，前端应清理本地会话与工作空间上下文，并回退到登录页。

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
- `access_token` 为 JWT，必须通过 `Authorization: Bearer <token>` 传递。
- JWT 当前最少包含 `sub/sid/jti/iat/exp/iss` 六个声明；`iam_sessions` 作为服务端会话锚点。
- `access_token` 应短期有效，`refresh_token` 应支持轮换续期。
- `refresh_token` 采用单次消费模型；续期成功后，旧令牌必须进入 `used` 状态，不允许重复使用。
- 活跃 `refresh_token` 在服务端判定过期后，应写回 `expired` 状态。
- 删除当前会话后，服务端应立即吊销当前访问令牌及其活跃刷新令牌。
- 会话被吊销后，该会话下后续所有 `refresh_token` 请求都应返回“已吊销”语义，而不是笼统非法。
- `users/current` 仅返回当前操作者可见的基础身份信息，不返回敏感字段。
- 前端当前已接入自动续期闭环，`session-refreshes` 会被用于：
  - 受保护路由进入前的 access token 恢复
  - 普通业务请求命中 `401` 后的单飞续期与一次自动重试
  - access token 到期前的前置定时续期
- 前端对续期成功保持静默，不展示成功提示；对 `REFRESH_TOKEN_INVALID / REFRESH_TOKEN_EXPIRED / REFRESH_TOKEN_REVOKED / TOKEN_REVOKED / SESSION_NOT_FOUND` 统一执行“提示后回到登录页”。

## 5. 推荐错误码

| 错误码 | 说明 |
|---|---|
| `INVALID_CREDENTIALS` | 用户名或密码错误 |
| `USER_DISABLED` | 账号已禁用 |
| `TOKEN_EXPIRED` | 令牌过期 |
| `TOKEN_REVOKED` | 令牌已失效 |
| `REFRESH_TOKEN_INVALID` | 刷新令牌格式非法、已消费或不存在 |
| `REFRESH_TOKEN_EXPIRED` | 刷新令牌已过期 |
| `REFRESH_TOKEN_REVOKED` | 刷新令牌已被吊销 |
| `SESSION_NOT_FOUND` | 会话不存在 |
| `USERNAME_ALREADY_EXISTS` | 用户名冲突 |
