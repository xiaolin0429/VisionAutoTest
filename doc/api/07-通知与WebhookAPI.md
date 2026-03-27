# 通知与 Webhook API

## 1. 模块范围

本模块负责通知渠道、告警规则、Webhook 终端及投递记录。

## 2. 资源清单

| 资源 | 说明 |
|---|---|
| `notification-channels` | 通知渠道 |
| `alert-rules` | 告警规则 |
| `webhook-endpoints` | Webhook 终端 |
| `webhook-deliveries` | Webhook 投递记录 |

## 3. 接口定义

### 3.1 查询通知渠道列表

- 方法：`GET`
- 路径：`/api/v1/notification-channels`

### 3.2 创建通知渠道

- 方法：`POST`
- 路径：`/api/v1/notification-channels`

### 3.3 更新通知渠道

- 方法：`PATCH`
- 路径：`/api/v1/notification-channels/{notification_channel_id}`

### 3.4 查询告警规则列表

- 方法：`GET`
- 路径：`/api/v1/alert-rules`

### 3.5 创建告警规则

- 方法：`POST`
- 路径：`/api/v1/alert-rules`

### 3.6 更新告警规则

- 方法：`PATCH`
- 路径：`/api/v1/alert-rules/{alert_rule_id}`

### 3.7 查询 Webhook 终端列表

- 方法：`GET`
- 路径：`/api/v1/webhook-endpoints`

### 3.8 创建 Webhook 终端

- 方法：`POST`
- 路径：`/api/v1/webhook-endpoints`

### 3.9 更新 Webhook 终端

- 方法：`PATCH`
- 路径：`/api/v1/webhook-endpoints/{webhook_endpoint_id}`

### 3.10 查询 Webhook 投递记录

- 方法：`GET`
- 路径：`/api/v1/webhook-endpoints/{webhook_endpoint_id}/deliveries`

## 4. 业务规则

- 通知渠道与工作空间强绑定。
- Webhook 终端必须支持签名密钥和重试策略。
- 投递记录为审计流水，不允许更新和逻辑删除。
- 告警规则只负责条件与路由，不与具体执行逻辑耦合。

## 5. 推荐错误码

| 错误码 | 说明 |
|---|---|
| `NOTIFICATION_CHANNEL_NOT_FOUND` | 通知渠道不存在 |
| `ALERT_RULE_NOT_FOUND` | 告警规则不存在 |
| `WEBHOOK_ENDPOINT_NOT_FOUND` | Webhook 终端不存在 |
| `WEBHOOK_SIGNATURE_INVALID` | Webhook 签名配置非法 |
